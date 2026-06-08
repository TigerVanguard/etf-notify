import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from health_check import build_alert, evaluate_today_health, run_health_check


class FakeDoc:
    def __init__(self, data):
        self._data = data

    def to_dict(self):
        return self._data


def test_evaluate_today_health_requires_successful_in_window_run():
    health = evaluate_today_health([
        {"final_status": "skipped", "in_monitor_window": False},
        {"final_status": "failed", "in_monitor_window": True, "error": "推送失败"},
    ])

    assert health["healthy"] is False
    assert health["failed_runs"] == 1
    assert health["last_status"] == "failed"


def test_evaluate_today_health_passes_on_completed_in_window_run():
    health = evaluate_today_health([
        {"final_status": "completed", "in_monitor_window": True},
    ])

    assert health["healthy"] is True
    assert health["successful_runs"] == 1


def test_build_alert_contains_reason_chain():
    title, body = build_alert("2026-06-08", {
        "total_runs": 2,
        "successful_runs": 0,
        "failed_runs": 1,
        "skipped_runs": 1,
        "last_status": "failed",
        "last_error": "推送失败",
    })

    assert "系统告警" in title
    assert "成功运行次数: 0" in body
    assert "最后错误: 推送失败" in body


@patch("health_check.send_pushdeer")
@patch("health_check.load_config")
@patch("health_check.init_firebase")
@patch("health_check.today_bj")
def test_run_health_check_sends_alert_when_no_successful_run(
    mock_today, mock_firebase, mock_config, mock_pushdeer
):
    mock_today.return_value = "2026-06-08"
    db = MagicMock()
    db.collection.return_value.where.return_value.stream.return_value = [
        FakeDoc({"date": "2026-06-08", "final_status": "failed", "in_monitor_window": True})
    ]
    mock_firebase.return_value = db
    mock_config.return_value = {"pushdeer_key": "PDU_test"}
    mock_pushdeer.return_value = True

    health = run_health_check()

    assert health["healthy"] is False
    mock_pushdeer.assert_called_once()


@patch("health_check.send_pushdeer")
@patch("health_check.init_firebase")
@patch("health_check.today_bj")
def test_run_health_check_does_not_alert_when_successful(
    mock_today, mock_firebase, mock_pushdeer
):
    mock_today.return_value = "2026-06-08"
    db = MagicMock()
    db.collection.return_value.where.return_value.stream.return_value = [
        FakeDoc({"date": "2026-06-08", "final_status": "completed", "in_monitor_window": True})
    ]
    mock_firebase.return_value = db

    health = run_health_check()

    assert health["healthy"] is True
    mock_pushdeer.assert_not_called()


@patch("health_check.load_config")
@patch("health_check.init_firebase")
@patch("health_check.today_bj")
def test_run_health_check_fails_without_push_key(mock_today, mock_firebase, mock_config):
    mock_today.return_value = "2026-06-08"
    db = MagicMock()
    db.collection.return_value.where.return_value.stream.return_value = []
    mock_firebase.return_value = db
    mock_config.return_value = {"pushdeer_key": ""}

    with pytest.raises(RuntimeError, match="PUSHDEER_KEY"):
        run_health_check()
