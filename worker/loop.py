import logging
import os
import time
from datetime import datetime, timedelta, timezone

import chinese_calendar

from main import TZ_BEIJING, run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_SECONDS = 10 * 60
DEFAULT_START_HOUR = 10
DEFAULT_START_MINUTE = 0
DEFAULT_END_HOUR = 15
DEFAULT_END_MINUTE = 0


def get_loop_settings() -> dict:
    """Load loop settings from env so tests can run quickly."""
    return {
        "interval": int(os.environ.get("MONITOR_LOOP_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS)),
        "start_hour": int(os.environ.get("MONITOR_LOOP_START_HOUR", DEFAULT_START_HOUR)),
        "start_minute": int(os.environ.get("MONITOR_LOOP_START_MINUTE", DEFAULT_START_MINUTE)),
        "end_hour": int(os.environ.get("MONITOR_LOOP_END_HOUR", DEFAULT_END_HOUR)),
        "end_minute": int(os.environ.get("MONITOR_LOOP_END_MINUTE", DEFAULT_END_MINUTE)),
    }


def seconds_until(now: datetime, hour: int, minute: int) -> float:
    """Return seconds from now to a given time today."""
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return (target - now).total_seconds()


def should_continue_loop(now: datetime, end_hour: int, end_minute: int) -> bool:
    """Return whether another scheduled in-window iteration can run today."""
    if not chinese_calendar.is_workday(now.date()):
        return False
    return seconds_until(now, end_hour, end_minute) > 0


def run_loop() -> None:
    """Run the monitor repeatedly inside one GitHub Actions job.

    If started before trading hours (e.g. due to early cron trigger),
    waits until the trading window opens before beginning the loop.
    """
    settings = get_loop_settings()
    interval_seconds = settings["interval"]
    start_hour, start_minute = settings["start_hour"], settings["start_minute"]
    end_hour, end_minute = settings["end_hour"], settings["end_minute"]

    logger.info(
        "=== ETF 监控循环启动: interval=%ss window=%02d:%02d~%02d:%02d ===",
        interval_seconds, start_hour, start_minute, end_hour, end_minute,
    )

    now = datetime.now(TZ_BEIJING)

    if not chinese_calendar.is_workday(now.date()):
        logger.info("今日非工作日，退出")
        return

    wait_seconds = seconds_until(now, start_hour, start_minute)
    if wait_seconds > 0:
        logger.info("距离交易时间还有 %.0f 秒，等待中...", wait_seconds)
        time.sleep(wait_seconds)

    if not should_continue_loop(datetime.now(TZ_BEIJING), end_hour, end_minute):
        logger.info("已过交易时间，退出")
        return

    iteration = 0
    while True:
        iteration += 1
        now = datetime.now(TZ_BEIJING)
        logger.info("开始第 %d 轮监控: %s", iteration, now.isoformat())
        try:
            run()
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            # One transient failure must not kill the rest of the day's loop.
            logger.exception("第 %d 轮监控执行失败，继续下一轮", iteration)

        now = datetime.now(TZ_BEIJING)
        remaining = seconds_until(now, end_hour, end_minute)
        if not should_continue_loop(now, end_hour, end_minute):
            logger.info("监控循环结束: 当前时间 %s", now.isoformat())
            break

        sleep_seconds = min(interval_seconds, remaining)
        logger.info("第 %d 轮完成，%.0f 秒后进入下一轮", iteration, sleep_seconds)
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    run_loop()
