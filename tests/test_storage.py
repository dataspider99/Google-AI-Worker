"""Unit tests for storage module."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

import storage
from storage import (
    DEFAULT_WORKFLOW_TOGGLES,
    _hash_api_key,
    _make_json_safe,
    _safe_filename,
    ensure_data_dir_ready,
    generate_api_key,
    get_user_by_api_key,
    revoke_api_key,
)


def test_safe_filename():
    assert _safe_filename("user@example.com") == "user_at_example_dot_com"
    assert _safe_filename("a@b.co") == "a_at_b_dot_co"
    assert _safe_filename("noats") == "noats"


def test_hash_api_key():
    h = _hash_api_key("secret")
    assert isinstance(h, str)
    assert len(h) == 64
    assert h == _hash_api_key("secret")
    assert h != _hash_api_key("other")


def test_make_json_safe():
    assert _make_json_safe(1) == 1
    assert _make_json_safe("x") == "x"
    assert _make_json_safe([1, 2]) == [1, 2]
    assert _make_json_safe({"a": 1}) == {"a": 1}
    dt = datetime(2025, 1, 15, 12, 0, 0)
    assert _make_json_safe(dt) == "2025-01-15T12:00:00"
    nested = {"expiry": dt, "nested": {"x": 1}}
    out = _make_json_safe(nested)
    assert out["expiry"] == "2025-01-15T12:00:00"
    assert out["nested"] == {"x": 1}


def test_ensure_data_dir_ready(tmp_path):
    with pytest.MonkeyPatch.context() as m:
        m.setattr(storage, "DATA_DIR", tmp_path)
        path = ensure_data_dir_ready()
        assert path == tmp_path
        assert (tmp_path / ".write_check").exists() is False  # probe is unlinked


def test_generate_and_lookup_api_key(tmp_path):
    with pytest.MonkeyPatch.context() as m:
        m.setattr(storage, "DATA_DIR", tmp_path)
        key1 = generate_api_key("user1@test.com")
        key2 = generate_api_key("user2@test.com")
        assert key1.startswith("ge_")
        assert key2.startswith("ge_")
        assert key1 != key2
        assert get_user_by_api_key(key1) == "user1@test.com"
        assert get_user_by_api_key(key2) == "user2@test.com"
        assert get_user_by_api_key("invalid") is None
        assert get_user_by_api_key("") is None


def test_revoke_api_key(tmp_path):
    with pytest.MonkeyPatch.context() as m:
        m.setattr(storage, "DATA_DIR", tmp_path)
        key = generate_api_key("revoke@test.com")
        assert get_user_by_api_key(key) == "revoke@test.com"
        ok = revoke_api_key("revoke@test.com")
        assert ok is True
        assert get_user_by_api_key(key) is None
        ok2 = revoke_api_key("revoke@test.com")
        assert ok2 is False


def test_default_workflow_toggles():
    assert set(DEFAULT_WORKFLOW_TOGGLES) == {
        "smart_inbox",
        "document_intelligence",
        "chat_auto_reply",
        "first_email_draft",
        "chat_spaces",
    }
    for v in DEFAULT_WORKFLOW_TOGGLES.values():
        assert v is True


def test_get_user_workflow_toggles_no_creds():
    """When user has no credentials, returns default toggles."""
    with patch.object(storage, "load_credentials", return_value=None):
        toggles = storage.get_user_workflow_toggles("nobody@test.com")
        assert toggles == dict(DEFAULT_WORKFLOW_TOGGLES)


def test_get_user_automation_enabled_no_creds():
    """When user has no credentials, default is True."""
    with patch.object(storage, "load_credentials", return_value=None):
        assert storage.get_user_automation_enabled("nobody@test.com") is True
