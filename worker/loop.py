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
DEFAULT_END_HOUR = 15
DEFAULT_END_MINUTE = 0


def get_loop_settings() -> tuple[int, int, int]:
    """Load loop settings from env so tests can run quickly."""
    interval = int(os.environ.get("MONITOR_LOOP_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS))
    end_hour = int(os.environ.get("MONITOR_LOOP_END_HOUR", DEFAULT_END_HOUR))
    end_minute = int(os.environ.get("MONITOR_LOOP_END_MINUTE", DEFAULT_END_MINUTE))
    return interval, end_hour, end_minute


def seconds_until_end(now: datetime, end_hour: int, end_minute: int) -> float:
    """Return seconds from now to today's loop end time."""
    end_at = now.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
    return (end_at - now).total_seconds()


def should_continue_loop(now: datetime, end_hour: int, end_minute: int) -> bool:
    """Return whether another scheduled in-window iteration can run today."""
    if not chinese_calendar.is_workday(now.date()):
        return False
    return seconds_until_end(now, end_hour, end_minute) > 0


def run_loop() -> None:
    """Run the monitor repeatedly inside one GitHub Actions job."""
    interval_seconds, end_hour, end_minute = get_loop_settings()
    logger.info(
        "=== ETF 监控循环启动: interval=%ss end=%02d:%02d ===",
        interval_seconds, end_hour, end_minute,
    )

    iteration = 0
    while True:
        iteration += 1
        now = datetime.now(TZ_BEIJING)
        logger.info("开始第 %d 轮监控: %s", iteration, now.isoformat())
        run()

        now = datetime.now(TZ_BEIJING)
        remaining = seconds_until_end(now, end_hour, end_minute)
        if not should_continue_loop(now, end_hour, end_minute):
            logger.info("监控循环结束: 当前时间 %s，剩余 %.0f 秒", now.isoformat(), remaining)
            break

        sleep_seconds = min(interval_seconds, remaining)
        logger.info("第 %d 轮完成，%.0f 秒后进入下一轮", iteration, sleep_seconds)
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    run_loop()
