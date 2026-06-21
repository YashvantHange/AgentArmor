# Build Windows MSI installer via Tauri (with embedded Python)

param(
    [string]$GuiDir = "$PSScriptRoot\..\gui",
    [switch]$SkipEmbed
)

$ErrorActionPreference = "Stop"

if (-not $SkipEmbed) {
    $embedPy = "$PSScriptRoot\embed-python\python\python.exe"
    if (-not (Test-Path $embedPy)) {
        Write-Host "Downloading embeddable Python..."
        & "$PSScriptRoot\embed-python\download.ps1"
    }
    Write-Host "Setting up embedded Python + agentarmor..."
    & "$PSScriptRoot\setup-embed-python.ps1"
}

& "$PSScriptRoot\bundle-models.ps1"

Write-Host "Generating application icon..."
python "$PSScriptRoot\generate-tauri-icon.py"

Push-Location $GuiDir
try {
    if (-not (Test-Path "src-tauri\icons\icon.ico")) {
        Write-Host "Building Tauri icon set from icon.png..."
        npx --yes @tauri-apps/cli icon src-tauri/icons/icon.png
    }
    npm install
    npm run tauri build
    Write-Host "Installer artifacts in gui/src-tauri/target/release/bundle/"
} finally {
    Pop-Location
}
