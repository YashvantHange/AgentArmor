"""Execute browser probes against discovered chat widgets."""

from __future__ import annotations

import re
from typing import Any

from agentarmor.webscan.models import StableResponse, WebProbeDef, WidgetCandidate
from agentarmor.webscan.probes.response_stability import capture_baseline_lines, wait_stable_response

_UNRELIABLE_SEND_RE = re.compile(r"upload|attach|file|member|card|image|photo", re.I)


def _input_locator(page: Any, widget: WidgetCandidate) -> Any:
    if widget.frame_path:
        fl = page
        for idx in widget.frame_path:
            fl = fl.frame_locator(f"iframe >> nth={idx}")
        return fl.locator(widget.input_selector)
    return page.locator(widget.input_selector)


def _send_locator(page: Any, widget: WidgetCandidate) -> Any | None:
    if not widget.send_selector:
        return None
    if widget.frame_path:
        fl = page
        for idx in widget.frame_path:
            fl = fl.frame_locator(f"iframe >> nth={idx}")
        return fl.locator(widget.send_selector)
    return page.locator(widget.send_selector)


def _send_selector_unreliable(widget: WidgetCandidate) -> bool:
    if not widget.send_selector:
        return False
    return bool(_UNRELIABLE_SEND_RE.search(widget.send_selector))


async def execute_probe(
    page: Any,
    widget: WidgetCandidate,
    probe: WebProbeDef,
    *,
    stable_ms: int = 1500,
    max_wait_ms: int = 45000,
    baseline_text: str = "",
) -> StableResponse:
    input_loc = _input_locator(page, widget)
    await input_loc.wait_for(state="visible", timeout=15000)
    baseline_lines = await capture_baseline_lines(page, widget)
    await input_loc.click()
    await input_loc.fill(probe.prompt)

    send_loc = _send_locator(page, widget)
    if send_loc is not None and not _send_selector_unreliable(widget):
        try:
            if await send_loc.count() > 0:
                await send_loc.first.click()
            else:
                await input_loc.press("Enter")
        except Exception:
            await input_loc.press("Enter")
    else:
        await input_loc.press("Enter")

    await page.wait_for_timeout(300)
    return await wait_stable_response(
        page,
        widget,
        stable_ms=stable_ms,
        max_wait_ms=max_wait_ms,
        baseline_lines=baseline_lines,
        prompt_text=probe.prompt,
    )


async def execute_multi_turn_probe(
    page: Any,
    widget: WidgetCandidate,
    probe: WebProbeDef,
    *,
    stable_ms: int = 1500,
    max_wait_ms: int = 45000,
) -> StableResponse:
    """Run a two-turn probe without reloading the page (memory persistence tests)."""
    first = await execute_probe(
        page,
        widget,
        probe,
        stable_ms=stable_ms,
        max_wait_ms=max_wait_ms,
    )
    if probe.turns < 2 or not probe.follow_up_prompt:
        return first

    follow_up = WebProbeDef(
        id=f"{probe.id}.turn2",
        name=f"{probe.name} (verify)",
        owasp=probe.owasp,
        prompt=probe.follow_up_prompt,
    )
    second = await execute_probe(
        page,
        widget,
        follow_up,
        stable_ms=stable_ms,
        max_wait_ms=max_wait_ms,
    )
    combined_text = f"{first.text}\n---\n{second.text}".strip()
    return StableResponse(
        text=combined_text,
        complete=first.complete and second.complete,
        wait_ms=first.wait_ms + second.wait_ms,
        stream_detected=first.stream_detected or second.stream_detected,
        partial=first.partial or second.partial,
    )
