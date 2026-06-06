from pathlib import Path


DEPLOY_WORKFLOW_PATH = (
    Path(__file__).resolve().parents[2] / ".github" / "workflows" / "deploy-hosting.yml"
)


def test_deploy_workflow_publishes_firestore_indexes():
    workflow = DEPLOY_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "firestore:indexes" in workflow
