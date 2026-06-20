# Build portable Windows folder (unpacked exe + resources, no MSI)

param(
    [string]$OutDir = "$PSScriptRoot\..\dist-portable"
)

$ErrorActionPreference = "Stop"
& "$PSScriptRoot\build-installer.ps1"

$release = Resolve-Path "$PSScriptRoot\..\gui\src-tauri\target\release"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Copy-Item "$release\agentarmor.exe" $OutDir -Force -ErrorAction SilentlyContinue
Copy-Item "$release\*.dll" $OutDir -Force -ErrorAction SilentlyContinue

$resources = "$PSScriptRoot\..\gui\src-tauri\resources"
if (Test-Path $resources) {
    Copy-Item $resources (Join-Path $OutDir "resources") -Recurse -Force
}

# Portable marker
Set-Content -Path (Join-Path $OutDir "PORTABLE") -Value "1"

Write-Host "Portable build: $OutDir"
Write-Host "Run: .\agentarmor.exe  (data stored in .\data\)"
