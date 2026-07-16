@echo off
cd /d C:\Users\Administrator\Desktop\A股报告
echo 启动A股Dashboard服务器...
echo.
echo 在手机上浏览器访问: http://你的电脑IP:8888/dashboard.html
echo.
echo 按 Ctrl+C 停止服务器
echo ========================================
python -m http.server 8888
pause
