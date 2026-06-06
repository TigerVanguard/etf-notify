import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deploy_firestore_indexes import index_matches, to_rest_index_body


def test_to_rest_index_body_converts_firebase_index_config():
    index = {
        "collectionGroup": "notifications",
        "queryScope": "COLLECTION",
        "fields": [
            {"fieldPath": "fund_code", "mode": "ASCENDING"},
            {"fieldPath": "level", "mode": "ASCENDING"},
            {"fieldPath": "timestamp", "mode": "DESCENDING"},
        ],
    }

    assert to_rest_index_body(index) == {
        "queryScope": "COLLECTION",
        "fields": [
            {"fieldPath": "fund_code", "order": "ASCENDING"},
            {"fieldPath": "level", "order": "ASCENDING"},
            {"fieldPath": "timestamp", "order": "DESCENDING"},
        ],
    }


def test_index_matches_existing_firestore_admin_response():
    desired = {
        "queryScope": "COLLECTION",
        "fields": [
            {"fieldPath": "fund_code", "order": "ASCENDING"},
            {"fieldPath": "level", "order": "ASCENDING"},
            {"fieldPath": "timestamp", "order": "DESCENDING"},
        ],
    }
    existing = {
        "name": "projects/demo/databases/(default)/collectionGroups/notifications/indexes/abc",
        "queryScope": "COLLECTION",
        "fields": [
            {"fieldPath": "fund_code", "order": "ASCENDING"},
            {"fieldPath": "level", "order": "ASCENDING"},
            {"fieldPath": "timestamp", "order": "DESCENDING"},
            {"fieldPath": "__name__", "order": "DESCENDING"},
        ],
    }

    assert index_matches(existing, desired)
