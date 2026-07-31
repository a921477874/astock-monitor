@echo off
REM Auto-start Hermes Gateway (cron scheduler depends on it) - maintained by Hermes Agent
REM NOTE: cron jobs fire via GATEWAY, not 'cron start'. This bat starts the gateway.
REM Used by Windows Task Scheduler at logon, or double-click manually.

setlocal enabledelayedexpansion

REM 1. Make sure WSL is up, wait for it
wsl -d Ubuntu -- true 2>nul
timeout /t 4 /nobreak >nul

REM 2. Kill leftover gateway/tmux in WSL to avoid conflicts
wsl -d Ubuntu -- pkill -f "hermes gateway run" >nul 2>nul
wsl -d Ubuntu -- tmux kill-server >nul 2>nul

REM 3. Start gateway as a background tmux session (survives terminal close)
wsl -d Ubuntu -- bash -lc "tmux new-session -d -s hermes-gw '/home/ran/.hermes/bin/hermes gateway run 2>&1 | tee -a /home/ran/.hermes/logs/gateway.log'"

REM 4. Wait and health-check
timeout /t 8 /nobreak >nul
wsl -d Ubuntu -- bash -lc "/home/ran/.hermes/bin/hermes gateway status" 2>nul
echo.
echo Hermes Gateway started (tmux session: hermes-gw).
endlocal
