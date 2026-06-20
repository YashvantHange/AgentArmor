# Copy detection models into Tauri resources for offline desktop bundle.

param(
    [string]$ModelDir = "$env:USERPROFILE\.agentarmor\models",
    [string]$Dest = "$PSScriptRoot\..\gui\src-tauri\resources\models"
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $ModelDir)) {
    Write-Host "Run: agentarmor models download"
    exit 1
}
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
Copy-Item -Path "$ModelDir\*" -Destination $Dest -Recurse -Force
Write-Host "Models bundled to $Dest"
