"""The local API refuses cross-origin requests from arbitrary websites.

`allow_origins=["*"]` with `allow_credentials=True` was worse than it looked.
Starlette computes `preflight_explicit_allow_origin = not allow_all_origins or
allow_credentials`, so it echoed the *requesting* origin rather than `"*"`. A
preflight from `https://evil.example.com` came back with that origin and
`access-control-allow-credentials: true`, meaning any page the user had open could
drive this API - which since 1.5.0 includes launching a hundred-agent swarm at a
host of the attacker's choosing.

A request with no Origin header never reaches the middleware, so the CLI and curl
are unaffected. A browser always sends Origin cross-origin, and a JSON body is not
a CORS-simple content type, so a drive-by POST has to preflight - and now fails.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from agentarmor.api.app import allowed_origin_regex, app

ATTACKER_ORIGINS = [
    "https://evil.example.com",
    "http://evil.example.com",
    "https://agentarmor.example.com",
    # Suffix and prefix tricks against a sloppy substring check.
    "http://attacker.localhost.evil.com",
    "http://localhost.evil.com",
    "http://tauri.localhost.evil.com",
    "https://notlocalhost",
    "null",
]

LEGITIMATE_ORIGINS = [
    "tauri://localhost",  # Tauri v2, macOS and Linux
    "http://tauri.localhost",  # Tauri v2, Windows
    "https://tauri.localhost",
    "http://localhost:1420",  # the vite dev server from tauri.conf.json
    "http://localhost:8787",  # the sidecar's own port
    "http://127.0.0.1:8787",
    "http://localhost",
]


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _preflight(client, origin: str):
    return client.options(
        "/v1/swarms",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )


@pytest.mark.parametrize("origin", ATTACKER_ORIGINS)
def test_an_arbitrary_site_cannot_preflight(client, origin):
    response = _preflight(client, origin)
    assert "access-control-allow-origin" not in response.headers, (
        f"{origin} was granted access"
    )


@pytest.mark.parametrize("origin", LEGITIMATE_ORIGINS)
def test_the_desktop_app_and_dev_server_are_allowed(client, origin):
    response = _preflight(client, origin)
    assert response.headers.get("access-control-allow-origin") == origin, (
        f"{origin} was refused; this would break the shipped GUI"
    )


@pytest.mark.parametrize("origin", ATTACKER_ORIGINS)
def test_a_simple_request_from_an_arbitrary_site_is_not_readable(client, origin):
    """Without the header the browser withholds the response from the page."""
    response = client.get("/health", headers={"Origin": origin})
    assert "access-control-allow-origin" not in response.headers


def test_a_request_without_an_origin_still_works(client):
    """The CLI, curl and the Tauri sidecar poll send no Origin at all."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_wildcard_with_credentials_is_not_reintroduced():
    """The combination is the bug, not either half on its own."""
    from starlette.middleware.cors import CORSMiddleware

    for middleware in app.user_middleware:
        if middleware.cls is not CORSMiddleware:
            continue
        kwargs = middleware.kwargs
        origins = kwargs.get("allow_origins") or []
        if kwargs.get("allow_credentials"):
            assert "*" not in origins, (
                "allow_origins=['*'] with allow_credentials=True echoes the "
                "requesting origin, which allows every site"
            )


def test_the_regex_is_anchored():
    """Unanchored, evil.com/tauri://localhost/x would match."""
    pattern = allowed_origin_regex()
    assert pattern.startswith("^")
    assert pattern.endswith("$")


def test_the_allowlist_is_overridable(monkeypatch):
    """An unusual packaging or remote host must not be permanently locked out."""
    monkeypatch.setenv("AGENTARMOR_ALLOW_ORIGIN_REGEX", r"^https://my\.console$")
    pattern = allowed_origin_regex()
    assert re.match(pattern, "https://my.console")
    assert not re.match(pattern, "https://evil.example.com")


def test_the_default_matches_what_tauri_config_declares():
    """If devUrl changes, the allowlist has to change with it."""
    import json
    from pathlib import Path

    config = json.loads(
        (Path(__file__).resolve().parents[1] / "gui" / "src-tauri" / "tauri.conf.json")
        .read_text(encoding="utf-8")
    )
    dev_url = config["build"]["devUrl"].rstrip("/")
    assert re.match(allowed_origin_regex(), dev_url), (
        f"tauri devUrl {dev_url} is not in the CORS allowlist"
    )
