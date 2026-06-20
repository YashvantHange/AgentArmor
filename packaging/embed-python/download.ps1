# Embed Python 3.12 for Windows desktop bundle.
# Download from https://www.python.org/downloads/windows/ (embeddable package)
# Extract to packaging/embed-python/python/

param(
    [string]$PythonEmbedUrl = "https://www.python.org/ftp/python/3.12.7/python-3.12.7-embed-amd64.zip",
    [string]$Dest = "$PSScriptRoot/embed-python"
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
$zip = Join-Path $Dest "python-embed.zip"
Write-Host "Downloading embeddable Python..."
Invoke-WebRequest -Uri $PythonEmbedUrl -OutFile $zip
Expand-Archive -Path $zip -DestinationPath (Join-Path $Dest "python") -Force
Remove-Item $zip
Write-Host "Embedded Python ready at $Dest/python"
