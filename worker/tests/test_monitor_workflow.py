from pathlib import Path
import re


WORKFLOW_PATH = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "monitor.yml"


def _expand_field(field: str, *, minimum: int, maximum: int) -> set[int]:
    values: set[int] = set()
    for part in field.split(","):
        part = part.strip()
        if part == "*":
            values.update(range(minimum, maximum + 1))
        elif part.startswith("*/"):
            step = int(part[2:])
            values.update(range(minimum, maximum + 1, step))
        elif "-" in part:
            start, end = (int(piece) for piece in part.split("-", 1))
            values.update(range(start, end + 1))
        else:
            values.add(int(part))
    return values


def _scheduled_beijing_minutes() -> list[int]:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    crons = re.findall(r"cron:\s*'([^']+)'", text)
    assert crons, "monitor workflow should define at least one cron schedule"

    scheduled: list[int] = []
    for cron in crons:
        minute_field, hour_field, *_ = cron.split()
        minutes = _expand_field(minute_field, minimum=0, maximum=59)
        hours = _expand_field(hour_field, minimum=0, maximum=23)
        for hour in hours:
            for minute in minutes:
                beijing_hour = (hour + 8) % 24
                scheduled.append(beijing_hour * 60 + minute)
    return sorted(scheduled)


def test_monitor_schedule_only_covers_trading_window():
    # The workflow runs loop.py, which waits until the 10:00 window opens if
    # started early and exits immediately if trading is over. The primary
    # trigger fires at Beijing 09:45 (15 min before open) with hourly backups,
    # so triggers may start up to 15 minutes before the window but must never
    # fire after the 15:00 window end.
    earliest = 9 * 60 + 45
    latest = 15 * 60

    scheduled = _scheduled_beijing_minutes()

    assert scheduled, "monitor workflow should have scheduled triggers"
    assert all(earliest <= minute < latest for minute in scheduled)


def test_monitor_schedule_avoids_busy_ten_minute_boundaries():
    scheduled = _scheduled_beijing_minutes()

    assert all(minute % 10 != 0 for minute in scheduled)
