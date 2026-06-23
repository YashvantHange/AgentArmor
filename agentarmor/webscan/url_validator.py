"""SSRF-safe URL validation for web scans."""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "0.0.0.0",
        "127.0.0.1",
        "::1",
    }
)

_PRIVATE_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
)


@dataclass
class UrlValidationResult:
    ok: bool
    normalized_url: str = ""
    error: str = ""


def _is_blocked_ip(ip_str: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
        return True
    for network in _PRIVATE_NETWORKS:
        if addr in network:
            return True
    return False


def _hostname_blocked(hostname: str, blocklist: list[str]) -> str | None:
    host = hostname.lower().rstrip(".")
    if host in _BLOCKED_HOSTNAMES:
        return f"blocked hostname: {host}"
    if host.endswith(".internal") or host.endswith(".local"):
        return f"blocked hostname suffix: {host}"
    for blocked in blocklist:
        b = blocked.lower()
        if host == b or host.endswith(f".{b}"):
            return f"blocklist match: {host}"
    return None


def _resolve_and_check(hostname: str) -> str | None:
    if hostname.lower() in _BLOCKED_HOSTNAMES:
        return f"blocked hostname: {hostname}"
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        return f"DNS resolution failed: {exc}"
    seen: set[str] = set()
    for info in infos:
        ip = info[4][0]
        if ip in seen:
            continue
        seen.add(ip)
        if _is_blocked_ip(ip):
            return f"resolved IP blocked: {ip}"
    return None


def validate_page_url(
    url: str,
    *,
    allowlist: list[str] | None = None,
    blocklist: list[str] | None = None,
    resolve_dns: bool = True,
) -> UrlValidationResult:
    allow = [a.lower() for a in (allowlist or []) if a.strip()]
    block = [b.lower() for b in (blocklist or []) if b.strip()]

    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        return UrlValidationResult(ok=False, error="only http and https URLs are allowed")
    if not parsed.netloc:
        return UrlValidationResult(ok=False, error="missing hostname")
    hostname = parsed.hostname
    if not hostname:
        return UrlValidationResult(ok=False, error="invalid hostname")

    host_lower = hostname.lower()
    if allow and not any(host_lower == a or host_lower.endswith(f".{a}") for a in allow):
        return UrlValidationResult(ok=False, error="hostname not in allowlist")

    blocked = _hostname_blocked(hostname, block)
    if blocked:
        return UrlValidationResult(ok=False, error=blocked)

    # Literal IP in URL
    try:
        if _is_blocked_ip(hostname):
            return UrlValidationResult(ok=False, error=f"blocked IP: {hostname}")
    except ValueError:
        pass

    if resolve_dns and not hostname.replace(".", "").isdigit():
        dns_err = _resolve_and_check(hostname)
        if dns_err:
            return UrlValidationResult(ok=False, error=dns_err)

    port = parsed.port
    if port is not None and port not in (80, 443, 8080, 8443):
        return UrlValidationResult(ok=False, error=f"blocked port: {port}")

    normalized = parsed._replace(fragment="").geturl()
    return UrlValidationResult(ok=True, normalized_url=normalized)
