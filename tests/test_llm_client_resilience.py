"""Timeout, bounded retry and error classification in completion_json."""

from __future__ import annotations

import asyncio
import json

import pytest

from agentarmor.core.config import AppConfig
from agentarmor.redteam.budget.governor import BudgetGovernor
from agentarmor.redteam.llm_client import completion_json, is_retryable


class _Usage:
    prompt_tokens = 11
    completion_tokens = 7


class _Message:
    def __init__(self, content: str) -> None:
        self.content = content


class _Choice:
    def __init__(self, content: str) -> None:
        self.message = _Message(content)


class _Completion:
    def __init__(self, content: str) -> None:
        self.choices = [_Choice(content)]
        self.usage = _Usage()
        self._hidden_params = {"response_cost": 0.0001}


class _StatusError(Exception):
    def __init__(self, message: str, status: int) -> None:
        super().__init__(message)
        self.status_code = status


class _AuthError(Exception):
    pass


def _config() -> AppConfig:
    cfg = AppConfig()
    cfg.detection.agentic.api_key = "test-key"
    cfg.detection.agentic.model = "gpt-4o-mini"
    return cfg


def _governor() -> BudgetGovernor:
    return BudgetGovernor(_config().redteam.budget)


@pytest.fixture
def no_backoff(monkeypatch):
    """Collapse retry backoff.

    Capture the real sleep first: patching asyncio.sleep with a lambda that calls
    asyncio.sleep recurses into the patch.
    """
    real_sleep = asyncio.sleep

    async def instant(_delay, *args, **kwargs):
        return await real_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", instant)


def _call(cfg, budget, **kwargs):
    return completion_json(
        cfg, budget, system="sys", user="usr", agent_name="test", **kwargs
    )


# --- classification ---------------------------------------------------------


@pytest.mark.parametrize("status", [408, 409, 429, 500, 502, 503, 504])
def test_transient_statuses_are_retryable(status):
    assert is_retryable(_StatusError("boom", status)) is True


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
def test_client_errors_are_not_retryable(status):
    assert is_retryable(_StatusError("boom", status)) is False


def test_timeout_is_retryable():
    assert is_retryable(asyncio.TimeoutError()) is True


def test_auth_errors_are_never_retryable():
    assert is_retryable(_AuthError("Incorrect API key provided")) is False
    assert is_retryable(Exception("AuthenticationError: invalid api key")) is False


@pytest.mark.parametrize(
    "message",
    [
        "This model's maximum context length is 8192 tokens",
        "invalid_request_error: bad payload",
        "The model does not exist",
        "content policy violation",
    ],
)
def test_permanent_failures_are_not_retryable(message):
    assert is_retryable(Exception(message)) is False


@pytest.mark.parametrize(
    "message",
    ["Rate limit exceeded", "Service Unavailable", "connection reset by peer"],
)
def test_transient_messages_are_retryable(message):
    assert is_retryable(Exception(message)) is True


# --- timeout ----------------------------------------------------------------


def test_timeout_is_enforced(monkeypatch):
    async def slow(*_args, **_kwargs):
        await asyncio.sleep(5)

    monkeypatch.setattr("litellm.acompletion", slow, raising=False)
    cfg, budget = _config(), _governor()

    async def run():
        loop = asyncio.get_event_loop()
        start = loop.time()
        parsed, trace = await _call(cfg, budget, timeout_s=0.05, max_retries=0)
        return parsed, trace, loop.time() - start

    parsed, trace, elapsed = asyncio.run(run())
    assert parsed is None
    assert trace["error"] == "timeout"
    assert elapsed < 2.0, "wait_for did not cut the call short"


def test_timeout_defaults_to_agentic_timeout(monkeypatch):
    """agentic.timeout_s already existed and was simply never applied here."""
    captured: dict[str, float] = {}

    async def fake_wait_for(coro, timeout):
        captured["timeout"] = timeout
        coro.close()
        raise asyncio.TimeoutError

    async def never(*_args, **_kwargs):
        await asyncio.sleep(99)

    monkeypatch.setattr("litellm.acompletion", never, raising=False)
    monkeypatch.setattr(asyncio, "wait_for", fake_wait_for)

    cfg = _config()
    cfg.detection.agentic.timeout_s = 12.5
    asyncio.run(_call(cfg, _governor(), max_retries=0))
    assert captured["timeout"] == 12.5


def test_a_timed_out_attempt_is_charged(monkeypatch):
    """A timeout may still have been billed upstream, so it must not look free."""

    async def slow(*_args, **_kwargs):
        await asyncio.sleep(5)

    monkeypatch.setattr("litellm.acompletion", slow, raising=False)
    budget = _governor()
    asyncio.run(_call(_config(), budget, timeout_s=0.05, max_retries=0))
    assert budget.state.tokens_used > 0
    assert budget.state.calls == 1


def test_a_rejected_attempt_is_not_charged(monkeypatch):
    """A 429 did no inference; charging for it would overstate spend."""

    async def rejected(*_args, **_kwargs):
        raise _StatusError("Rate limit exceeded", 429)

    monkeypatch.setattr("litellm.acompletion", rejected, raising=False)
    budget = _governor()
    asyncio.run(_call(_config(), budget, max_retries=0))
    assert budget.state.tokens_used == 0


# --- retries ----------------------------------------------------------------


def test_retries_a_transient_failure_then_succeeds(monkeypatch, no_backoff):
    attempts = {"n": 0}

    async def flaky(*_args, **_kwargs):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise _StatusError("Rate limit exceeded", 429)
        return _Completion(json.dumps({"prompt": "ok"}))

    monkeypatch.setattr("litellm.acompletion", flaky, raising=False)
    parsed, trace = asyncio.run(_call(_config(), _governor(), max_retries=2))
    assert parsed == {"prompt": "ok"}
    assert attempts["n"] == 3
    assert trace["attempts"] == 3


def test_does_not_retry_an_auth_error(monkeypatch):
    attempts = {"n": 0}

    async def unauthorized(*_args, **_kwargs):
        attempts["n"] += 1
        raise _AuthError("Incorrect API key provided")

    monkeypatch.setattr("litellm.acompletion", unauthorized, raising=False)
    parsed, trace = asyncio.run(_call(_config(), _governor(), max_retries=3))
    assert parsed is None
    assert attempts["n"] == 1, "an auth failure must surface immediately"
    assert trace["attempts"] == 1


def test_does_not_retry_a_permanent_failure(monkeypatch):
    attempts = {"n": 0}

    async def too_long(*_args, **_kwargs):
        attempts["n"] += 1
        raise Exception("This model's maximum context length is 8192 tokens")

    monkeypatch.setattr("litellm.acompletion", too_long, raising=False)
    asyncio.run(_call(_config(), _governor(), max_retries=3))
    assert attempts["n"] == 1


def test_retries_are_bounded(monkeypatch, no_backoff):
    attempts = {"n": 0}

    async def always_429(*_args, **_kwargs):
        attempts["n"] += 1
        raise _StatusError("Rate limit exceeded", 429)

    monkeypatch.setattr("litellm.acompletion", always_429, raising=False)
    _, trace = asyncio.run(_call(_config(), _governor(), max_retries=2))
    assert attempts["n"] == 3  # the initial call plus two retries
    assert trace["attempts"] == 3


def test_retry_count_defaults_to_swarm_config(monkeypatch, no_backoff):
    attempts = {"n": 0}

    async def always_503(*_args, **_kwargs):
        attempts["n"] += 1
        raise _StatusError("Service Unavailable", 503)

    monkeypatch.setattr("litellm.acompletion", always_503, raising=False)
    cfg = _config()
    cfg.swarm.llm_max_retries = 1
    asyncio.run(_call(cfg, _governor()))
    assert attempts["n"] == 2


def test_retry_stops_when_the_budget_is_exhausted(monkeypatch, no_backoff):
    async def always_429(*_args, **_kwargs):
        raise _StatusError("Rate limit exceeded", 429)

    monkeypatch.setattr("litellm.acompletion", always_429, raising=False)
    budget = _governor()
    budget.record_usage(input_tokens=budget.config.max_tokens, output_tokens=0)
    _, trace = asyncio.run(_call(_config(), budget, max_retries=5))
    assert trace["attempts"] == 0
    assert "budget" in trace["error"].lower() or "max_tokens" in trace["error"].lower()


# --- backwards compatibility -------------------------------------------------


def test_existing_callers_are_unaffected(monkeypatch):
    """The 13 red-team agents call this with the pre-1.5.0 keyword set only."""
    calls = {"n": 0}

    async def ok(*_args, **_kwargs):
        calls["n"] += 1
        return _Completion(json.dumps({"prompt": "hello", "name": "probe"}))

    monkeypatch.setattr("litellm.acompletion", ok, raising=False)
    budget = _governor()

    parsed, trace = asyncio.run(
        completion_json(
            _config(),
            budget,
            system="sys",
            user="usr",
            agent_name="attack_llm01",
            temperature=0.4,
        )
    )
    assert parsed == {"prompt": "hello", "name": "probe"}
    assert trace["agent"] == "attack_llm01"
    assert trace["tokens"] == 18
    assert calls["n"] == 1
    # Usage recorded exactly once, as before.
    assert budget.state.calls == 1


def test_fenced_json_still_parses(monkeypatch):
    async def fenced(*_args, **_kwargs):
        return _Completion('```json\n{"prompt": "x"}\n```')

    monkeypatch.setattr("litellm.acompletion", fenced, raising=False)
    parsed, _ = asyncio.run(_call(_config(), _governor()))
    assert parsed == {"prompt": "x"}


def test_non_dict_json_returns_none(monkeypatch):
    async def listy(*_args, **_kwargs):
        return _Completion("[1, 2, 3]")

    monkeypatch.setattr("litellm.acompletion", listy, raising=False)
    parsed, _ = asyncio.run(_call(_config(), _governor()))
    assert parsed is None


def test_concurrent_calls_respect_the_llm_semaphore(monkeypatch):
    in_flight = {"now": 0, "max": 0}

    async def tracked(*_args, **_kwargs):
        in_flight["now"] += 1
        in_flight["max"] = max(in_flight["max"], in_flight["now"])
        await asyncio.sleep(0.01)
        in_flight["now"] -= 1
        return _Completion(json.dumps({"prompt": "ok"}))

    monkeypatch.setattr("litellm.acompletion", tracked, raising=False)
    cfg = _config()
    cfg.swarm.llm_max_concurrent = 3
    budget = _governor()

    async def run():
        await asyncio.gather(*[_call(cfg, budget) for _ in range(12)])

    asyncio.run(run())
    assert in_flight["max"] <= 3, f"semaphore exceeded: {in_flight['max']}"
