import json
from pathlib import Path


INDEXES_PATH = Path(__file__).resolve().parents[2] / "firestore.indexes.json"


def test_notifications_cooldown_query_has_composite_index():
    config = json.loads(INDEXES_PATH.read_text(encoding="utf-8"))

    expected_fields = [
        {"fieldPath": "fund_code", "mode": "ASCENDING"},
        {"fieldPath": "level", "mode": "ASCENDING"},
        {"fieldPath": "timestamp", "mode": "DESCENDING"},
    ]

    assert any(
        index.get("collectionGroup") == "notifications"
        and index.get("queryScope") == "COLLECTION"
        and index.get("fields") == expected_fields
        for index in config.get("indexes", [])
    )
