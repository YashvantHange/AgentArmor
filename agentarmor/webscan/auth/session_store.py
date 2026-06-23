"""Encrypted Playwright storage state persistence with TTL."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_SESSION_SALT = b"agentarmor-webscan-session-v1"


def _session_secret() -> str:
    return os.environ.get("AGENTARMOR_SESSION_KEY", "local-dev-session-key-change-me")


def _derive_key(secret: str) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", secret.encode(), _SESSION_SALT, 120_000, dklen=32)


def _xor_keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    stream = b""
    ctr = 0
    while len(stream) < length:
        stream += hmac.new(key, nonce + ctr.to_bytes(4, "big"), "sha256").digest()
        ctr += 1
    return stream[:length]


def encrypt_payload(data: bytes, secret: str | None = None) -> str:
    """Encrypt bytes; output is base64 JSON envelope (never log this)."""
    key = _derive_key(secret or _session_secret())
    nonce = secrets.token_bytes(16)
    ciphertext = bytes(a ^ b for a, b in zip(data, _xor_keystream(key, nonce, len(data))))
    mac = hmac.new(key, nonce + ciphertext, "sha256").hexdigest()
    envelope = {
        "n": base64.b64encode(nonce).decode("ascii"),
        "c": base64.b64encode(ciphertext).decode("ascii"),
        "m": mac,
    }
    return base64.b64encode(json.dumps(envelope).encode("utf-8")).decode("ascii")


def decrypt_payload(token: str, secret: str | None = None) -> bytes:
    """Decrypt envelope produced by encrypt_payload."""
    key = _derive_key(secret or _session_secret())
    envelope = json.loads(base64.b64decode(token.encode("ascii")))
    nonce = base64.b64decode(envelope["n"])
    ciphertext = base64.b64decode(envelope["c"])
    expected_mac = envelope["m"]
    actual_mac = hmac.new(key, nonce + ciphertext, "sha256").hexdigest()
    if not hmac.compare_digest(expected_mac, actual_mac):
        raise ValueError("session integrity check failed")
    return bytes(a ^ b for a, b in zip(ciphertext, _xor_keystream(key, nonce, len(ciphertext))))


def _default_store_dir() -> Path:
    base = os.environ.get("AGENTARMOR_DATA_DIR")
    if base:
        return Path(base) / "webscan-sessions"
    return Path.home() / ".agentarmor" / "webscan-sessions"


def save_storage_state(
    scan_id: str,
    state: dict[str, Any],
    *,
    ttl_hours: int = 24,
    store_dir: Path | None = None,
) -> Path:
    """Persist encrypted Playwright storage state; returns file path."""
    directory = store_dir or _default_store_dir()
    directory.mkdir(parents=True, exist_ok=True)
    payload = {
        "scan_id": scan_id,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=ttl_hours)).isoformat(),
        "storage_state": state,
    }
    raw = json.dumps(payload).encode("utf-8")
    encrypted = encrypt_payload(raw)
    path = directory / f"{scan_id}.enc"
    path.write_text(encrypted, encoding="utf-8")
    return path


def load_storage_state(path: Path | str) -> dict[str, Any]:
    """Load and decrypt storage state; raises if expired or tampered."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"session file not found: {file_path}")
    token = file_path.read_text(encoding="utf-8")
    raw = decrypt_payload(token)
    payload = json.loads(raw.decode("utf-8"))
    expires = datetime.fromisoformat(payload["expires_at"])
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires:
        raise ValueError("session expired")
    state = payload.get("storage_state")
    if not isinstance(state, dict):
        raise ValueError("invalid session payload")
    return state


def session_expired(path: Path | str) -> bool:
    try:
        load_storage_state(path)
        return False
    except (ValueError, FileNotFoundError):
        return True


def delete_session(path: Path | str) -> None:
    file_path = Path(path)
    if file_path.exists():
        file_path.unlink()
