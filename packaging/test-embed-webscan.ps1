# Smoke test embedded Python + Playwright for web scans.
# Run from repo root after setup-embed-python.ps1

param(
    [string]$EmbedRoot = (Join-Path $PSScriptRoot "embed-python\python")
)

$ErrorActionPreference = "Stop"

$python = Join-Path $EmbedRoot "python.exe"
if (-not (Test-Path $python)) {
    Write-Error "Embedded python not found at $python. Run setup-embed-python.ps1 first."
    exit 1
}

$playwrightDir = Join-Path (Split-Path $PSScriptRoot -Parent) "gui\src-tauri\resources\playwright"
if (Test-Path $playwrightDir) {
    $env:PLAYWRIGHT_BROWSERS_PATH = $playwrightDir
}

Write-Host "Checking agentarmor webscan imports..."
& $python -c "from agentarmor.webscan.browser.pool import playwright_available; from agentarmor.webscan.planning.attack_planner import plan_web_attack; print('imports_ok', playwright_available())"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Checking Playwright chromium launch..."
& $python -c @"
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content('<html><body>ok</body></html>')
        assert 'ok' in await page.content()
        await browser.close()
    print('chromium_ok')

asyncio.run(main())
"@
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "test-embed-webscan: PASS"
