import json
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEXES_PATH = PROJECT_ROOT / "firestore.indexes.json"
PROJECT_ID = "etf-notify-app"
DATABASE_ID = "(default)"
FIRESTORE_SCOPE = "https://www.googleapis.com/auth/datastore"


def to_rest_index_body(index: dict) -> dict:
    fields = []
    for field in index.get("fields", []):
        rest_field = {"fieldPath": field["fieldPath"]}
        if "mode" in field:
            rest_field["order"] = field["mode"]
        elif "order" in field:
            rest_field["order"] = field["order"]
        elif "arrayConfig" in field:
            rest_field["arrayConfig"] = field["arrayConfig"]
        else:
            raise ValueError(f"Unsupported index field config: {field}")
        fields.append(rest_field)

    return {
        "queryScope": index.get("queryScope", "COLLECTION"),
        "fields": fields,
    }


def _comparable_fields(fields: list[dict]) -> list[dict]:
    return [
        field
        for field in fields
        if field.get("fieldPath") != "__name__"
    ]


def index_matches(existing: dict, desired: dict) -> bool:
    return (
        existing.get("queryScope") == desired.get("queryScope")
        and _comparable_fields(existing.get("fields", [])) == desired.get("fields", [])
    )


def _load_credentials():
    from google.oauth2 import service_account

    credentials_json = os.environ.get("FIREBASE_CREDENTIALS")
    if not credentials_json:
        raise EnvironmentError("FIREBASE_CREDENTIALS environment variable is not set")

    credentials_info = json.loads(credentials_json)
    return service_account.Credentials.from_service_account_info(
        credentials_info,
        scopes=[FIRESTORE_SCOPE],
    )


def _authorized_session():
    from google.auth.transport.requests import AuthorizedSession

    return AuthorizedSession(_load_credentials())


def _collection_group_url(collection_group: str) -> str:
    return (
        f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}"
        f"/databases/{DATABASE_ID}/collectionGroups/{collection_group}/indexes"
    )


def deploy_indexes() -> None:
    config = json.loads(INDEXES_PATH.read_text(encoding="utf-8"))
    session = _authorized_session()

    for index in config.get("indexes", []):
        collection_group = index["collectionGroup"]
        desired = to_rest_index_body(index)
        url = _collection_group_url(collection_group)

        list_response = session.get(url, timeout=30)
        list_response.raise_for_status()
        existing_indexes = list_response.json().get("indexes", [])
        if any(index_matches(existing, desired) for existing in existing_indexes):
            print(f"Firestore index already exists: {collection_group}")
            continue

        create_response = session.post(url, json=desired, timeout=30)
        if create_response.status_code == 409:
            print(f"Firestore index already exists: {collection_group}")
            continue
        create_response.raise_for_status()
        print(f"Firestore index creation requested: {collection_group}")


if __name__ == "__main__":
    deploy_indexes()
