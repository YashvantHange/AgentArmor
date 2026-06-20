# Prepare embeddable Python with pip + agentarmor for desktop bundle.
# Run from repo root after packaging/embed-python/download.ps1

param(
    [string]$EmbedRoot = (Join-Path $PSScriptRoot "embed-python\python"),
    [string]$RepoRoot = "$PSScriptRoot\.."
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
    & "$EmbedRoot\python.exe" -m pip install --upgrade pip wheel
    & "$EmbedRoot\python.exe" -m pip install ".[ml]" --no-warn-script-location
    & "$EmbedRoot\python.exe" -m agentarmor.cli.main models download
} finally {
    Pop-Location
}

# Stage for Tauri resources
$Dest = Join-Path $RepoRoot "gui\src-tauri\resources\python"
if (Test-Path $Dest) { Remove-Item $Dest -Recurse -Force }
Copy-Item -Path $EmbedRoot -Destination $Dest -Recurse
Write-Host "Embedded Python + agentarmor staged at $Dest"
