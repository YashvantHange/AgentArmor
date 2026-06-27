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

WIDGET_ROOT_SCRIPT = """
(inputSelector) => {
  const input = document.querySelector(inputSelector);
  if (!input) return null;
  const chatRoot = input.closest('[class*="chat-content"], [class*="first-page"], [class*="conversation"]');
  if (chatRoot) return chatRoot;

  let best = null;
  let cur = input.parentElement;
  for (let i = 0; i < 12 && cur; i++) {
    const hasMessages = cur.querySelector && cur.querySelector(
      '[class*="message"], [class*="assistant"], .bg-ai-message-bg, [class*="chat-content"], [class*="bot-message"]'
    );
    const len = (cur.innerText || '').length;
    if (hasMessages) best = cur;
    else if (len > 200 && len < 8000) best = cur;
    cur = cur.parentElement;
  }
  if (best) return best;
  return input.closest('[class*="chat"], [id*="chat"], form, main, section, .app')
    || input.parentElement?.parentElement?.parentElement;
}
"""

WIDGET_BASELINE_LINES_SCRIPT = """
(inputSelector) => {
  const root = (%ROOT_FN%)(inputSelector);
  if (!root) return [];
  return (root.innerText || '').split('\\n').map(s => s.trim()).filter(s => s.length >= 8);
}
""".replace("%ROOT_FN%", WIDGET_ROOT_SCRIPT.strip())

WIDGET_NEW_RESPONSE_SCRIPT = """
(args) => {
  const inputSelector = args[0];
  const baseline = new Set(args[1] || []);
  const prompt = (args[2] || '').trim();
  const root = (%ROOT_FN%)(inputSelector);
  if (!root) return '';

  const skipRe = /privacy|contact|partnership|careers|documentation|sign up|book a demo|email address|validate|play agent|share gandalf|leaderboard|made by lakera|company or institution/i;
  const staticRe = /ask me for the password|ask gandalf a question|enter the secret password|levels passed|your goal is to make gandalf|memebership cards upload|welcome to prompt airlines/i;

  const sels = ['[class*="message"]', '[class*="assistant"]', '[data-role="assistant"]', '.bot-message', '[class*="response"]', '[class*="reply"]', '.bg-ai-message-bg', '[class*="ai-message"]'];
  for (const sel of sels) {
    const els = root.querySelectorAll(sel);
    for (let i = els.length - 1; i >= 0; i--) {
      const el = els[i];
      const cls = String(el.className || '');
      if (/human|user-message|human-message/i.test(cls)) continue;
      const t = (el.textContent || '').trim();
      if (t.length >= 8 && t !== prompt && !baseline.has(t) && !skipRe.test(t) && !staticRe.test(t)) return t;
    }
  }

  const lines = (root.innerText || '').split('\\n').map(s => s.trim()).filter(s => s.length >= 8);
  for (let i = lines.length - 1; i >= 0; i--) {
    const t = lines[i];
    if (t === prompt || baseline.has(t) || skipRe.test(t) || staticRe.test(t)) continue;
    return t;
  }
  return '';
}
""".replace("%ROOT_FN%", WIDGET_ROOT_SCRIPT.strip())


async def capture_baseline_lines(page: Any, widget: WidgetCandidate) -> list[str]:
    try:
        lines = await page.evaluate(WIDGET_BASELINE_LINES_SCRIPT, widget.input_selector)
        return list(lines) if isinstance(lines, list) else []
    except Exception:
        return []


async def wait_stable_response(
    page: Any,
    widget: WidgetCandidate,
    *,
    assistant_selector: str | None = None,
    stable_ms: int = 1500,
    poll_ms: int = 200,
    max_wait_ms: int = 45000,
    baseline_lines: list[str] | None = None,
    prompt_text: str = "",
) -> StableResponse:
    start = time.perf_counter()
    last_text = ""
    stable_since: float | None = None
    stream_detected = False
    partial = False
    baseline = baseline_lines or []

    async def _read_assistant_text() -> str:
        if assistant_selector:
            try:
                loc = _resolve_locator(page, widget, assistant_selector)
                if await loc.count() > 0:
                    return (await loc.last.inner_text()).strip()
            except Exception:
                pass
        try:
            text = await page.evaluate(
                WIDGET_NEW_RESPONSE_SCRIPT,
                [widget.input_selector, baseline, prompt_text],
            )
            return (text or "").strip()
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
            if text:
                stream_detected = True
            last_text = text
            stable_since = None
        elif typing_clear and text:
            if stable_since is None:
                stable_since = time.perf_counter()
            elif (time.perf_counter() - stable_since) * 1000 >= stable_ms:
                break
        elif not text and elapsed_ms > 3000 and not stream_detected:
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
