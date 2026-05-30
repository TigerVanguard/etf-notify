import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch, MagicMock, call
from datetime import datetime, timedelta, timezone
import pytest

TZ_BEIJING = timezone(timedelta(hours=8))

DEFAULT_CONFIG = {
    "funds": [
        {"code": "159941", "name": "纳指ETF", "index": "纳斯达克100", "enabled": True},
    ],
    "levels": [
        {"name": "提醒", "threshold": -1.0, "color": "yellow"},
        {"name": "警告", "threshold": -2.0, "color": "orange"},
        {"name": "紧急", "threshold": -3.0, "color": "red"},
    ],
    "cooldown_minutes": 60,
    "pushdeer_key": "PDU_test",
    "fcm_enabled": True,
}


def _make_quote(code, name, price, prev_close, change_pct):
    return {
        code: {
            "name": name,
            "price": price,
            "prev_close": prev_close,
            "change_pct": change_pct,
            "high": price + 0.01,
            "low": price - 0.01,
            "volume": 1000000,
        }
    }


class TestTradingTimeWeekend:
    """TC-05: Mock weekend, verify run() returns early without doing anything."""

    @patch("main.init_firebase")
    @patch("main.chinese_calendar.is_workday")
    @patch("main.datetime")
    def test_weekend_skips_execution(self, mock_dt, mock_workday, mock_firebase):
        sunday = datetime(2026, 5, 31, 11, 0, 0, tzinfo=TZ_BEIJING)
        mock_dt.now.return_value = sunday
        mock_workday.return_value = False

        from main import run
        run()

        mock_firebase.assert_not_called()

    @patch("main.init_firebase")
    @patch("main.chinese_calendar.is_workday")
    @patch("main.datetime")
    def test_saturday_skips_execution(self, mock_dt, mock_workday, mock_firebase):
        saturday = datetime(2026, 5, 30, 11, 0, 0, tzinfo=TZ_BEIJING)
        mock_dt.now.return_value = saturday
        mock_workday.return_value = False

        from main import run
        run()

        mock_firebase.assert_not_called()


class TestTradingTimeHoliday:
    """TC-05: Mock Chinese holiday (e.g. National Day), verify no execution."""

    @patch("main.init_firebase")
    @patch("main.chinese_calendar.is_workday")
    @patch("main.datetime")
    def test_national_day_skips(self, mock_dt, mock_workday, mock_firebase):
        national_day = datetime(2026, 10, 1, 11, 0, 0, tzinfo=TZ_BEIJING)
        mock_dt.now.return_value = national_day
        mock_workday.return_value = False

        from main import run
        run()

        mock_firebase.assert_not_called()


class TestNormalTrigger:
    """TC-01: Trading time + drop -3.5% + no cooldown → notifications sent."""

    @patch("main.save_snapshot")
    @patch("main.record_notification")
    @patch("main.send_fcm")
    @patch("main.send_pushdeer")
    @patch("main.is_in_cooldown")
    @patch("main.fetch_etf_quotes")
    @patch("main.load_config")
    @patch("main.init_firebase")
    @patch("main.is_trading_time")
    def test_urgent_trigger_sends_both_channels(
        self, mock_trading, mock_firebase, mock_config, mock_quotes,
        mock_cooldown, mock_pushdeer, mock_fcm, mock_record, mock_snapshot
    ):
        mock_trading.return_value = True
        mock_firebase.return_value = MagicMock()
        mock_config.return_value = dict(DEFAULT_CONFIG)
        mock_quotes.return_value = _make_quote(
            "159941", "纳指ETF", 1.856, 1.917, -3.5
        )
        mock_cooldown.return_value = False
        mock_pushdeer.return_value = True
        mock_fcm.return_value = True

        from main import run
        run()

        mock_pushdeer.assert_called_once()
        mock_fcm.assert_called_once()
        mock_record.assert_called_once()

        record_kwargs = mock_record.call_args[1]
        assert record_kwargs["fund_code"] == "159941"
        assert record_kwargs["level_name"] == "紧急"
        assert record_kwargs["change_pct"] == -3.5
        assert "pushdeer" in record_kwargs["channels"]
        assert "fcm" in record_kwargs["channels"]


class TestMultiLevelTrigger:
    """TC-02: Two consecutive runs with escalating drops both notify."""

    @patch("main.save_snapshot")
    @patch("main.record_notification")
    @patch("main.send_fcm")
    @patch("main.send_pushdeer")
    @patch("main.is_in_cooldown")
    @patch("main.fetch_etf_quotes")
    @patch("main.load_config")
    @patch("main.init_firebase")
    @patch("main.is_trading_time")
    def test_escalating_levels_both_notify(
        self, mock_trading, mock_firebase, mock_config, mock_quotes,
        mock_cooldown, mock_pushdeer, mock_fcm, mock_record, mock_snapshot
    ):
        mock_trading.return_value = True
        mock_firebase.return_value = MagicMock()
        mock_config.return_value = dict(DEFAULT_CONFIG)
        mock_cooldown.return_value = False
        mock_pushdeer.return_value = True
        mock_fcm.return_value = True

        # First run: -1.5% triggers "提醒"
        mock_quotes.return_value = _make_quote(
            "159941", "纳指ETF", 1.89, 1.917, -1.5
        )
        from main import run
        run()

        first_record_call = mock_record.call_args
        assert first_record_call[1]["level_name"] == "提醒"

        mock_record.reset_mock()
        mock_pushdeer.reset_mock()
        mock_fcm.reset_mock()

        # Second run: -2.5% triggers "警告"
        mock_quotes.return_value = _make_quote(
            "159941", "纳指ETF", 1.869, 1.917, -2.5
        )
        run()

        second_record_call = mock_record.call_args
        assert second_record_call[1]["level_name"] == "警告"
        mock_pushdeer.assert_called_once()
        mock_fcm.assert_called_once()


class TestConfigChange:
    """TC-08: Different Firestore config (modified thresholds) is respected."""

    @patch("main.save_snapshot")
    @patch("main.record_notification")
    @patch("main.send_fcm")
    @patch("main.send_pushdeer")
    @patch("main.is_in_cooldown")
    @patch("main.fetch_etf_quotes")
    @patch("main.load_config")
    @patch("main.init_firebase")
    @patch("main.is_trading_time")
    def test_custom_threshold_respected(
        self, mock_trading, mock_firebase, mock_config, mock_quotes,
        mock_cooldown, mock_pushdeer, mock_fcm, mock_record, mock_snapshot
    ):
        mock_trading.return_value = True
        mock_firebase.return_value = MagicMock()

        custom_config = dict(DEFAULT_CONFIG)
        custom_config["levels"] = [
            {"name": "自定义提醒", "threshold": -0.5, "color": "yellow"},
            {"name": "自定义警告", "threshold": -1.0, "color": "orange"},
        ]
        mock_config.return_value = custom_config

        mock_quotes.return_value = _make_quote(
            "159941", "纳指ETF", 1.9, 1.917, -0.8
        )
        mock_cooldown.return_value = False
        mock_pushdeer.return_value = True
        mock_fcm.return_value = True

        from main import run
        run()

        mock_pushdeer.assert_called_once()
        record_kwargs = mock_record.call_args[1]
        assert record_kwargs["level_name"] == "自定义提醒"

    @patch("main.save_snapshot")
    @patch("main.record_notification")
    @patch("main.send_fcm")
    @patch("main.send_pushdeer")
    @patch("main.is_in_cooldown")
    @patch("main.fetch_etf_quotes")
    @patch("main.load_config")
    @patch("main.init_firebase")
    @patch("main.is_trading_time")
    def test_higher_threshold_no_trigger(
        self, mock_trading, mock_firebase, mock_config, mock_quotes,
        mock_cooldown, mock_pushdeer, mock_fcm, mock_record, mock_snapshot
    ):
        mock_trading.return_value = True
        mock_firebase.return_value = MagicMock()

        strict_config = dict(DEFAULT_CONFIG)
        strict_config["levels"] = [
            {"name": "紧急", "threshold": -5.0, "color": "red"},
        ]
        mock_config.return_value = strict_config

        mock_quotes.return_value = _make_quote(
            "159941", "纳指ETF", 1.856, 1.917, -3.0
        )
        mock_cooldown.return_value = False

        from main import run
        run()

        mock_pushdeer.assert_not_called()
        mock_fcm.assert_not_called()
        mock_record.assert_not_called()


class TestOutsideTradingHours:
    """Test that run() does nothing outside 10:00-14:30."""

    @patch("main.init_firebase")
    @patch("main.chinese_calendar.is_workday")
    @patch("main.datetime")
    def test_early_morning_skips(self, mock_dt, mock_workday, mock_firebase):
        mock_dt.now.return_value = datetime(2026, 5, 28, 8, 0, 0, tzinfo=TZ_BEIJING)
        mock_workday.return_value = True

        from main import run
        run()

        mock_firebase.assert_not_called()

    @patch("main.init_firebase")
    @patch("main.chinese_calendar.is_workday")
    @patch("main.datetime")
    def test_evening_skips(self, mock_dt, mock_workday, mock_firebase):
        mock_dt.now.return_value = datetime(2026, 5, 28, 16, 0, 0, tzinfo=TZ_BEIJING)
        mock_workday.return_value = True

        from main import run
        run()

        mock_firebase.assert_not_called()
