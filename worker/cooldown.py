import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

TZ_BEIJING = timezone(timedelta(hours=8))


def _parse_timestamp(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value.tzinfo is None:
        value = value.replace(tzinfo=TZ_BEIJING)
    return value


def _latest_notification_from_docs(docs, level_name: str) -> dict | None:
    notifications = []
    for doc in docs:
        item = doc.to_dict()
        if item.get("level") != level_name:
            continue
        timestamp = item.get("timestamp")
        if not timestamp:
            continue
        notifications.append((item, _parse_timestamp(timestamp)))

    if not notifications:
        return None

    notifications.sort(key=lambda item: item[1], reverse=True)
    return notifications[0][0]


def _load_latest_notification(fund_code: str, level_name: str, db) -> dict | None:
    query = (
        db.collection("notifications")
        .where("fund_code", "==", fund_code)
        .where("level", "==", level_name)
        .order_by("timestamp", direction="DESCENDING")
        .limit(1)
    )
    docs = list(query.stream())
    if docs:
        return docs[0].to_dict()
    return None


def _load_latest_notification_without_composite_index(
    fund_code: str,
    level_name: str,
    db,
) -> dict | None:
    query = db.collection("notifications").where("fund_code", "==", fund_code)
    return _latest_notification_from_docs(query.stream(), level_name)


def is_in_cooldown(
    fund_code: str,
    level_name: str,
    cooldown_minutes: int,
    db,
) -> bool:
    """Check whether a notification for this fund+level is still in cooldown."""
    try:
        last_notification = _load_latest_notification(fund_code, level_name, db)
    except Exception:
        logger.warning(
            "复合索引冷却查询失败（基金 %s），尝试单字段 fallback 查询",
            fund_code,
            exc_info=True,
        )
        try:
            last_notification = _load_latest_notification_without_composite_index(
                fund_code,
                level_name,
                db,
            )
        except Exception:
            logger.warning(
                "检查冷却时间 fallback 失败（基金 %s），返回冷却中以防刷屏",
                fund_code,
                exc_info=True,
            )
            return True

    if not last_notification:
        return False

    try:
        last_ts = _parse_timestamp(last_notification.get("timestamp"))

        now = datetime.now(TZ_BEIJING)
        elapsed = now - last_ts
        if elapsed < timedelta(minutes=cooldown_minutes):
            logger.info(
                "基金 %s [%s] 仍在冷却期内（%d 分钟前通知过）",
                fund_code,
                level_name,
                elapsed.total_seconds() / 60,
            )
            return True
        return False
    except Exception:
        logger.warning(
            "解析冷却时间失败（基金 %s），返回冷却中以防刷屏",
            fund_code,
            exc_info=True,
        )
        return True


def record_notification(
    fund_code: str,
    fund_name: str,
    level_name: str,
    change_pct: float,
    price: float,
    channels: list[str],
    db,
) -> None:
    """Write a notification record to Firestore."""
    try:
        now = datetime.now(TZ_BEIJING)
        doc = {
            "fund_code": fund_code,
            "fund_name": fund_name,
            "level": level_name,
            "change_pct": change_pct,
            "price": price,
            "timestamp": now.isoformat(),
            "channels": channels,
            "delivered": True,
        }
        db.collection("notifications").add(doc)
        logger.info(
            "通知记录已写入 Firestore: %s [%s] %.2f%%",
            fund_code,
            level_name,
            change_pct,
        )
    except Exception:
        logger.exception("写入通知记录失败（基金 %s）", fund_code)
