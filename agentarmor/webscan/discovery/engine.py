"""Discovery engine — widget + capability intelligence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agentarmor.core.config import AppConfig
from agentarmor.webscan.discovery.capability_map import build_capability_map
from agentarmor.webscan.discovery.dom_scanner import DOM_SCAN_SCRIPT, IFRAME_SCAN_SCRIPT
from agentarmor.webscan.discovery.framework import (
    boost_candidates_for_framework,
    detect_framework,
    get_chat_keywords,
)
from agentarmor.webscan.models import DiscoveryResult, WidgetCandidate


def _raw_to_candidate(raw: dict[str, Any], framework_name: str | None = None) -> WidgetCandidate:
    return WidgetCandidate(
        input_selector=raw.get("input_selector", ""),
        send_selector=raw.get("send_selector"),
        frame_path=list(raw.get("frame_path") or []),
        confidence=float(raw.get("confidence", 0)),
        framework=framework_name,
        score_breakdown=dict(raw.get("score_breakdown") or {}),
        tag_name=raw.get("tag_name", ""),
        placeholder=raw.get("placeholder", ""),
    )


async def discover_widget(page: Any, page_url: str) -> DiscoveryResult:
    """Layer 1+2 widget discovery."""
    import json

    keywords = get_chat_keywords()
    keywords_js = json.dumps(keywords)

    dom_script = DOM_SCAN_SCRIPT.replace("%KEYWORDS%", keywords_js)
    raw_dom: list[dict] = await page.evaluate(dom_script)
    raw_iframe: list[dict] = await page.evaluate(IFRAME_SCAN_SCRIPT, keywords_js)

    framework = await detect_framework(page)
    fw_name = framework.get("name") if framework else None

    seen: set[str] = set()
    candidates: list[WidgetCandidate] = []
    for raw in raw_dom + raw_iframe:
        sel = raw.get("input_selector", "")
        if not sel or sel in seen:
            continue
        seen.add(sel)
        candidates.append(_raw_to_candidate(raw, fw_name))

    candidates = boost_candidates_for_framework(candidates, framework)
    candidates.sort(key=lambda c: c.confidence, reverse=True)

    widget = candidates[0] if candidates and candidates[0].confidence >= 0.2 else None
    if widget and fw_name:
        widget.framework = fw_name

    return DiscoveryResult(
        page_url=page_url,
        widget=widget,
        framework=fw_name,
        candidates=candidates[:5],
    )


async def discover_full(
    page: Any,
    page_url: str,
    network_log: list[dict[str, Any]],
    config: AppConfig,
    *,
    use_llm_discovery: bool = False,
) -> DiscoveryResult:
    """Widget discovery plus capability map and agent risk profile."""
    result = await discover_widget(page, page_url)

    needs_llm = use_llm_discovery and (
        not result.widget or result.widget.confidence < config.webscan.llm_discovery_min_confidence
    )
    if needs_llm:
        from agentarmor.webscan.discovery.llm_classifier import refine_widget_with_llm

        refined = await refine_widget_with_llm(page, result.candidates, config)
        if refined:
            result.widget = refined
            if result.candidates:
                result.candidates = [refined] + [c for c in result.candidates if c.input_selector != refined.input_selector]

    cap, profile, _tools = await build_capability_map(
        page,
        network_log,
        page_url,
        result.framework,
        config,
    )
    result.capability_map = cap
    result.agent_risk = profile
    return result


async def screenshot_page(page: Any, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    await page.screenshot(path=str(path), full_page=False)
    return str(path)
