# Prepare embeddable Python with pip + agentarmor for desktop bundle.
# Run from repo root after packaging/embed-python/download.ps1

param(
    [string]$EmbedRoot = (Join-Path $PSScriptRoot "embed-python\python"),
    [string]$RepoRoot = "$PSScriptRoot\..",
    [string]$WheelPath = "",
    [switch]$SkipModelsDownload
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path "$EmbedRoot\python.exe")) {
    Write-Host "Embedded Python not found - running download.ps1 ..."
    & (Join-Path $PSScriptRoot "embed-python\download.ps1")
}
if (-not (Test-Path "$EmbedRoot\python.exe")) {
    Write-Error "python.exe missing at $EmbedRoot after download"
    exit 1
}

# Enable site-packages in embeddable Python
$pth = Get-ChildItem "$EmbedRoot\python*._pth" | Select-Object -First 1
if ($pth) {
    $lines = Get-Content $pth.FullName | ForEach-Object {
        if ($_ -match '^#import site') { 'import site' } else { $_ }
    }
    if ($lines -notcontains 'Lib\site-packages') {
        $lines += 'Lib\site-packages'
    }
    Set-Content -Path $pth.FullName -Value $lines
}

New-Item -ItemType Directory -Force -Path "$EmbedRoot\Lib\site-packages" | Out-Null

# Bootstrap pip
$getPip = Join-Path $EmbedRoot "get-pip.py"
if (-not (Test-Path $getPip)) {
    Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $getPip
}
& "$EmbedRoot\python.exe" $getPip --no-warn-script-location
Remove-Item $getPip -ErrorAction SilentlyContinue

# Install agentarmor into embed environment
Push-Location $RepoRoot
try {
    & "$EmbedRoot\python.exe" -m pip install --upgrade pip wheel setuptools hatchling
    if ($LASTEXITCODE -ne 0) { throw "pip bootstrap failed with exit code $LASTEXITCODE" }

    if ($WheelPath -and (Test-Path $WheelPath)) {
        Write-Host "Installing prebuilt wheel: $WheelPath"
        & "$EmbedRoot\python.exe" -m pip install $WheelPath --force-reinstall --no-warn-script-location
        & "$EmbedRoot\python.exe" -m pip install "playwright>=1.40.0" --no-warn-script-location
    } else {
        $dist = Join-Path $RepoRoot "dist"
        $wheel = Get-ChildItem -Path $dist -Filter "agentarmor-*.whl" -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1
        if (-not $wheel) {
            Write-Host "Building wheel with system Python..."
            python -m pip install --upgrade build hatchling -q
            if ($LASTEXITCODE -ne 0) { throw "system pip build tools failed" }
            python -m build --wheel
            if ($LASTEXITCODE -ne 0) { throw "python -m build --wheel failed" }
            $wheel = Get-ChildItem -Path $dist -Filter "agentarmor-*.whl" |
                Sort-Object LastWriteTime -Descending |
                Select-Object -First 1
        }
        if (-not $wheel) { throw "No agentarmor wheel found in dist/" }
        Write-Host "Installing wheel into embed Python: $($wheel.FullName)"
        $wheelWithExtras = "$($wheel.FullName)[ml,browser]"
        & "$EmbedRoot\python.exe" -m pip install $wheelWithExtras --force-reinstall --no-warn-script-location
    }
    if ($LASTEXITCODE -ne 0) { throw "pip install agentarmor failed with exit code $LASTEXITCODE" }
    & "$EmbedRoot\python.exe" -m pip install "playwright>=1.40.0" --no-warn-script-location
    if ($LASTEXITCODE -ne 0) { throw "pip install playwright failed with exit code $LASTEXITCODE" }
    $agentarmor = Join-Path $EmbedRoot "Scripts\agentarmor.exe"
    if (-not (Test-Path $agentarmor)) {
        throw "agentarmor.exe not found at $agentarmor after pip install"
    }

    # Bundle Chromium for web scans (~150-200 MB)
    $PlaywrightDest = Join-Path $RepoRoot "gui\src-tauri\resources\playwright"
    if (Test-Path $PlaywrightDest) { Remove-Item $PlaywrightDest -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $PlaywrightDest | Out-Null
    $env:PLAYWRIGHT_BROWSERS_PATH = $PlaywrightDest
    Write-Host "Installing Playwright Chromium into $PlaywrightDest ..."
    & "$EmbedRoot\python.exe" -m playwright install chromium
    if ($LASTEXITCODE -ne 0) { throw "playwright install chromium failed with exit code $LASTEXITCODE" }
    Write-Host "Playwright browsers staged at $PlaywrightDest"

    if (-not $SkipModelsDownload) {
        & $agentarmor models download
        if ($LASTEXITCODE -ne 0) { throw "agentarmor models download failed with exit code $LASTEXITCODE" }
    }
} finally {
    Pop-Location
}

# Stage for Tauri resources
$Dest = Join-Path $RepoRoot "gui\src-tauri\resources\python"
if (Test-Path $Dest) { Remove-Item $Dest -Recurse -Force }
Copy-Item -Path $EmbedRoot -Destination $Dest -Recurse
Write-Host "Embedded Python + agentarmor staged at $Dest"
