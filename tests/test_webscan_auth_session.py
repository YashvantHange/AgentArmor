"""Auth session encryption and TTL tests."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentarmor.webscan.auth.session_store import (
    decrypt_payload,
    encrypt_payload,
    load_storage_state,
    save_storage_state,
    session_expired,
)


def test_encrypt_decrypt_round_trip():
    secret = "test-secret-key"
    raw = b'{"cookies":[{"name":"sid","value":"abc"}]}'
    token = encrypt_payload(raw, secret=secret)
    assert "sid" not in token
    restored = decrypt_payload(token, secret=secret)
    assert restored == raw


def test_wrong_secret_fails():
    token = encrypt_payload(b"data", secret="alpha")
    with pytest.raises(ValueError, match="integrity"):
        decrypt_payload(token, secret="beta")


def test_save_and_load_storage_state(tmp_path: Path):
    state = {"cookies": [{"name": "session", "value": "xyz", "domain": "example.com"}]}
    path = save_storage_state("scan-1", state, ttl_hours=24, store_dir=tmp_path)
    loaded = load_storage_state(path)
    assert loaded["cookies"][0]["name"] == "session"


def test_expired_session_rejected(tmp_path: Path):
    from agentarmor.webscan.auth import session_store

    payload = {
        "scan_id": "scan-2",
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        "storage_state": {"cookies": []},
    }
    path = tmp_path / "scan-2.enc"
    path.write_text(session_store.encrypt_payload(json.dumps(payload).encode()), encoding="utf-8")
    assert session_expired(path)
    with pytest.raises(ValueError, match="expired"):
        load_storage_state(path)


def test_storage_state_not_in_plaintext_logs(tmp_path: Path, caplog):
    import logging

    state = {"cookies": [{"name": "secret_token", "value": "super-secret-value"}]}
    path = save_storage_state("scan-3", state, store_dir=tmp_path)
    content = path.read_text(encoding="utf-8")
    assert "super-secret-value" not in content
    with caplog.at_level(logging.DEBUG):
        logging.debug("saved session to %s", path.name)
    assert "super-secret-value" not in caplog.text
