import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone

from cooldown import is_in_cooldown, record_notification

TZ_BEIJING = timezone(timedelta(hours=8))


def _mock_db_with_notification(timestamp_str):
    """Create a mock Firestore db that returns a single notification doc."""
    mock_doc = MagicMock()
    mock_doc.to_dict.return_value = {"timestamp": timestamp_str}

    mock_query = MagicMock()
    mock_query.where.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.stream.return_value = [mock_doc]

    mock_collection = MagicMock()
    mock_collection.where.return_value = mock_query
    mock_collection.order_by.return_value = mock_query

    db = MagicMock()
    db.collection.return_value = mock_collection
    mock_collection.where.return_value = mock_query

    db.collection.return_value = mock_query
    mock_query.where.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query

    return db


def _mock_db_no_records():
    """Create a mock Firestore db that returns no notification docs."""
    mock_query = MagicMock()
    mock_query.where.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.stream.return_value = []

    db = MagicMock()
    db.collection.return_value = mock_query
    mock_query.where.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query

    return db


class TestIsInCooldownActive:
    """TC-03: Notification within cooldown period should return True."""

    @patch("cooldown.datetime")
    def test_recent_notification_in_cooldown(self, mock_datetime):
        now = datetime(2026, 5, 30, 11, 30, 0, tzinfo=TZ_BEIJING)
        mock_datetime.now.return_value = now
        mock_datetime.fromisoformat = datetime.fromisoformat

        recent_ts = (now - timedelta(minutes=30)).isoformat()
        db = _mock_db_with_notification(recent_ts)

        result = is_in_cooldown("159941", "提醒", 60, db)
        assert result is True

    @patch("cooldown.datetime")
    def test_just_inside_cooldown_boundary(self, mock_datetime):
        now = datetime(2026, 5, 30, 11, 0, 0, tzinfo=TZ_BEIJING)
        mock_datetime.now.return_value = now
        mock_datetime.fromisoformat = datetime.fromisoformat

        recent_ts = (now - timedelta(minutes=59)).isoformat()
        db = _mock_db_with_notification(recent_ts)

        result = is_in_cooldown("159941", "警告", 60, db)
        assert result is True


class TestIsInCooldownExpired:
    """TC-04: Notification outside cooldown period should return False."""

    @patch("cooldown.datetime")
    def test_expired_notification_no_cooldown(self, mock_datetime):
        now = datetime(2026, 5, 30, 14, 0, 0, tzinfo=TZ_BEIJING)
        mock_datetime.now.return_value = now
        mock_datetime.fromisoformat = datetime.fromisoformat

        old_ts = (now - timedelta(minutes=120)).isoformat()
        db = _mock_db_with_notification(old_ts)

        result = is_in_cooldown("159941", "提醒", 60, db)
        assert result is False

    @patch("cooldown.datetime")
    def test_exactly_at_cooldown_boundary(self, mock_datetime):
        now = datetime(2026, 5, 30, 12, 0, 0, tzinfo=TZ_BEIJING)
        mock_datetime.now.return_value = now
        mock_datetime.fromisoformat = datetime.fromisoformat

        boundary_ts = (now - timedelta(minutes=60)).isoformat()
        db = _mock_db_with_notification(boundary_ts)

        result = is_in_cooldown("159941", "紧急", 60, db)
        assert result is False


class TestIsInCooldownIndexFallback:
    """Fallback query should handle missing composite Firestore indexes."""

    @patch("cooldown.datetime")
    def test_missing_composite_index_falls_back_to_single_field_query(self, mock_datetime):
        now = datetime(2026, 6, 5, 14, 23, 0, tzinfo=TZ_BEIJING)
        mock_datetime.now.return_value = now
        mock_datetime.fromisoformat = datetime.fromisoformat

        expired_ts = (now - timedelta(minutes=120)).isoformat()
        fallback_doc = MagicMock()
        fallback_doc.to_dict.return_value = {
            "fund_code": "513100",
            "level": "提醒",
            "timestamp": expired_ts,
        }

        indexed_query = MagicMock()
        indexed_query.where.return_value = indexed_query
        indexed_query.order_by.return_value = indexed_query
        indexed_query.limit.return_value = indexed_query
        indexed_query.stream.side_effect = Exception("The query requires an index")

        fallback_query = MagicMock()
        fallback_query.where.return_value = fallback_query
        fallback_query.stream.return_value = [fallback_doc]

        collection = MagicMock()
        collection.where.side_effect = [indexed_query, fallback_query]

        db = MagicMock()
        db.collection.return_value = collection

        result = is_in_cooldown("513100", "提醒", 60, db)

        assert result is False


class TestIsInCooldownNoRecords:
    """No notification records should return False (not in cooldown)."""

    def test_no_previous_notifications(self):
        db = _mock_db_no_records()
        result = is_in_cooldown("159941", "提醒", 60, db)
        assert result is False

    def test_no_records_different_fund(self):
        db = _mock_db_no_records()
        result = is_in_cooldown("513500", "警告", 60, db)
        assert result is False


class TestRecordNotification:
    """Test that record_notification writes to Firestore correctly."""

    def test_record_writes_to_firestore(self):
        mock_collection = MagicMock()
        db = MagicMock()
        db.collection.return_value = mock_collection

        record_notification(
            fund_code="159941",
            fund_name="纳指ETF",
            level_name="紧急",
            change_pct=-3.18,
            price=1.856,
            channels=["pushdeer", "fcm"],
            db=db,
        )

        db.collection.assert_called_with("notifications")
        mock_collection.add.assert_called_once()
        written_doc = mock_collection.add.call_args[0][0]
        assert written_doc["fund_code"] == "159941"
        assert written_doc["level"] == "紧急"
        assert written_doc["change_pct"] == -3.18
        assert written_doc["channels"] == ["pushdeer", "fcm"]
        assert written_doc["delivered"] is True

    def test_record_handles_firestore_error(self):
        mock_collection = MagicMock()
        mock_collection.add.side_effect = Exception("Firestore unavailable")
        db = MagicMock()
        db.collection.return_value = mock_collection

        # Should not raise
        record_notification(
            fund_code="159941",
            fund_name="纳指ETF",
            level_name="提醒",
            change_pct=-1.5,
            price=1.9,
            channels=["pushdeer"],
            db=db,
        )
