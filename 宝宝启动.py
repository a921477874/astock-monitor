#!/usr/bin/env python3
"""
宝宝量化系统 — 快捷启动程序
===========================
一键更新dashboard，数据优先用本地SQLite。

用法:
    python3 宝宝启动.py          # 更新dashboard + 展示数据状态
    python3 宝宝启动.py --full   # 更新 + 回补K线
    python3 宝宝启动.py --status # 只看数据状态
"""

import os
import sys
import json
import re
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db_manager import DB

DESKTOP = os.path.dirname(os.path.abspath(__file__))
DASHBOARD_PATH = os.path.join(DESKTOP, "dashboard.html")

def main():
    args = sys.argv[1:]
    
    print("╔══════════════════════════════════╗")
    print("║   宝宝量化系统 — 本地数据平台   ║")
    print("╚══════════════════════════════════╝")
    
    if "--status" in args:
        show_status()
        return
    
    if "--full" in args:
        # 全量：更新 + 回补
        print("\n📦 正在更新Dashboard...")
        os.system(f"python3 /home/ran/.hermes/scripts/update_dashboard.py")
        print("\n📈 正在回补K线...")
        os.system(f"python3 {DESKTOP}/backfill_history.py")
    else:
        print("\n📦 更新Dashboard（数据优先从本地读取）...")
        os.system(f"python3 /home/ran/.hermes/scripts/update_dashboard.py")
    
    show_status()

    # 提示桌面快捷方式
    print("\n💡 提示: 在Windows桌面上双击「宝宝量化系统.bat」即可运行")

def show_status():
    db = DB()
    st = db.stats()
    
    print(f"\n{'=' * 50}")
    print(f"  📊 market_data.db  — 本地数据仓库")
    print(f"{'=' * 50}")
    
    total_records = 0
    for tbl, info in st.items():
        if tbl == 'stock_weekly': continue
        total_records += info['count']
        name = tbl.replace('_', ' ').title()
        status = "✅" if info['count'] > 0 else "⬜"
        count_str = f"{info['count']:5d}条"
        period = f"{info.get('earliest','--') or '--'} → {info.get('latest','--') or '--'}" if info.get('earliest') else "⚠️ 空"
        print(f"  {status} {name:18s} {count_str}  {period}")
    
    print(f"{'=' * 50}")
    print(f"  📦 总计 {total_records} 条记录 | 文件: {os.path.getsize(db.db_path)/1024:.0f} KB")
    
    # 检查dashboard是否可用
    if os.path.exists(DASHBOARD_PATH):
        mtime = datetime.fromtimestamp(os.path.getmtime(DASHBOARD_PATH))
        size = os.path.getsize(DASHBOARD_PATH)
        print(f"  📄 dashboard.html ({size/1024:.0f} KB) — 更新于 {mtime.strftime('%Y-%m-%d %H:%M')}")
        
        # 检查DAILY_REPORT日期
        try:
            with open(DASHBOARD_PATH) as f:
                h = f.read()
            m = re.search(r'const DAILY_REPORT = ({.*?});', h, re.DOTALL)
            if m:
                dr = json.loads(m.group(1))
                print(f"  🎯 面板数据日期: {dr.get('date','?')} | 评分: {dr.get('moodCycle',{}).get('score','?')}")
        except:
            pass
    
    print(f"{'=' * 50}")
    print(f"  提示: 网络正常时自动拉最新数据并缓存")
    print(f"       断网时自动使用本地缓存数据")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()
