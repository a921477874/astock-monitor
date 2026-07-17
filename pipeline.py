#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
宝宝量化系统 - 主调度器 v2.0
统一管理所有数据模块的执行顺序:
  1. 跨市场预警 (global_mood.py)
  2. 市场情绪周期 (mood_cycle.py) 
  3. 板块资金热度 (sector_flow.py) — optional
  4. 产业新闻逻辑 (industry_news.py)
  5. 龙虎榜游资追踪 (dragon_tiger.py)
  6. 盘前精选选股 (closing_picks.py)
  7. 同步到网站 (dashboard + git push)

用法:
  python3 pipeline.py                    # 跑完整流程
  python3 pipeline.py --picks-only       # 只跑选股
  python3 pipeline.py --pre-market       # 只跑前置模块
"""

import json, os, sys, subprocess, time
from datetime import datetime

TOOLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools")
DESKTOP = os.path.dirname(os.path.abspath(__file__))
CP_PATH = os.path.expanduser("~/.hermes/scripts/closing_picks.py")
UD_PATH = os.path.expanduser("~/.hermes/scripts/update_dashboard.py")

PIPELINE = [
    {"name": "跨市场预警",   "script": "global_mood.py",   "timeout": 30, "optional": False},
    {"name": "市场情绪周期", "script": "mood_cycle.py",    "timeout": 90, "optional": False},
    {"name": "板块资金热度", "script": "sector_flow.py",   "timeout": 30, "optional": True},
    {"name": "产业新闻逻辑", "script": "industry_news.py", "timeout": 30, "optional": False},
    {"name": "龙虎榜游资",   "script": "dragon_tiger.py",  "timeout": 30, "optional": True},
]


def run_module(m):
    script = os.path.join(TOOLS_DIR, m["script"])
    if not os.path.exists(script):
        print(f"  ⚠️ 脚本不存在: {script}")
        return False
    st = time.time()
    try:
        r = subprocess.run(["python3", script], capture_output=True, text=True,
                           timeout=m["timeout"], cwd=DESKTOP)
        ok = r.returncode == 0
        print(f"  {'✅' if ok else '⚠️'} {m['name']} ({time.time()-st:.1f}s)")
        if not ok and not m["optional"]:
            return False
        return True
    except subprocess.TimeoutExpired:
        print(f"  ⏰ {m['name']} 超时")
        return m["optional"]
    except Exception as e:
        print(f"  ❌ {m['name']}: {e}")
        return m["optional"]


def run_pipeline(picks_only=False, pre_market=False):
    now = datetime.now()
    print(f"\n{'='*55}")
    print(f"  宝宝量化系统 v2.0 — {now.strftime('%m-%d %H:%M')}")
    print(f"{'='*55}")
    
    all_ok = True
    
    # Step 1~5: 前置数据模块
    if not picks_only:
        mode = "盘前数据预热" if pre_market else "数据采集"
        print(f"\n{'─'*30}\n  Step 1~5: {mode}\n{'─'*30}")
        for m in PIPELINE:
            if not run_module(m):
                if not m["optional"]:
                    all_ok = False
    
    if pre_market:
        print(f"\n{'='*55}\n  {'✅ 盘前数据就绪' if all_ok else '⚠️ 部分模块异常'}\n{'='*55}")
        return all_ok
    
    # Step 6: 选股
    print(f"\n{'─'*30}\n  Step 6: 选股引擎\n{'─'*30}")
    if os.path.exists(CP_PATH):
        st = time.time()
        try:
            r = subprocess.run(["python3", CP_PATH], capture_output=True, text=True,
                               timeout=180, cwd=DESKTOP)
            print(f"  {'✅' if r.returncode==0 else '⚠️'} 盘前精选 ({time.time()-st:.1f}s)")
            if r.returncode != 0:
                all_ok = False
        except subprocess.TimeoutExpired:
            print(f"  ⏰ 选股超时"); all_ok = False
        except Exception as e:
            print(f"  ❌ {e}"); all_ok = False
    else:
        print(f"  ⚠️ closing_picks.py 不存在"); all_ok = False
    
    # Step 7: 同步网站
    print(f"\n{'─'*30}\n  Step 7: 同步网站\n{'─'*30}")
    try:
        if os.path.exists(UD_PATH):
            r = subprocess.run(["python3", UD_PATH], capture_output=True, text=True,
                               timeout=45, cwd=DESKTOP)
            print(f"  {'✅' if r.returncode==0 else '⚠️'} Dashboard更新")
        subprocess.run(["cp", "dashboard.html", "index.html"], cwd=DESKTOP, capture_output=True)
        subprocess.run(["git", "add", "-A"], cwd=DESKTOP, capture_output=True, timeout=10)
        subprocess.run(["git", "commit", "-m", f"auto {now.strftime('%m-%d %H:%M')}"],
                       cwd=DESKTOP, capture_output=True, timeout=10)
        r = subprocess.run(["git", "push", "origin", "main"], cwd=DESKTOP,
                           capture_output=True, timeout=30)
        print(f"  {'✅ GitHub已同步' if r.returncode==0 else '⚠️ 推送: '+r.stderr.decode()[:60]}")
    except Exception as e:
        print(f"  ⚠️ 同步异常: {e}")
    
    print(f"\n{'='*55}\n  {'✅ 流程完成' if all_ok else '⚠️ 部分异常'}\n{'='*55}")
    return all_ok


if __name__ == "__main__":
    if "--picks-only" in sys.argv:
        run_pipeline(picks_only=True)
    elif "--pre-market" in sys.argv:
        run_pipeline(pre_market=True)
    else:
        run_pipeline()
