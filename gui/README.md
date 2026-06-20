# AgentArmor Desktop GUI

Tauri v2 + React + TypeScript + Tailwind desktop app.

## Development

Terminal 1 — API sidecar:

```bash
pip install -e ".[dev]"
agentarmor serve --port 8787
```

Terminal 2 — GUI:

```bash
cd gui
npm install
npm run dev
```

Open http://localhost:1420 (Vite dev server; API at :8787).

## Tauri desktop

```bash
cd gui
npm install
npm run tauri dev
```

The Tauri shell spawns `python -m agentarmor.cli.main serve` on launch.

## Windows release build

```powershell
pip install -e .
agentarmor models download
powershell -File packaging/build-installer.ps1
```

Artifacts: `gui/src-tauri/target/release/bundle/`

## Screens

| Screen | Route | Description |
|--------|-------|-------------|
| Home | `/` | Scan type picker + benchmark shortcut |
| Scan Config | `/scan/:type` | Target configuration form |
| Progress | `/progress/:id` | SSE live probe events |
| Findings | `/findings/:id` | OWASP-tagged results |
| Reports | `/reports/:id` | Export paths (HTML/SARIF/PDF) |
| Benchmark | `/benchmark` | Multi-provider leaderboard |
| Settings | `/settings` | Portable mode, L5 judge, paths |
