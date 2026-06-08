import logging
import os
from datetime import datetime, timedelta, timezone

from config import init_firebase, load_config
from notifier import send_pushdeer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

TZ_BEIJING = timezone(timedelta(hours=8))
SUCCESS_STATUS = "completed"


def today_bj() -> str:
    """Return today's date in Beijing time."""
    return datetime.now(TZ_BEIJING).strftime("%Y-%m-%d")


def load_today_runs(db, date_str: str) -> list[dict]:
    """Load all run_status documents for one date without requiring composite indexes."""
    docs = db.collection("run_status").where("date", "==", date_str).stream()
    runs = [doc.to_dict() for doc in docs]
    return sorted(
        runs,
        key=lambda run: run.get("finished_at") or run.get("started_at") or "",
    )


def evaluate_today_health(runs: list[dict]) -> dict:
    """Evaluate whether today's monitor had at least one successful in-window run."""
    successful_runs = [
        run for run in runs
        if run.get("in_monitor_window") is True and run.get("final_status") == SUCCESS_STATUS
    ]
    failed_runs = [run for run in runs if run.get("final_status") == "failed"]
    skipped_runs = [run for run in runs if run.get("final_status") == "skipped"]

    return {
        "healthy": bool(successful_runs),
        "total_runs": len(runs),
        "successful_runs": len(successful_runs),
        "failed_runs": len(failed_runs),
        "skipped_runs": len(skipped_runs),
        "last_status": runs[-1].get("final_status") if runs else "missing",
        "last_error": runs[-1].get("error", "") if runs else "",
    }


def build_alert(date_str: str, health: dict) -> tuple[str, str]:
    """Build PushDeer alert text for an unhealthy monitor day."""
    title = "[系统告警] ETF Notify 今日监控异常"
    body = (
        f"日期: {date_str}\n"
        f"今日运行次数: {health['total_runs']}\n"
        f"成功运行次数: {health['successful_runs']}\n"
        f"失败运行次数: {health['failed_runs']}\n"
        f"跳过运行次数: {health['skipped_runs']}\n"
        f"最后状态: {health['last_status']}\n"
    )
    if health.get("last_error"):
        body += f"最后错误: {health['last_error']}\n"
    body += "请检查 GitHub Actions 的 ETF Monitor 工作流和 Firestore run_status。"
    return title, body


def run_health_check() -> dict:
    """Check today's monitor status and alert via PushDeer if no successful run exists."""
    date_str = today_bj()
    db = init_firebase()
    runs = load_today_runs(db, date_str)
    health = evaluate_today_health(runs)

    logger.info("今日监控健康检查: %s", health)
    if health["healthy"]:
        return health

    config = load_config(db)
    pushdeer_key = config.get("pushdeer_key", "") or os.environ.get("PUSHDEER_KEY", "")
    if not pushdeer_key:
        raise RuntimeError("今日监控异常，且 PUSHDEER_KEY 未配置，无法发送系统告警")

    title, body = build_alert(date_str, health)
    if not send_pushdeer(pushdeer_key, title, body):
        raise RuntimeError("今日监控异常，系统告警 PushDeer 发送失败")

    return health


if __name__ == "__main__":
    run_health_check()
