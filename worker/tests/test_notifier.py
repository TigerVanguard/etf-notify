import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch, MagicMock
import pytest

from notifier import send_pushdeer, send_fcm


class TestSendPushdeerFailure:
    """TC-07: requests.get failure should return False without crashing."""

    @patch("notifier.requests.get")
    def test_network_error_returns_false(self, mock_get):
        mock_get.side_effect = ConnectionError("Connection refused")
        result = send_pushdeer("test_key", "Title", "Body")
        assert result is False

    @patch("notifier.requests.get")
    def test_timeout_returns_false(self, mock_get):
        mock_get.side_effect = TimeoutError("Timed out")
        result = send_pushdeer("test_key", "Title", "Body")
        assert result is False

    @patch("notifier.requests.get")
    def test_http_500_returns_false(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("500 Server Error")
        mock_get.return_value = mock_resp
        result = send_pushdeer("test_key", "Title", "Body")
        assert result is False

    @patch("notifier.requests.get")
    def test_pushdeer_business_error_returns_false(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"code": 1, "error": "invalid pushkey"}
        mock_get.return_value = mock_resp

        result = send_pushdeer("test_key", "Title", "Body")

        assert result is False

    @patch("notifier.requests.get")
    def test_invalid_json_returns_false(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.side_effect = ValueError("not json")
        mock_get.return_value = mock_resp

        result = send_pushdeer("test_key", "Title", "Body")

        assert result is False

    def test_empty_key_returns_false(self):
        result = send_pushdeer("", "Title", "Body")
        assert result is False


class TestSendPushdeerSuccess:
    """Mock requests.get success, verify send_pushdeer returns True."""

    @patch("notifier.requests.get")
    def test_successful_push(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"code": 0}
        mock_get.return_value = mock_resp

        result = send_pushdeer("PDU_test_key", "[紧急] 纳指ETF 跌幅 -3.2%", "详细内容")
        assert result is True
        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args
        assert call_kwargs[1]["params"]["pushkey"] == "PDU_test_key"
        assert "紧急" in call_kwargs[1]["params"]["text"]

    @patch("notifier.requests.get")
    def test_params_format(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"code": 0}
        mock_get.return_value = mock_resp

        send_pushdeer("my_key", "Test Title", "Test Content")
        params = mock_get.call_args[1]["params"]
        assert params["pushkey"] == "my_key"
        assert params["text"] == "Test Title"
        assert params["desp"] == "Test Content"
        assert params["type"] == "markdown"


class TestSendFcmFailure:
    """TC-07: firebase_admin.messaging.send failure should return False."""

    @patch("notifier.messaging.send")
    @patch("notifier.messaging.Message")
    @patch("notifier.messaging.Notification")
    def test_fcm_send_exception_returns_false(self, mock_notif, mock_msg, mock_send):
        mock_send.side_effect = Exception("FCM service unavailable")
        result = send_fcm("etf-alerts", "Title", "Body", {"key": "val"})
        assert result is False

    @patch("notifier.messaging.send")
    @patch("notifier.messaging.Message")
    @patch("notifier.messaging.Notification")
    def test_fcm_auth_error_returns_false(self, mock_notif, mock_msg, mock_send):
        mock_send.side_effect = ValueError("Invalid credentials")
        result = send_fcm("etf-alerts", "Title", "Body")
        assert result is False


class TestSendFcmSuccess:
    """Mock FCM send success."""

    @patch("notifier.messaging.send")
    @patch("notifier.messaging.Message")
    @patch("notifier.messaging.Notification")
    def test_successful_fcm_send(self, mock_notif, mock_msg, mock_send):
        mock_send.return_value = "projects/my-project/messages/12345"
        result = send_fcm("etf-alerts", "Title", "Body", {"fund": "159941"})
        assert result is True
