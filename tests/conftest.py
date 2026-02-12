"""Pytest fixtures for Johny Sins tests."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    """Return a temporary directory for DATA_DIR in tests."""
    return tmp_path


@pytest.fixture
def client(tmp_data_dir: Path):
    """FastAPI TestClient with DATA_DIR pointed at a temp directory."""
    import config
    import storage

    # Point config and storage at temp dir so tests don't touch real data
    original_data_dir = config.DATA_DIR
    config.DATA_DIR = tmp_data_dir
    storage.DATA_DIR = tmp_data_dir

    try:
        from main import app
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c
    finally:
        config.DATA_DIR = original_data_dir
        storage.DATA_DIR = original_data_dir


@pytest.fixture
def client_with_auth(client, tmp_data_dir):
    """TestClient with get_current_user overridden to return a test user."""
    from main import app
    from auth.deps import get_current_user

    def override_get_current_user():
        return "test@example.com"

    app.dependency_overrides[get_current_user] = override_get_current_user
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def api_key_for_user(client, tmp_data_dir):
    """Create an API key for test@example.com and return the raw key."""
    import storage
    storage.DATA_DIR = tmp_data_dir
    key = storage.generate_api_key("test@example.com")
    return key
