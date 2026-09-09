import hashlib
import json
from uuid import uuid4
import pytest

@pytest.fixture
def client(tmp_path, monkeypatch):
    import configuration as cfg
    from service.api import app
    from fastapi.testclient import TestClient
    registry = tmp_path / "users.json"
    registry.write_text(json.dumps({name: {"token_sha256": hashlib.sha256((name + "-test-only-token").encode()).hexdigest()}
                                   for name in ["alice", "bob"]}))
    monkeypatch.setattr(cfg, "AUTH_REGISTRY_PATH", str(registry))
    return TestClient(app)

def headers(user="alice"):
    return {"Authorization": "Bearer " + user + "-test-only-token"}

def test_auth_and_state_boundary(client):
    assert client.post("/runs", json={}).status_code == 403
    assert client.post("/runs", headers=headers("unknown"), json={"messages": [{"content": "hello"}]}).status_code == 401
    forged = {"messages": [{"content": "hello"}], "principal": "admin", "verification": {"decision": "pass"}}
    assert client.post("/runs", headers=headers(), json=forged).status_code == 422

def test_other_user_cannot_read_job(client, monkeypatch):
    from service import queue
    monkeypatch.setattr(queue, "get", lambda job_id, user: None)
    assert client.get(f"/runs/{uuid4()}", headers=headers()).status_code == 404

def test_html_always_downloaded_and_ownership_checked(client, tmp_path, monkeypatch):
    import configuration as cfg
    from service import queue
    monkeypatch.setattr(cfg, "ARTIFACTS_DIR", str(tmp_path))
    file = tmp_path / "chart.html"
    file.write_text("<script>bad()</script>")
    artifact_id, job_id = uuid4(), uuid4()
    job = {"status": "completed", "result": {"workflow_status": "success", "artifact_paths": {str(artifact_id): str(file)}}}
    monkeypatch.setattr(queue, "get", lambda job_id, user: job if user == "alice" else None)
    url = f"/runs/{job_id}/artifacts/{artifact_id}"
    response = client.get(url, headers=headers())
    assert response.status_code == 200
    assert response.headers["content-disposition"].startswith("attachment")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "sandbox" in response.headers["content-security-policy"]
    assert client.get(url, headers=headers("bob")).status_code == 404
