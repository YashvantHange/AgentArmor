# Embed Python 3.12 for Windows desktop bundle.
# Download from https://www.python.org/downloads/windows/ (embeddable package)
# Extract to packaging/embed-python/python/

param(
    [string]$PythonEmbedUrl = "https://www.python.org/ftp/python/3.12.7/python-3.12.7-embed-amd64.zip"
)

$ErrorActionPreference = "Stop"
# Script lives in packaging/embed-python/ - always extract to ./python/
$EmbedBase = $PSScriptRoot
$PythonDir = Join-Path $EmbedBase "python"
New-Item -ItemType Directory -Force -Path $PythonDir | Out-Null
$zip = Join-Path $EmbedBase "python-embed.zip"
Write-Host "Downloading embeddable Python to $PythonDir ..."
Invoke-WebRequest -Uri $PythonEmbedUrl -OutFile $zip
Expand-Archive -Path $zip -DestinationPath $PythonDir -Force
Remove-Item $zip
$pythonExe = Join-Path $PythonDir "python.exe"
if (-not (Test-Path $pythonExe)) {
    Write-Error "python.exe not found after extract; check zip layout at $PythonDir"
}
Write-Host "Embedded Python ready at $PythonDir"
