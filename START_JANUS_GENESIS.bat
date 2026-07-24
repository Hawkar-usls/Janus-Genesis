@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0START_JANUS_GENESIS.ps1"
if errorlevel 1 (
  echo.
  echo Janus Genesis stopped with an error.
  pause
)
