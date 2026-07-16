@echo off
cd /d C:\Users\Administrator\Desktop\A股报告
title A股监控Dashboard
echo ========================================
echo   A股监控 Dashboard 启动器 v1.0
echo ========================================
echo.
echo 正在启动本地服务...
start /B python3 C:\Users\Administrator\Desktop\A股报告\dashboard_server.py
timeout /t 3 /nobreak >nul
echo.
echo 正在建立公网隧道...
echo 请在打开的浏览器窗口中按提示操作
echo.
wsl.exe -d Ubuntu -e ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30 -i ~/.ssh/id_rsa -R astock:80:localhost:8890 serveo.net
echo.
pause
