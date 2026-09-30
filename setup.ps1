$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path .venv\Scripts\python.exe)) {
    py -3.11 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.11 from python.org (including Tcl/Tk and launcher).' }
}
& .venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
foreach ($Folder in @('documents','data','runtime')) { New-Item -ItemType Directory -Force $Folder | Out-Null }
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
if (-not (Test-Path services.json)) { Copy-Item services.example.json services.json }
Write-Host 'Ready. Edit .env and services.json, then run launch.cmd.'
