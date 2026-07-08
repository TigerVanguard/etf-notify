import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import loop

TZ_BEIJING = timezone(timedelta(hours=8))

LOOP_SETTINGS = {
    "interval": 600,
    "start_hour": 10,
    "start_minute": 0,
    "end_hour": 15,
    "end_minute": 0,
}


def test_seconds_until():
    now = datetime(2026, 6, 9, 14, 45, 0, tzinfo=TZ_BEIJING)

    assert loop.seconds_until(now, 15, 0) == 15 * 60


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
    mock_settings.return_value = dict(LOOP_SETTINGS)
    mock_datetime.now.side_effect = [
        datetime(2026, 6, 9, 14, 40, 0, tzinfo=TZ_BEIJING),   # startup
        datetime(2026, 6, 9, 14, 40, 1, tzinfo=TZ_BEIJING),   # pre-loop window check
        datetime(2026, 6, 9, 14, 40, 2, tzinfo=TZ_BEIJING),   # iter 1 start
        datetime(2026, 6, 9, 14, 40, 3, tzinfo=TZ_BEIJING),   # iter 1 end check
        datetime(2026, 6, 9, 14, 50, 3, tzinfo=TZ_BEIJING),   # iter 2 start
        datetime(2026, 6, 9, 14, 50, 4, tzinfo=TZ_BEIJING),   # iter 2 end check
        datetime(2026, 6, 9, 14, 59, 4, tzinfo=TZ_BEIJING),   # iter 3 start
        datetime(2026, 6, 9, 15, 0, 5, tzinfo=TZ_BEIJING),    # iter 3 end check -> stop
    ]

    loop.run_loop()

    assert mock_run.call_count == 3
    assert mock_sleep.call_count == 2


@patch("loop.time.sleep")
@patch("loop.run")
@patch("loop.datetime")
@patch("loop.get_loop_settings")
@patch("loop.chinese_calendar.is_workday")
def test_run_loop_started_after_end_exits_without_running(
    mock_workday, mock_settings, mock_datetime, mock_run, mock_sleep
):
    mock_workday.return_value = True
    mock_settings.return_value = dict(LOOP_SETTINGS)
    mock_datetime.now.side_effect = [
        datetime(2026, 6, 9, 17, 42, 0, tzinfo=TZ_BEIJING),
        datetime(2026, 6, 9, 17, 42, 1, tzinfo=TZ_BEIJING),
    ]

    loop.run_loop()

    mock_run.assert_not_called()
    mock_sleep.assert_not_called()


@patch("loop.time.sleep")
@patch("loop.run")
@patch("loop.datetime")
@patch("loop.get_loop_settings")
@patch("loop.chinese_calendar.is_workday")
def test_run_loop_survives_transient_run_error(
    mock_workday, mock_settings, mock_datetime, mock_run, mock_sleep
):
    """One failed iteration must not kill the loop for the rest of the day."""
    mock_workday.return_value = True
    mock_settings.return_value = dict(LOOP_SETTINGS)
    mock_run.side_effect = [RuntimeError("transient AkShare failure"), None]
    mock_datetime.now.side_effect = [
        datetime(2026, 6, 9, 14, 40, 0, tzinfo=TZ_BEIJING),   # startup
        datetime(2026, 6, 9, 14, 40, 1, tzinfo=TZ_BEIJING),   # pre-loop window check
        datetime(2026, 6, 9, 14, 40, 2, tzinfo=TZ_BEIJING),   # iter 1 start (raises)
        datetime(2026, 6, 9, 14, 40, 3, tzinfo=TZ_BEIJING),   # iter 1 end check
        datetime(2026, 6, 9, 14, 50, 3, tzinfo=TZ_BEIJING),   # iter 2 start (ok)
        datetime(2026, 6, 9, 15, 0, 4, tzinfo=TZ_BEIJING),    # iter 2 end check -> stop
    ]

    loop.run_loop()

    assert mock_run.call_count == 2
    assert mock_sleep.call_count == 1


@patch("loop.time.sleep")
@patch("loop.run")
@patch("loop.datetime")
@patch("loop.get_loop_settings")
@patch("loop.chinese_calendar.is_workday")
def test_run_loop_keyboard_interrupt_propagates(
    mock_workday, mock_settings, mock_datetime, mock_run, mock_sleep
):
    mock_workday.return_value = True
    mock_settings.return_value = dict(LOOP_SETTINGS)
    mock_run.side_effect = KeyboardInterrupt()
    mock_datetime.now.side_effect = [
        datetime(2026, 6, 9, 14, 40, 0, tzinfo=TZ_BEIJING),
        datetime(2026, 6, 9, 14, 40, 1, tzinfo=TZ_BEIJING),
        datetime(2026, 6, 9, 14, 40, 2, tzinfo=TZ_BEIJING),
    ]

    with pytest.raises(KeyboardInterrupt):
        loop.run_loop()

    mock_run.assert_called_once()
    mock_sleep.assert_not_called()
