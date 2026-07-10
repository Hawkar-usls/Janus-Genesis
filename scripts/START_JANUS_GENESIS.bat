@echo off
setlocal
cd /d "%~dp0\.."
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0START_JANUS_GENESIS.ps1"
if errorlevel 1 pause
endlocal
