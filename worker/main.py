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


def get_monitor_window_status() -> dict:
    """Return current Beijing monitor-window status and skip reason."""
    now = datetime.now(TZ_BEIJING)
    status = {
        "current_time_bj": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "is_workday": chinese_calendar.is_workday(now.date()),
        "in_monitor_window": False,
        "skip_reason": None,
    }

    if not status["is_workday"]:
        status["skip_reason"] = "non_workday"
        return status

    hour, minute = now.hour, now.minute
    current_minutes = hour * 60 + minute
    start_minutes = 10 * 60       # 10:00
    end_minutes = 15 * 60         # 15:00, allows delayed GitHub cron runs

    if not (start_minutes <= current_minutes <= end_minutes):
        status["skip_reason"] = "outside_monitor_window"
        return status

    status["in_monitor_window"] = True
    return status


def is_trading_time() -> bool:
    """Check if current time is within A-share trading hours on a workday."""
    status = get_monitor_window_status()
    if not status["is_workday"]:
        logger.info("今日非工作日，跳过监控")
        return False
    if not status["in_monitor_window"]:
        now = datetime.fromisoformat(status["current_time_bj"])
        logger.info("当前时间 %02d:%02d 不在监控时段 (10:00~15:00)，跳过", now.hour, now.minute)
        return False
    return True


def build_run_status(now: datetime | None = None) -> dict:
    """Build the initial status document for one worker invocation."""
    now = now or datetime.now(TZ_BEIJING)
    run_id = os.environ.get("GITHUB_RUN_ID") or now.strftime("%Y%m%d%H%M%S")
    return {
        "run_id": run_id,
        "date": now.strftime("%Y-%m-%d"),
        "started_at": now.isoformat(),
        "finished_at": None,
        "github_run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
        "github_sha": os.environ.get("GITHUB_SHA", ""),
        "github_workflow": os.environ.get("GITHUB_WORKFLOW", ""),
        "final_status": "running",
        "skip_reason": None,
        "quotes_count": 0,
        "triggered_count": 0,
        "cooldown_count": 0,
        "notifications_recorded": 0,
        "delivery_failures": [],
    }


def record_run_status(db, status: dict) -> None:
    """Persist worker status so missed alerts have a visible reason chain."""
    try:
        finished = datetime.now(TZ_BEIJING)
        payload = dict(status)
        payload["finished_at"] = finished.isoformat()
        db.collection("run_status").document(payload["run_id"]).set(payload, merge=True)
        logger.info("运行状态已保存: %s %s", payload["run_id"], payload["final_status"])
    except Exception:
        logger.exception("保存运行状态失败")


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

    db = init_firebase()
    status = build_run_status()

    try:
        window_status = get_monitor_window_status()
        status.update(window_status)
        if not window_status["in_monitor_window"]:
            if window_status["skip_reason"] == "non_workday":
                logger.info("今日非工作日，跳过监控")
            else:
                now = datetime.fromisoformat(window_status["current_time_bj"])
                logger.info("当前时间 %02d:%02d 不在监控时段 (10:00~15:00)，跳过", now.hour, now.minute)
            status["final_status"] = "skipped"
            return

        config = load_config(db)

        funds = config.get("funds", [])
        levels = config.get("levels", [])
        cooldown_minutes = config.get("cooldown_minutes", 60)
        pushdeer_key = config.get("pushdeer_key", "") or os.environ.get("PUSHDEER_KEY", "")
        fcm_enabled = config.get("fcm_enabled", True)

        enabled_funds = [f for f in funds if f.get("enabled", True)]
        if not enabled_funds:
            logger.warning("没有启用的基金，跳过")
            status["final_status"] = "skipped"
            status["skip_reason"] = "no_enabled_funds"
            return

        fund_codes = [f["code"] for f in enabled_funds]
        quotes = fetch_etf_quotes(fund_codes)
        status["quotes_count"] = len(quotes or {})

        if not quotes:
            logger.warning("未获取到任何行情数据")
            status["final_status"] = "failed"
            status["skip_reason"] = "no_quotes"
            raise RuntimeError("未获取到任何行情数据")

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

            status["triggered_count"] += 1
            level_name = triggered["name"]
            logger.info(
                "基金 %s(%s) 涨跌幅 %.2f%% 触发 [%s] 门限",
                fund_name, code, change_pct, level_name,
            )

            if is_in_cooldown(code, level_name, cooldown_minutes, db):
                status["cooldown_count"] += 1
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
                failure = {
                    "fund_code": code,
                    "fund_name": fund_name,
                    "level": level_name,
                    "change_pct": change_pct,
                }
                status["delivery_failures"].append(failure)
                logger.warning(
                    "基金 %s [%s] 触发 %s 门限但无推送通道成功",
                    fund_name, code, level_name,
                )
                continue

            record_notification(
                fund_code=code,
                fund_name=fund_name,
                level_name=level_name,
                change_pct=change_pct,
                price=price,
                channels=channels,
                db=db,
            )
            status["notifications_recorded"] += 1

        save_snapshot(db, quotes)

        if status["delivery_failures"]:
            status["final_status"] = "failed"
            raise RuntimeError(f"推送失败: {len(status['delivery_failures'])} 个触发信号未送达")

        status["final_status"] = "completed"
        logger.info("=== ETF 监控 Worker 完成 ===")
    except Exception as exc:
        status["final_status"] = "failed"
        status["error"] = str(exc)
        raise
    finally:
        record_run_status(db, status)


if __name__ == "__main__":
    run()
