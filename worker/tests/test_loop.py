import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import loop

TZ_BEIJING = timezone(timedelta(hours=8))


def test_seconds_until_end():
    now = datetime(2026, 6, 9, 14, 45, 0, tzinfo=TZ_BEIJING)

    assert loop.seconds_until_end(now, 15, 0) == 15 * 60


@patch("loop.chinese_calendar.is_workday")
def test_should_continue_loop_requires_workday(mock_workday):
    mock_workday.return_value = False
    now = datetime(2026, 6, 9, 14, 0, 0, tzinfo=TZ_BEIJING)

    assert loop.should_continue_loop(now, 15, 0) is False


@patch("loop.chinese_calendar.is_workday")
def test_should_continue_loop_stops_after_end(mock_workday):
    mock_workday.return_value = True
    now = datetime(2026, 6, 9, 15, 1, 0, tzinfo=TZ_BEIJING)

    assert loop.should_continue_loop(now, 15, 0) is False


@patch("loop.time.sleep")
@patch("loop.run")
@patch("loop.datetime")
@patch("loop.get_loop_settings")
@patch("loop.chinese_calendar.is_workday")
def test_run_loop_runs_multiple_iterations_until_end(
    mock_workday, mock_settings, mock_datetime, mock_run, mock_sleep
):
    mock_workday.return_value = True
    mock_settings.return_value = (600, 15, 0)
    mock_datetime.now.side_effect = [
        datetime(2026, 6, 9, 14, 40, 0, tzinfo=TZ_BEIJING),
        datetime(2026, 6, 9, 14, 40, 1, tzinfo=TZ_BEIJING),
        datetime(2026, 6, 9, 14, 50, 1, tzinfo=TZ_BEIJING),
        datetime(2026, 6, 9, 14, 50, 2, tzinfo=TZ_BEIJING),
        datetime(2026, 6, 9, 15, 0, 0, tzinfo=TZ_BEIJING),
        datetime(2026, 6, 9, 15, 0, 1, tzinfo=TZ_BEIJING),
    ]

    loop.run_loop()

    assert mock_run.call_count == 3
    assert mock_sleep.call_count == 2


@patch("loop.time.sleep")
@patch("loop.run")
@patch("loop.datetime")
@patch("loop.get_loop_settings")
@patch("loop.chinese_calendar.is_workday")
def test_run_loop_delayed_after_end_records_one_skip(
    mock_workday, mock_settings, mock_datetime, mock_run, mock_sleep
):
    mock_workday.return_value = True
    mock_settings.return_value = (600, 15, 0)
    mock_datetime.now.side_effect = [
        datetime(2026, 6, 9, 17, 42, 0, tzinfo=TZ_BEIJING),
        datetime(2026, 6, 9, 17, 42, 1, tzinfo=TZ_BEIJING),
    ]

    loop.run_loop()

    mock_run.assert_called_once()
    mock_sleep.assert_not_called()
