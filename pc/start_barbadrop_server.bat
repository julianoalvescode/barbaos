@echo off
title BarbaDrop server
REM Shares the "games" folder next to this file with BarbaDrop on the console.
REM Requires Python 3 (https://www.python.org). Allow access when Windows Firewall asks.
python "%~dp0barbadrop_server.py" %*
if errorlevel 1 (
  echo.
  echo Python was not found. Install it from https://www.python.org and tick "Add python.exe to PATH".
)
pause
