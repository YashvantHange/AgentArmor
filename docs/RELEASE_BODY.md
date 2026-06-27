## AgentArmor v1.2.2 — Website URL scan reliability

This patch release fixes live progress streaming and improves browser-based chatbot probing on public challenge sites.

### Fixed — Website URL scanning
- SSE heartbeats and discovery/planning progress events (no more false "Connection to scan stream lost" during long scans)
- Scan progress UI polls scan status when the event stream drops
- Playwright response capture: baseline diffing and chat-container detection for Gandalf / Prompt Airlines-style UIs
- Send-button heuristics skip upload/attach controls; browser session route guard fix
- SPA chat-input wait; default page timeout 60s; low-confidence widget fallback

### Added
- GUI disclaimer on website URL testing limits vs API endpoint scanning
- Framework selector hints for ChatGPT, Claude, Gemini
- Gandalf-like regression test fixture

---

## Windows (recommended)

Download **AgentArmor_*_x64-setup.exe** or **.msi** from the assets below.

1. Run the installer (or portable `.exe`)
2. Double-click **AgentArmor** — no Python install required
3. **Test my chatbot** → website URL or API URL → run scan → export reports

For login-required targets (ChatGPT, Claude), use **Login required (SSO)** in the website wizard.
