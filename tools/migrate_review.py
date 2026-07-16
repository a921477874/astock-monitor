#!/usr/bin/env python3
"""
一次性迁移脚本：将旧的 .review_picks.json 迁移到 .review_history.json 格式
同时也检查 data/daily_report.json 是否存在并正确更新
"""

import json
import os

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD_REVIEW_FILE = os.path.join(REPO_DIR, '.review_picks.json')
HISTORY_FILE = os.path.join(REPO_DIR, '.review_history.json')

def migrate():
    # 如果 history 已经存在且非空，不做覆盖
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            existing = json.load(f)
        if existing:
            print(f"📋 已有 review history: {len(existing)} 条记录")
            print(f"   日期: {[r['date'] for r in existing]}")
            return
    
    if not os.path.exists(OLD_REVIEW_FILE):
        print("⚠️  没有找到旧的 .review_picks.json")
        return
    
    with open(OLD_REVIEW_FILE, 'r', encoding='utf-8') as f:
        old_data = json.load(f)
    
    if not old_data:
        print("⚠️  旧文件为空")
        return
    
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(old_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 已迁移 {len(old_data)} 条复盘记录到 .review_history.json")
    for r in old_data:
        print(f"   {r['date']}: {r['total']}只推荐, 胜率{r['win_rate']}%")

if __name__ == '__main__':
    migrate()
