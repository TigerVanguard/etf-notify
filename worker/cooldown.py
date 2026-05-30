import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

TZ_BEIJING = timezone(timedelta(hours=8))


def is_in_cooldown(
    fund_code: str,
    level_name: str,
    cooldown_minutes: int,
    db,
) -> bool:
    """Check whether a notification for this fund+level is still in cooldown."""
    try:
        query = (
            db.collection("notifications")
            .where("fund_code", "==", fund_code)
            .where("level", "==", level_name)
            .order_by("timestamp", direction="DESCENDING")
            .limit(1)
        )
        docs = list(query.stream())
        if not docs:
            return False

        last_notification = docs[0].to_dict()
        last_ts = last_notification.get("timestamp")

        if isinstance(last_ts, str):
            last_ts = datetime.fromisoformat(last_ts)
        if last_ts.tzinfo is None:
            last_ts = last_ts.replace(tzinfo=TZ_BEIJING)

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
            "检查冷却时间失败（基金 %s），返回冷却中以防刷屏。"
            "若持续出现，请检查 Firestore 复合索引是否已创建"
            "（fund_code ASC + level ASC + timestamp DESC）",
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
