# Smoke test embedded Python red-team agents.
param(
    [string]$EmbedRoot = (Join-Path $PSScriptRoot "embed-python\python"),
    [string]$ResourcesPython = (Join-Path $PSScriptRoot "..\gui\src-tauri\resources\python")
)

$ErrorActionPreference = "Stop"
$python = Join-Path $EmbedRoot "python.exe"
if (-not (Test-Path $python) -and (Test-Path (Join-Path $ResourcesPython "python.exe"))) {
    $python = Join-Path $ResourcesPython "python.exe"
}
if (-not (Test-Path $python)) {
    Write-Error "Embedded python not found at $python. Run setup-embed-python.ps1 first."
}

Write-Host "Checking redteam skills + registry from embed Python..."
& $python -c @"
from agentarmor.redteam.skills.loader import load_skills
from agentarmor.redteam.agents.registry import resolve_agent
skills = load_skills()
assert len(skills) >= 13, len(skills)
assert resolve_agent('memory_poison').agent_id == 'memory'
assert resolve_agent('model_theft').agent_id == 'llm10'
print('redteam_embed_ok', len(skills))
"@

if ($LASTEXITCODE -ne 0) { throw "redteam embed smoke failed" }
Write-Host "test-embed-redteam: PASS"
