# AgentArmor Windows packaging

## Desktop bundle pipeline

```
embed-python/download.ps1     → Download Python 3.12 embeddable zip
setup-embed-python.ps1        → pip install agentarmor + models into embed
bundle-models.ps1             → Copy ONNX models to Tauri resources/models
build-installer.ps1           → Full MSI/NSIS via Tauri
build-portable.ps1            → Unpacked portable folder
```

## Requirements

- Node.js 20+, Rust stable, PowerShell 5+
- ~2 GB disk for embed Python + models
- Windows for installer builds (or use `release.yml` windows-gui job)

## Portable vs installed

| Mode | Data location |
|------|----------------|
| Installed | `%APPDATA%\AgentArmor\` (default) |
| Portable | `./data/` next to `AgentArmor.exe` |

Web scans require Playwright Chromium. The installer bundle includes browsers under `resources/playwright/` (~150–200 MB).

Set portable via GUI Settings or env `AGENTARMOR_PORTABLE=1`.

## CI secrets (release.yml)

| Secret | Purpose |
|--------|---------|
| `PYPI_API_TOKEN` | PyPI publish on `v*` tag |
| `DOCKERHUB_USERNAME` | Docker Hub login |
| `DOCKERHUB_TOKEN` | Docker Hub push |

## Icon

Before first Tauri build, generate icons:

```bash
cd gui
npm run tauri icon ../packaging/icon.png   # add a 1024x1024 PNG first
```

## Verification checklist

- [ ] `packaging/build-installer.ps1` on clean Windows VM
- [ ] Double-click MSI → GUI opens without system Python
- [ ] Run endpoint scan offline (L5 judge off)
- [ ] `docker build -f docker/Dockerfile .` succeeds
- [ ] Tag `v1.0.0` with secrets configured → PyPI + Docker publish
