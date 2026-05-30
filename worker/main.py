import logging
import os
from datetime import datetime, timedelta, timezone

import chinese_calendar

from config import init_firebase, load_config
from cooldown import is_in_cooldown, record_notification
from market_data import fetch_etf_quotes
from notifier import send_fcm, send_pushdeer
from threshold import check_threshold

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

TZ_BEIJING = timezone(timedelta(hours=8))
FCM_TOPIC = "etf-alerts"


def is_trading_time() -> bool:
    """Check if current time is within A-share trading hours on a workday."""
    now = datetime.now(TZ_BEIJING)

    if not chinese_calendar.is_workday(now.date()):
        logger.info("今日非工作日，跳过监控")
        return False

    hour, minute = now.hour, now.minute
    current_minutes = hour * 60 + minute
    start_minutes = 10 * 60       # 10:00
    end_minutes = 14 * 60 + 30    # 14:30

    if not (start_minutes <= current_minutes <= end_minutes):
        logger.info("当前时间 %02d:%02d 不在交易时段 (10:00~14:30)，跳过", hour, minute)
        return False

    return True


def format_notification(fund_name, fund_code, level_name, change_pct, price, prev_close):
    """Build title and body strings for notifications."""
    now = datetime.now(TZ_BEIJING)
    title = f"[{level_name}] {fund_name}({fund_code}) 跌幅 {change_pct:+.2f}%"
    body = (
        f"当前价格: {price:.3f} | 昨收: {prev_close:.3f}\n"
        f"时间: {now.strftime('%Y-%m-%d %H:%M')}"
    )
    return title, body


def save_snapshot(db, quotes: dict) -> None:
    """Save the current quotes snapshot to Firestore."""
    now = datetime.now(TZ_BEIJING)
    date_str = now.strftime("%Y-%m-%d")
    try:
        doc = {
            "date": date_str,
            "updated_at": now.isoformat(),
            "quotes": quotes,
        }
        db.collection("snapshots").document(date_str).set(doc)
        logger.info("行情快照已保存: %s", date_str)
    except Exception:
        logger.exception("保存行情快照失败")


def run():
    """Main entry point: fetch quotes, check thresholds, send notifications."""
    logger.info("=== ETF 监控 Worker 启动 ===")

    if not is_trading_time():
        return

    db = init_firebase()
    config = load_config(db)

    funds = config.get("funds", [])
    levels = config.get("levels", [])
    cooldown_minutes = config.get("cooldown_minutes", 60)
    pushdeer_key = config.get("pushdeer_key", "") or os.environ.get("PUSHDEER_KEY", "")
    fcm_enabled = config.get("fcm_enabled", True)

    enabled_funds = [f for f in funds if f.get("enabled", True)]
    if not enabled_funds:
        logger.warning("没有启用的基金，跳过")
        return

    fund_codes = [f["code"] for f in enabled_funds]
    quotes = fetch_etf_quotes(fund_codes)

    if not quotes:
        logger.warning("未获取到任何行情数据")
        return

    fund_map = {f["code"]: f for f in enabled_funds}

    for code, quote in quotes.items():
        fund_info = fund_map.get(code, {})
        fund_name = quote.get("name") or fund_info.get("name", code)
        change_pct = quote.get("change_pct", 0)
        price = quote.get("price", 0)
        prev_close = quote.get("prev_close", 0)

        triggered = check_threshold(change_pct, levels)
        if not triggered:
            logger.info("基金 %s(%s) 涨跌幅 %.2f%% 未触发门限", fund_name, code, change_pct)
            continue

        level_name = triggered["name"]
        logger.info(
            "基金 %s(%s) 涨跌幅 %.2f%% 触发 [%s] 门限",
            fund_name, code, change_pct, level_name,
        )

        if is_in_cooldown(code, level_name, cooldown_minutes, db):
            continue

        title, body = format_notification(
            fund_name, code, level_name, change_pct, price, prev_close,
        )
        channels = []

        if pushdeer_key:
            if send_pushdeer(pushdeer_key, title, body):
                channels.append("pushdeer")

        if fcm_enabled:
            data = {
                "fund_code": code,
                "fund_name": fund_name,
                "level": level_name,
                "change_pct": str(change_pct),
            }
            if send_fcm(FCM_TOPIC, title, body, data):
                channels.append("fcm")

        if not channels:
            logger.warning(
                "基金 %s [%s] 触发 %s 门限但无可用推送通道",
                fund_name, code, level_name,
            )

        if channels:
            record_notification(
                fund_code=code,
                fund_name=fund_name,
                level_name=level_name,
                change_pct=change_pct,
                price=price,
                channels=channels,
                db=db,
            )

    save_snapshot(db, quotes)
    logger.info("=== ETF 监控 Worker 完成 ===")


if __name__ == "__main__":
    run()
