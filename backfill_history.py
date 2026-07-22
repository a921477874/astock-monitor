#!/usr/bin/env python3
"""
宝宝量化系统 — 历史数据回补引擎
=================================
把已有的JSON数据写入SQLite，然后从腾讯K线接口回补历史日线。
首次运行：把所有已有的数据迁移到SQLite。
后续运行：补充缺失的交易日数据。

用法:
    python3 backfill_history.py          # 全量迁移+回补
    python3 backfill_history.py --quick  # 只迁移已有JSON文件，不回补K线
    python3 backfill_history.py --status # 只看状态
"""

import os
import json
import re
import sys
import subprocess as sp
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db_manager import DB

DESKTOP = "/mnt/c/Users/Administrator/Desktop/A股报告"

# 关注的个股代码
TRACKED_CODES = [
    "600519", "600036", "600276", "600584", "600900", "600030",
    "601318", "601899", "601088", "600028", "601857", "601766",
    "601668", "600547", "601398", "601012", "603501", "600309",
    "603993", "000333", "000002", "000725", "002594", "002475",
    "002371", "002230", "002415", "002714", "002241", "000063",
    "000858", "000651", "001979",
]


def run():
    db = DB()
    args = sys.argv[1:]

    if "--status" in args:
        print_status(db)
        return

    print("=" * 50)
    print("  宝宝量化系统 - 历史数据回补")
    print("=" * 50)

    # 1. 迁移JSON文件到SQLite
    print("\n📋 第一步：迁移已有JSON文件...")
    migrate_review_history(db)
    migrate_closing_picks(db)
    migrate_mood_score(db)
    migrate_history_json(db)

    # 2. 打印迁移后状态
    print("\n📊 迁移后状态：")
    print_status(db)

    if "--quick" in args:
        print("\n✅ 快速迁移完成（未回补K线）")
        return

    # 3. 回补K线
    print("\n📈 第二步：回补个股历史K线...")
    backfill_kline(db)

    # 4. 最终状态
    print("\n" + "=" * 50)
    print("  ✅ 数据回补完成")
    print("=" * 50)
    print_status(db)

    db.vacuum()
    print(f"\n📦 DB优化完成，最终大小: {os.path.getsize(db.db_path)/1024:.1f} KB")


def migrate_review_history(db):
    """复盘记录 → picks_history + stock_daily"""
    path = os.path.join(DESKTOP, ".review_history.json")
    if not os.path.exists(path):
        print("  ⬜ .review_history.json 不存在，跳过")
        return
    
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    count = 0
    if isinstance(data, list):
        for rec in data:
            date = rec.get("date", "")
            if not date: continue
            picks = rec.get("picks", [])
            for i, p in enumerate(picks):
                db.save_picks_history(
                    date, i+1, p.get("code", ""), p.get("name", ""),
                    score=p.get("score"), price_t0=p.get("rec_price", 0),
                    change_t1=p.get("today_change", 0),
                    outcome="涨" if p.get("verdict") == "✅ 涨" else ("跌" if p.get("verdict") == "❌ 跌" else "平"),
                )
                count += 1
    print(f"  ✅ picks_history: 迁移 {count} 条记录")


def migrate_closing_picks(db):
    """尾盘精选 → picks_history"""
    path = os.path.join(DESKTOP, ".closing_picks.json")
    if not os.path.exists(path):
        print("  ⬜ .closing_picks.json 不存在，跳过")
        return
    
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    date = data.get("date", "")
    top = data.get("top5") or data.get("top3") or []
    for i, p in enumerate(top):
        db.save_picks_history(
            date, i+1, p.get("code", ""), p.get("name", ""),
            score=p.get("score"), channel=p.get("channel", ""),
            price_t0=p.get("price", 0),
            stop_loss=p.get("stop_loss", 0),
            take_profit=p.get("take_profit", 0),
        )
    print(f"  ✅ closing_picks: 迁移 {len(top)} 条")


def migrate_mood_score(db):
    """情绪评分 → mood_daily"""
    path = os.path.join(DESKTOP, ".mood_score.json")
    if not os.path.exists(path):
        print("  ⬜ .mood_score.json 不存在，跳过")
        return
    
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    date = data.get("date", "") or datetime.now().strftime("%Y-%m-%d")
    db.save_mood_daily(
        date, data.get("score", 5), data.get("phase", ""),
        detail=json.dumps(data, ensure_ascii=False),
    )
    print(f"  ✅ mood_daily: 迁移 {date} 的情绪评分")


def migrate_history_json(db):
    """大盘走势历史 → index_daily"""
    path = os.path.join(DESKTOP, ".history.json")
    if not os.path.exists(path):
        print("  ⬜ .history.json 不存在，跳过")
        return
    
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    count = 0
    for rec in data:
        date = rec.get("date", "")
        if not date: continue
        sh_price = rec.get("shPrice", 0)
        sh_change = rec.get("shChange", 0)
        # 如果有收盘价和涨跌幅，反推昨收
        if sh_price and sh_change != 0:
            prev_close = round(sh_price / (1 + sh_change / 100), 2)
        else:
            prev_close = sh_price
        
        idx_data = {
            "close": sh_price, "change_pct": sh_change,
            "open": prev_close, "high": sh_price * 1.01, "low": sh_price * 0.99,
        }
        db.save_index_daily(date, "sh000001", "上证指数", **idx_data)
        count += 1
    
    print(f"  ✅ index_daily: 迁移 {count} 条大盘历史数据")


def backfill_kline(db):
    """回补关注的个股历史K线（最近60个交易日）"""
    total = 0
    errors = 0
    for code in TRACKED_CODES:
        prefix = "sh" if code.startswith("6") else "sz"
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={prefix}{code},day,,,60,qfq"
        try:
            raw = sp.run(["curl", "-s", "--max-time", "8", url],
                        capture_output=True, timeout=10).stdout
            if not raw: continue
            data = json.loads(raw.decode("utf-8", errors="replace"))
            saved = 0
            for key in data.get("data", {}):
                if "qfqday" in data["data"][key]:
                    for k in data["data"][key]["qfqday"]:
                        date_str = k[0]
                        _open = float(k[1]) if len(k) > 1 else 0
                        _close = float(k[2]) if len(k) > 2 else 0
                        _high = float(k[3]) if len(k) > 3 else 0
                        _low = float(k[4]) if len(k) > 4 else 0
                        _vol = float(k[5]) if len(k) > 5 else 0
                        chg = round((_close - _open) / _open * 100, 2) if _open else 0
                        db.save_stock_daily(date_str, code,
                            open=_open, close=_close, high=_high, low=_low,
                            volume=_vol, change_pct=chg)
                        saved += 1
                    break
            total += saved
            print(f"  {code} {'✅' if saved > 30 else '⚠️'}  {saved}条", end="")
            if saved <= 10:
                print(" (数据太少?)")
            else:
                print()
        except Exception as e:
            errors += 1
            print(f"  {code} ❌ 抓取失败: {str(e)[:30]}")
    
    print(f"\n  K线回补完成: {total}条, 失败{errors}只")


def print_status(db):
    st = db.stats()
    print(f"{'表名':20s} {'条数':>6s} {'最早日期':12s} {'最近日期':12s}")
    print("-" * 52)
    for tbl, info in st.items():
        if tbl == 'stock_weekly': continue
        print(f"  {tbl.replace('_',' ').title():18s} {info['count']:6d}  {info.get('earliest','--') or '--':12s} {info.get('latest','--') or '--':12s}")
    print(f"\n  DB大小: {os.path.getsize(db.db_path)/1024:.1f} KB")


if __name__ == "__main__":
    run()
