"""URL validator tests."""

import pytest

from agentarmor.webscan.url_validator import validate_page_url


def test_accepts_https_public_url():
    r = validate_page_url("https://example.com/chat", resolve_dns=False)
    assert r.ok
    assert r.normalized_url.startswith("https://example.com")


def test_blocks_localhost():
    r = validate_page_url("http://localhost/chat")
    assert not r.ok
    assert "localhost" in r.error.lower() or "blocked" in r.error.lower()


def test_blocks_127():
    r = validate_page_url("http://127.0.0.1/chat")
    assert not r.ok


def test_blocks_private_ip_literal():
    r = validate_page_url("http://192.168.1.1/chat")
    assert not r.ok


def test_blocks_file_scheme():
    r = validate_page_url("file:///etc/passwd")
    assert not r.ok


def test_blocks_internal_suffix():
    r = validate_page_url("http://app.corp.internal/chat", resolve_dns=False)
    assert not r.ok


def test_allowlist_enforced():
    r = validate_page_url(
        "https://example.com/chat",
        allowlist=["allowed.com"],
        resolve_dns=False,
    )
    assert not r.ok


def test_allowlist_permits():
    r = validate_page_url(
        "https://app.allowed.com/chat",
        allowlist=["allowed.com"],
        resolve_dns=False,
    )
    assert r.ok
