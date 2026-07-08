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
    # The primary trigger is an external scheduler calling workflow_dispatch.
    # The cron entries are best-effort backups and must all fall inside the
    # Beijing 10:00-15:00 monitor window (main.py skips runs outside it).
    earliest = 10 * 60
    latest = 15 * 60

    scheduled = _scheduled_beijing_minutes()

    assert scheduled, "monitor workflow should have scheduled triggers"
    assert all(earliest <= minute < latest for minute in scheduled)


def test_monitor_schedule_avoids_busy_ten_minute_boundaries():
    scheduled = _scheduled_beijing_minutes()

    assert all(minute % 10 != 0 for minute in scheduled)
