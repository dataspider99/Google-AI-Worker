"""API tests for main FastAPI app."""
from __future__ import annotations

import pytest


def test_root_returns_200(client):
    r = client.get("/")
    assert r.status_code == 200


def test_health_returns_200(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data


def test_app_ui_returns_200(client):
    r = client.get("/app")
    assert r.status_code == 200


def test_me_requires_auth(client):
    r = client.get("/me")
    assert r.status_code in (401, 403)


def test_me_with_session_override(client_with_auth):
    r = client_with_auth.get("/me")
    assert r.status_code == 200
    data = r.json()
    assert data.get("user_id") == "test@example.com"


def test_me_with_api_key(client, api_key_for_user):
    r = client.get("/me", headers={"Authorization": f"Bearer {api_key_for_user}"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("user_id") == "test@example.com"


def test_workflow_toggles_with_auth(client_with_auth):
    r = client_with_auth.get("/me/workflow-toggles")
    assert r.status_code == 200
    data = r.json()
    assert "smart_inbox" in data
    assert "chat_auto_reply" in data


def test_automation_status_with_auth(client_with_auth):
    r = client_with_auth.get("/me/automation")
    assert r.status_code == 200
    data = r.json()
    assert "enabled" in data


def test_auth_google_fix_double_path_redirects(client):
    r = client.get("/auth/google/auth/google", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert "auth/google" in (r.headers.get("location") or "")
