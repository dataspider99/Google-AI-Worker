"""Unit tests for auth.google_oauth (credentials dict and expiry normalization)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from auth.google_oauth import (
    _normalize_expiry_to_naive_utc,
    dict_to_credentials,
)


def test_normalize_expiry_to_naive_utc():
    utc_aware = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    out = _normalize_expiry_to_naive_utc(utc_aware)
    assert out.tzinfo is None
    assert out.year == 2025 and out.month == 6 and out.day == 1

    naive = datetime(2025, 6, 1, 12, 0, 0)
    out2 = _normalize_expiry_to_naive_utc(naive)
    assert out2.tzinfo is None
    assert out2 == naive


def test_dict_to_credentials_normalizes_expiry():
    """Expiry from ISO string with Z is stored as naive UTC on credentials."""
    data = {
        "token": "t",
        "refresh_token": "r",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "cid",
        "client_secret": "csec",
        "scopes": [],
        "expiry": "2025-06-01T12:00:00Z",
    }
    creds = dict_to_credentials(data)
    assert creds.expiry is not None
    assert creds.expiry.tzinfo is None


def test_dict_to_credentials_no_expiry():
    data = {
        "token": "t",
        "refresh_token": "r",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "cid",
        "client_secret": "csec",
        "scopes": [],
    }
    creds = dict_to_credentials(data)
    assert creds.expiry is None
