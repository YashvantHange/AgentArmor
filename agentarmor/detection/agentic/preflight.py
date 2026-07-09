"""Preflight validation for the cloud analysis provider key.

Every scan runs the multi-agent cloud analysis, so an invalid/unauthorized key
turns a scan into signature-only results without the user realising. This makes
one cheap call up front and fails fast on authentication errors, while treating
transient problems (network, rate limit, timeout) as non-fatal so they don't
block a scan.
"""

from __future__ import annotations

import logging

from agentarmor.core.config import AppConfig

_log = logging.getLogger(__name__)


def _is_auth_error(exc: Exception) -> bool:
    """True when the exception clearly means the key was rejected (401/403)."""
    name = exc.__class__.__name__.lower()
    if "authentication" in name or "permissiondenied" in name:
        return True
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    try:
        if int(status) in (401, 403):
            return True
    except (TypeError, ValueError):
        pass
    text = str(exc).lower()
    return "authenticationerror" in text or "incorrect api key" in text or "invalid api key" in text


async def validate_analysis_key(config: AppConfig) -> None:
    """Make one minimal completion to confirm the analysis key is accepted.

    Raises ``ValueError`` only when the provider rejects the key (401/403). Any
    other error is logged and swallowed so transient issues don't block scans.
    """
    agentic = config.detection.agentic
    if not agentic.enabled or not agentic.api_key:
        return  # ensure_analysis_ready already guards the missing-key case

    import litellm

    model = agentic.model
    if "/" not in model:
        model = f"{agentic.provider}/{model}"

    try:
        await litellm.acompletion(
            model=model,
            api_key=agentic.api_key or None,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
            temperature=0.0,
        )
    except Exception as exc:  # noqa: BLE001 - classify then re-raise or warn
        if _is_auth_error(exc):
            raise ValueError(
                f"Analysis API key was rejected by the provider ({agentic.provider}). "
                "The scan needs a valid analysis key to run its multi-agent analysis. "
                "Check AGENTARMOR_ANALYSIS_API_KEY (or the key in Settings / --analysis-api-key)."
            ) from exc
        _log.warning(
            "Analysis key preflight could not complete (%s: %s); continuing — "
            "the scan will flag it if cloud analysis fails.",
            exc.__class__.__name__,
            exc,
        )
