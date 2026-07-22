@echo off
title 宝宝量化系统 — 本地数据平台
chcp 65001 >nul

set "DIR=%~dp0"
cd /d "%DIR%"

:menu
cls
echo ╔══════════════════════════════════════════╗
echo ║       宝宝量化系统 — 本地数据平台       ║
echo ║         双击一下，数据更新                ║
echo ╚══════════════════════════════════════════╝
echo.
echo   [1] 📦 一键更新 Dashboard
echo   [2] 📊 数据状态
echo   [3] 🌐 打开本地网页
echo   [4] 📈 回补K线数据
echo   [5] 🧹 清理打包临时文件
echo   [Q] ❌ 退出
echo.

choice /c 12345Q /n /m "请选择 (1-5/Q): "
if errorlevel 6 goto end
if errorlevel 5 goto clean
if errorlevel 4 goto backfill
if errorlevel 3 goto openweb
if errorlevel 2 goto status
if errorlevel 1 goto update
goto end

:update
cls
echo.
echo ══════════════════════════════════════════
echo   📦 正在更新 Dashboard（数据自动缓存）
echo ══════════════════════════════════════════
wsl python3 /home/ran/.hermes/scripts/update_dashboard.py
echo.
echo ══════════════════════════════════════════
echo   ✅ 更新完成！按任意键返回菜单
pause >nul
goto menu

:status
cls
echo.
echo ══════════════════════════════════════════
echo   📊 数据状态
echo ══════════════════════════════════════════
wsl python3 -c ^
"import sys; sys.path.insert(0,'/mnt/c/Users/Administrator/Desktop/A股报告'); from db_manager import DB; import os; db=DB();st=db.stats(); tot=0; tbl=['index_daily','stock_daily','picks_history','sector_daily','mood_daily']; nm=['📈 大盘指数','📊 个股日线','🏆 推荐记录','🏭 板块行情','🧠 情绪评分']; [print(f\"  {nm[i]:10s} {st[t]['count']:5d}条  {st[t].get('earliest','--') or '--'} ~ {st[t].get('latest','--') or '--'}\") or tot:=tot+st[t]['count'] for i,t in enumerate(tbl)]; print(f'\n  📦 总计 {tot} 条记录 | DB大小: {os.path.getsize(db.db_path)/1024:.0f} KB')"
echo.
echo 按任意键返回菜单
pause >nul
goto menu

:openweb
start "" "%DIR%dashboard.html"
echo 🌐 已打开本地Dashboard
timeout /t 2 >nul
goto menu

:backfill
cls
echo.
echo ══════════════════════════════════════════
echo   📈 正在回补历史K线数据
echo ══════════════════════════════════════════
wsl python3 /mnt/c/Users/Administrator/Desktop/A股报告/backfill_history.py
echo.
echo ✅ 回补完成！按任意键返回菜单
pause >nul
goto menu

:clean
cls
echo.
echo 🧹 清理打包临时文件...
rmdir /s /q "%DIR%build" 2>nul
rmdir /s /q "%DIR%__pycache__" 2>nul
del /q "%DIR%*.spec" 2>nul
del /q "%DIR%宝宝量化系统" 2>nul
echo ✅ 清理完成！
timeout /t 2 >nul
goto menu

:end
exit
