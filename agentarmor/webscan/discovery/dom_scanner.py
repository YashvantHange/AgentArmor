"""Layer 1 — fast DOM discovery via in-page JavaScript."""

from __future__ import annotations

DOM_SCAN_SCRIPT = """
() => {
  const KEYWORDS = %KEYWORDS%;
  const INPUT_SEL = 'input:not([type=hidden]):not([type=checkbox]):not([type=radio]), textarea, [contenteditable="true"], [role="textbox"]';

  function keywordScore(el) {
    const parts = [
      el.id || '',
      el.name || '',
      el.className || '',
      el.getAttribute('placeholder') || '',
      el.getAttribute('aria-label') || '',
      el.getAttribute('data-testid') || '',
    ].join(' ').toLowerCase();
    let score = 0;
    for (const kw of KEYWORDS) {
      if (parts.includes(kw)) score += 1.5;
    }
    const parent = el.closest('form, [class*="chat"], [class*="message"], [id*="chat"]');
    if (parent) {
      const pt = (parent.className || '') + (parent.id || '');
      for (const kw of KEYWORDS) {
        if (pt.toLowerCase().includes(kw)) score += 0.5;
      }
    }
    return score;
  }

  function cssPath(el) {
    if (el.id) return '#' + CSS.escape(el.id);
    const parts = [];
    let cur = el;
    while (cur && cur.nodeType === 1 && parts.length < 6) {
      let sel = cur.tagName.toLowerCase();
      if (cur.id) {
        parts.unshift('#' + CSS.escape(cur.id));
        break;
      }
      const parent = cur.parentElement;
      if (parent) {
        const siblings = Array.from(parent.children).filter(c => c.tagName === cur.tagName);
        if (siblings.length > 1) {
          sel += ':nth-of-type(' + (siblings.indexOf(cur) + 1) + ')';
        }
      }
      parts.unshift(sel);
      cur = parent;
    }
    return parts.join(' > ');
  }

  function isUploadButton(btn) {
    const blob = ((btn.id || '') + (btn.className || '') + (btn.getAttribute('aria-label') || '') + (btn.textContent || '')).toLowerCase();
    return /upload|attach|file|member|card|image|photo/.test(blob);
  }

  function findSendButton(input) {
    const form = input.closest('form');
    if (form) {
      const buttons = form.querySelectorAll('button[type="submit"], input[type="submit"], button:not([type="button"])');
      for (const btn of buttons) {
        if (!isUploadButton(btn)) return cssPath(btn);
      }
    }
    const container = input.closest('[class*="chat"], [class*="composer"], form, [role="form"]') || input.parentElement;
    if (container) {
      const buttons = container.querySelectorAll('button, [role="button"]');
      for (const b of buttons) {
        if (isUploadButton(b)) continue;
        const t = ((b.textContent || '') + (b.getAttribute('aria-label') || '')).toLowerCase();
        if (/send|submit|ask|go|enter|reply/.test(t)) return cssPath(b);
      }
      for (const b of buttons) {
        if (!isUploadButton(b) && b.type !== 'button') return cssPath(b);
      }
    }
    return null;
  }

  const results = [];
  document.querySelectorAll(INPUT_SEL).forEach(el => {
    const rect = el.getBoundingClientRect();
    if (rect.width < 20 || rect.height < 10) return;
    const style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return;
    const kw = keywordScore(el);
    let score = kw;
    if (el.tagName === 'TEXTAREA') score += 1;
    if (el.getAttribute('contenteditable') === 'true') score += 0.5;
    if (score < 0.5 && kw === 0) return;
    results.push({
      input_selector: cssPath(el),
      send_selector: findSendButton(el),
      confidence: Math.min(1, score / 5),
      score_breakdown: { keywords: kw, visibility: 1 },
      tag_name: el.tagName.toLowerCase(),
      placeholder: el.getAttribute('placeholder') || '',
      frame_path: [],
    });
  });
  results.sort((a, b) => b.confidence - a.confidence);
  return results.slice(0, 15);
}
"""

FRAMEWORK_DETECT_SCRIPT = """
(providers) => {
  const scripts = Array.from(document.querySelectorAll('script[src]')).map(s => s.src.toLowerCase());
  const html = document.documentElement.innerHTML.toLowerCase();
  let best = null;
  let bestScore = 0;
  for (const p of providers) {
    let score = 0;
    for (const pat of p.script_patterns || []) {
      if (scripts.some(s => s.includes(pat)) || html.includes(pat)) score += 2;
    }
    for (const sel of p.dom_selectors || []) {
      try {
        if (document.querySelector(sel)) score += 3;
      } catch (e) {}
    }
    for (const g of p.globals || []) {
      try {
        if (window[g] !== undefined) score += 4;
      } catch (e) {}
    }
    if (score > bestScore) {
      bestScore = score;
      best = { id: p.id, name: p.name, score };
    }
  }
  return best;
}
"""

IFRAME_SCAN_SCRIPT = """
(keywordsJson) => {
  const KEYWORDS = JSON.parse(keywordsJson);
  const results = [];

  function scanDoc(doc, framePath) {
    const INPUT_SEL = 'input:not([type=hidden]), textarea, [contenteditable="true"], [role="textbox"]';
    doc.querySelectorAll(INPUT_SEL).forEach(el => {
      const rect = el.getBoundingClientRect();
      if (rect.width < 20) return;
      const parts = [el.id, el.name, el.className, el.placeholder, el.getAttribute('aria-label')]
        .join(' ').toLowerCase();
      let kw = 0;
      for (const k of KEYWORDS) if (parts.includes(k)) kw += 1;
      if (kw === 0 && el.tagName !== 'TEXTAREA') return;
      let sel = el.id ? '#' + CSS.escape(el.id) : el.tagName.toLowerCase();
      results.push({
        input_selector: sel,
        send_selector: null,
        confidence: Math.min(1, (kw + 1) / 4),
        frame_path: framePath,
        tag_name: el.tagName.toLowerCase(),
        placeholder: el.getAttribute('placeholder') || '',
        score_breakdown: { keywords: kw, iframe: 1 },
      });
    });
    doc.querySelectorAll('iframe').forEach((iframe, idx) => {
      try {
        const inner = iframe.contentDocument;
        if (inner) scanDoc(inner, framePath.concat(String(idx)));
      } catch (e) {}
    });
  }
  scanDoc(document, []);
  return results.slice(0, 10);
}
"""
