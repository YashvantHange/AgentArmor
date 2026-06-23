"""Layer 3 LLM widget discovery — cloud-assisted chat input detection."""

from __future__ import annotations

import json
import time
from typing import Any

from agentarmor.core.config import AppConfig
from agentarmor.webscan.models import WidgetCandidate

WIDGET_CLASSIFIER_SYSTEM = """You locate embedded chat widget input fields on web pages from a DOM summary.
You do NOT execute attacks. Output valid JSON only:
{"input_selector": "css selector", "send_selector": "css selector or null", "confidence": 0.0-1.0, "rationale": "..."}
Use valid CSS selectors present in the summary. If no chat widget exists, set input_selector to "" and confidence to 0."""

DOM_SUMMARY_SCRIPT = """
() => {
  const inputs = [];
  document.querySelectorAll('textarea, input[type="text"], input:not([type]), [contenteditable="true"]').forEach(el => {
    const tag = el.tagName.toLowerCase();
    const id = el.id ? '#' + el.id : '';
    const cls = el.className && typeof el.className === 'string'
      ? '.' + el.className.trim().split(/\\s+/).slice(0, 3).join('.')
      : '';
    const ph = el.getAttribute('placeholder') || el.getAttribute('aria-label') || '';
    inputs.push({ tag, id, cls, placeholder: ph.slice(0, 80) });
  });
  const buttons = [];
  document.querySelectorAll('button, [role="button"]').forEach(el => {
    const t = (el.textContent || '').trim().slice(0, 40);
    if (t) buttons.push(t);
  });
  return { inputs: inputs.slice(0, 15), buttons: buttons.slice(0, 10), title: document.title };
}
"""


def _parse_classifier_json(raw: str) -> dict[str, Any] | None:
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


async def refine_widget_with_llm(
    page: Any,
    candidates: list[WidgetCandidate],
    config: AppConfig,
) -> WidgetCandidate | None:
    """Use cloud LLM to pick a chat input when heuristics are weak or empty."""
    agentic = config.detection.agentic
    if config.detection.analysis_mode != "cloud" or not agentic.enabled:
        return None
    api_key = agentic.api_key or ""
    if not api_key:
        return None

    summary: dict[str, Any] = await page.evaluate(DOM_SUMMARY_SCRIPT)
    cand_lines = [
        f"- {c.input_selector} (confidence={c.confidence:.2f}, placeholder={c.placeholder!r})"
        for c in candidates[:8]
    ]
    user = (
        f"page_title: {summary.get('title', '')}\n"
        f"dom_inputs: {json.dumps(summary.get('inputs', []))[:2000]}\n"
        f"buttons: {json.dumps(summary.get('buttons', []))[:500]}\n"
        f"heuristic_candidates:\n" + ("\n".join(cand_lines) if cand_lines else "none")
    )

    import litellm

    model = agentic.model
    if "/" not in model:
        model = f"{agentic.provider}/{model}"

    start = time.perf_counter()
    try:
        completion = await litellm.acompletion(
            model=model,
            api_key=api_key or None,
            messages=[
                {"role": "system", "content": WIDGET_CLASSIFIER_SYSTEM},
                {"role": "user", "content": user},
            ],
            temperature=0.0,
            max_tokens=400,
        )
        content = (completion.choices[0].message.content or "").strip()
        parsed = _parse_classifier_json(content)
        if not parsed:
            return None
        selector = str(parsed.get("input_selector", "")).strip()
        confidence = float(parsed.get("confidence", 0))
        if not selector or confidence < 0.25:
            return None
        send_sel = parsed.get("send_selector")
        return WidgetCandidate(
            input_selector=selector,
            send_selector=str(send_sel) if send_sel else None,
            confidence=min(1.0, confidence),
            score_breakdown={"llm_layer3": confidence, "latency_ms": round((time.perf_counter() - start) * 1000, 1)},
        )
    except Exception:
        return None
