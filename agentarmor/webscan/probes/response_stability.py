"""Wait for streaming chat responses to stabilize before analysis."""

from __future__ import annotations

import time
from typing import Any

from agentarmor.webscan.models import StableResponse, WidgetCandidate

TYPING_SELECTORS = [
    "[aria-busy='true']",
    ".typing",
    ".thinking",
    "[class*='typing']",
    "[class*='loading']",
    "[class*='spinner']",
]

STREAM_DONE_SCRIPT = """
(selectors) => {
  for (const sel of selectors) {
    const els = document.querySelectorAll(sel);
    for (const el of els) {
      const t = (el.textContent || '').toLowerCase();
      if (t.includes('thinking') || t.includes('typing') || el.getAttribute('aria-busy') === 'true') {
        return false;
      }
    }
  }
  return true;
}
"""


async def wait_stable_response(
    page: Any,
    widget: WidgetCandidate,
    *,
    assistant_selector: str | None = None,
    stable_ms: int = 1500,
    poll_ms: int = 200,
    max_wait_ms: int = 45000,
) -> StableResponse:
    start = time.perf_counter()
    last_text = ""
    stable_since: float | None = None
    stream_detected = False
    partial = False

    async def _read_assistant_text() -> str:
        if assistant_selector:
            try:
                loc = _resolve_locator(page, widget, assistant_selector)
                if await loc.count() > 0:
                    return (await loc.last.inner_text()).strip()
            except Exception:
                pass
        # Fallback: last message-like elements near chat
        script = """
        () => {
          const sels = [
            '[class*="message"]', '[class*="assistant"]', '[data-role="assistant"]',
            '.bot-message', '[class*="response"]', '[class*="reply"]'
          ];
          let best = '';
          for (const sel of sels) {
            document.querySelectorAll(sel).forEach(el => {
              const t = (el.textContent || '').trim();
              if (t.length > best.length) best = t;
            });
          }
          if (best) return best;
          const all = document.body.innerText || '';
          return all.split('\\n').filter(l => l.trim()).slice(-3).join('\\n');
        }
        """
        try:
            return (await page.evaluate(script) or "").strip()
        except Exception:
            return ""

    while True:
        elapsed_ms = (time.perf_counter() - start) * 1000
        if elapsed_ms >= max_wait_ms:
            partial = True
            break

        try:
            typing_clear = await page.evaluate(STREAM_DONE_SCRIPT, TYPING_SELECTORS)
        except Exception:
            typing_clear = True

        text = await _read_assistant_text()
        if text != last_text:
            stream_detected = True
            last_text = text
            stable_since = None
        elif typing_clear and text:
            if stable_since is None:
                stable_since = time.perf_counter()
            elif (time.perf_counter() - stable_since) * 1000 >= stable_ms:
                break
        elif not text and elapsed_ms > 3000 and not stream_detected:
            # No response yet — keep waiting unless timeout
            pass

        await page.wait_for_timeout(poll_ms)

    wait_ms = (time.perf_counter() - start) * 1000
    complete = not partial and bool(last_text)
    return StableResponse(
        text=last_text,
        complete=complete,
        wait_ms=round(wait_ms, 1),
        stream_detected=stream_detected,
        partial=partial and bool(last_text),
    )


def _resolve_locator(page: Any, widget: WidgetCandidate, selector: str) -> Any:
    if widget.frame_path:
        fl = page
        for idx in widget.frame_path:
            fl = fl.frame_locator(f"iframe >> nth={idx}")
        return fl.locator(selector)
    return page.locator(selector)
