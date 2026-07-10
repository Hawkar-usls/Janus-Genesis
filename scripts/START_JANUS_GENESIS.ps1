$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    py -3.11 -m venv .venv
}

& ".venv\Scripts\python.exe" -m pip install -e .
& ".venv\Scripts\janus-genesis.exe" init-workspace
& ".venv\Scripts\janus-genesis.exe" run

Write-Host ""
Write-Host "Janus Genesis finished. Check workspace/outbox and workspace/reports."
