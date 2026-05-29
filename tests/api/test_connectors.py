from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.dependencies import require_user
from src.api.routes import connectors


def _user() -> dict:
    return {"id": "user-1", "email": "user@example.com", "username": "user"}


def _client() -> TestClient:
    app = FastAPI()
    app.dependency_overrides[require_user] = _user
    app.include_router(connectors.router)
    return TestClient(app)


def test_lists_supported_connectors() -> None:
    response = _client().get("/api/connectors")

    assert response.status_code == 200
    body = response.json()
    ids = {item["id"] for item in body["connectors"]}
    assert ids == {"notion", "google-drive"}
    assert {item["state"] for item in body["connectors"]} == {"not_connected"}


def test_oauth_start_requires_configured_client_id(monkeypatch) -> None:
    monkeypatch.setattr(connectors.settings, "notion_client_id", None, raising=False)

    response = _client().post("/api/connectors/notion/oauth/start")

    assert response.status_code == 503
    assert "client ID is not configured" in response.json()["detail"]


def test_oauth_start_builds_authorization_url_without_secret(monkeypatch) -> None:
    monkeypatch.setattr(connectors.settings, "google_drive_client_id", "drive-client", raising=False)
    monkeypatch.setattr(connectors.settings, "google_drive_client_secret", "do-not-leak", raising=False)
    monkeypatch.setattr(
        connectors.settings,
        "google_drive_redirect_uri",
        "http://localhost:8000/api/connectors/google-drive/oauth/callback",
        raising=False,
    )

    response = _client().post("/api/connectors/google-drive/oauth/start")

    assert response.status_code == 200
    body = response.json()
    assert body["connector_id"] == "google-drive"
    assert "accounts.google.com" in body["authorization_url"]
    assert "client_id=drive-client" in body["authorization_url"]
    assert "do-not-leak" not in body["authorization_url"]
    assert body["state"]


def test_callback_marks_connection_then_disconnects(monkeypatch) -> None:
    monkeypatch.setattr(connectors.settings, "notion_client_id", "notion-client", raising=False)
    client = _client()

    started = client.post("/api/connectors/notion/oauth/start")
    state = started.json()["state"]

    callback = client.get(f"/api/connectors/notion/oauth/callback?code=abc&state={state}")
    assert callback.status_code == 200
    assert callback.json()["status"] == "connected"

    connected = client.get("/api/connectors/notion/status")
    assert connected.status_code == 200
    assert connected.json()["state"] == "connected"

    disconnected = client.post("/api/connectors/notion/disconnect")
    assert disconnected.status_code == 200
    assert disconnected.json() == {"connector_id": "notion", "disconnected": True}
