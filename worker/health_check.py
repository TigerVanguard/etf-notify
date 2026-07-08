import logging
import os
from datetime import datetime, timedelta, timezone

import chinese_calendar

from config import init_firebase
from notifier import send_pushdeer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

TZ_BEIJING = timezone(timedelta(hours=8))
SUCCESS_STATUS = "completed"
# The external scheduler triggers ~27 runs per trading day (every 10 min,
# 10:00-14:30). Below this many successes, coverage has meaningful gaps.
DEFAULT_MIN_SUCCESS_RUNS = 20


def min_success_runs() -> int:
    """Read the required in-window success count from env, with a default."""
    raw = os.environ.get("HEALTH_MIN_SUCCESS_RUNS", "")
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_MIN_SUCCESS_RUNS


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


def evaluate_today_health(runs: list[dict], required_runs: int | None = None) -> dict:
    """Evaluate whether today's monitor had enough successful in-window runs.

    A single success used to count as healthy, which hid multi-hour coverage
    gaps. Now the day is healthy only if at least `required_runs` in-window
    runs completed successfully.
    """
    required = required_runs if required_runs is not None else min_success_runs()
    successful_runs = [
        run for run in runs
        if run.get("in_monitor_window") is True and run.get("final_status") == SUCCESS_STATUS
    ]
    failed_runs = [run for run in runs if run.get("final_status") == "failed"]
    skipped_runs = [run for run in runs if run.get("final_status") == "skipped"]

    return {
        "healthy": len(successful_runs) >= required,
        "required_runs": required,
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
        f"要求成功次数: {health.get('required_runs', DEFAULT_MIN_SUCCESS_RUNS)}\n"
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
    """Check today's monitor coverage and alert via PushDeer when it falls short."""
    now_bj = datetime.now(TZ_BEIJING)
    if not chinese_calendar.is_workday(now_bj.date()):
        logger.info("今日非工作日，无需健康检查")
        return {"healthy": True, "skipped": "non_workday"}

    date_str = today_bj()
    db = init_firebase()
    runs = load_today_runs(db, date_str)
    health = evaluate_today_health(runs)

    logger.info("今日监控健康检查: %s", health)
    if health["healthy"]:
        return health

    # Firestore is world-readable, so the key must only come from env (GitHub Secrets).
    pushdeer_key = os.environ.get("PUSHDEER_KEY", "")
    if not pushdeer_key:
        raise RuntimeError("今日监控异常，且 PUSHDEER_KEY 未配置，无法发送系统告警")

    title, body = build_alert(date_str, health)
    if not send_pushdeer(pushdeer_key, title, body):
        raise RuntimeError("今日监控异常，系统告警 PushDeer 发送失败")

    return health


if __name__ == "__main__":
    run_health_check()
