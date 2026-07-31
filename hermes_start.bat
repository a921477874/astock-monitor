@echo off
REM 开机自启WSL并拉起Hermes cron调度器
REM 由Hermes Agent自动创建

REM 启动WSL（如果没在运行的话）
wsl -d Ubuntu -- cd ~ && nohup hermes cron start > /dev/null 2>&1 &

REM 等待WSL就绪
timeout /t 3 /nobreak >nul

REM 再确认一次cron运行
wsl -d Ubuntu -- hermes cron status 2>nul || wsl -d Ubuntu -- hermes cron start 2>nul
