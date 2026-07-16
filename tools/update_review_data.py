#!/usr/bin/env python3
"""
更新复盘数据到 DAILY_REPORT JSON
将 auto_review.py 产出的 .review_history.json 数据注入 dashboard 可读的格式
生成 update_dashboard.py 可用的 DAILY_REPORT 扩展字段
"""

import json
import os
import sys
from datetime import datetime

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_FILE = os.path.join(REPO_DIR, '.review_history.json')
DAILY_REPORT_FILE = os.path.join(REPO_DIR, 'data', 'daily_report.json')

def load_review_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def load_daily_report():
    if os.path.exists(DAILY_REPORT_FILE):
        with open(DAILY_REPORT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def build_review_data():
    """构建 `pickReview` 和 `backtest` 字段"""
    history = load_review_history()
    daily_report = load_daily_report()
    
    if not history:
        print(json.dumps({"warning": "No review history yet"}, ensure_ascii=False))
        return
    
    # 计算累计统计
    total_picks = sum(r['total'] for r in history)
    total_up = sum(r['up'] for r in history)
    total_flat = sum(r['flat'] for r in history)
    total_down = sum(r['down'] for r in history)
    
    # 兼容新旧字段名
    def get_pnl(p):
        return p.get('pnl_from_rec', p.get('today_change', 0))
    
    def get_avg_pnl(record):
        if 'avg_pnl' in record:
            return record['avg_pnl']
        picks = record.get('picks', [])
        if picks:
            return sum(get_pnl(p) for p in picks) / len(picks)
        return 0
    
    total_weighted_pnl = sum(get_avg_pnl(r) * r['total'] for r in history)
    
    win_rate = round(total_up / (total_up + total_down) * 100, 1) if (total_up + total_down) > 0 else 0
    avg_pnl = round(total_weighted_pnl / total_picks, 2) if total_picks > 0 else 0
    
    # 按风险等级分组统计
    risk_stats = {}
    all_picks = []
    for r in history:
        for p in r.get('picks', []):
            all_picks.append(p)
            risk_level = p.get('risk', '未知')
            if risk_level not in risk_stats:
                risk_stats[risk_level] = {'total': 0, 'up': 0, 'down': 0, 'flat': 0, 'total_pnl': 0}
            risk_stats[risk_level]['total'] += 1
            pnl = get_pnl(p)
            if pnl > 0.3:
                risk_stats[risk_level]['up'] += 1
            elif pnl < -0.3:
                risk_stats[risk_level]['down'] += 1
            else:
                risk_stats[risk_level]['flat'] += 1
            risk_stats[risk_level]['total_pnl'] += pnl
    
    # 添加胜率到每个风险等级
    for rk, rs in risk_stats.items():
        valid = rs['up'] + rs['down']
        rs['win_rate'] = round(rs['up'] / valid * 100, 1) if valid > 0 else 0
        rs['avg_pnl'] = round(rs['total_pnl'] / rs['total'], 2) if rs['total'] > 0 else 0
    
    # 评分分组统计
    high_score = [p for p in all_picks if p.get('score', 0) >= 7.5]
    mid_score = [p for p in all_picks if 6 <= p.get('score', 0) < 7.5]
    low_score = [p for p in all_picks if p.get('score', 0) < 6]
    
    def score_group_stats(picks):
        if not picks:
            return None
        ups = sum(1 for p in picks if get_pnl(p) > 0.3)
        downs = sum(1 for p in picks if get_pnl(p) < -0.3)
        valid = ups + downs
        return {
            'count': len(picks),
            'up': ups,
            'down': downs,
            'win_rate': round(ups / valid * 100, 1) if valid > 0 else 0,
            'avg_pnl': round(sum(get_pnl(p) for p in picks) / len(picks), 2)
        }
    
    # 构建 pickReview 字段
    pick_review = {
        'stats': {
            'total_days': len(history),
            'total_picks': total_picks,
            'up': total_up,
            'flat': total_flat,
            'down': total_down,
            'win_rate': win_rate,
            'avg_pnl': avg_pnl,
            'risk_stats': risk_stats,
            'score_analysis': {
                'high_score': score_group_stats(high_score),
                'mid_score': score_group_stats(mid_score),
                'low_score': score_group_stats(low_score)
            }
        },
        'records': history
    }
    
    # 构建 backtest 字段 (与 renderBacktest 兼容)
    daily_records = []
    for r in history:
        daily_records.append({
            'date': r['date'],
            'picks': r.get('picks', []),
            'day_pnl': r.get('avg_pnl', 0),
            'up': r.get('up', 0),
            'down': r.get('down', 0)
        })
    
    # 累计收益（简单相加）
    total_return = sum(get_avg_pnl(r) for r in history)
    
    # 最大回撤（模拟）
    cumulative = 0
    max_dd = 0
    peak = 0
    for r in history:
        cumulative += get_avg_pnl(r)
        peak = max(peak, cumulative)
        dd = peak - cumulative
        max_dd = max(max_dd, dd)
    
    # 夏普比率（简化计算）
    returns = [get_avg_pnl(r) for r in history]
    avg_r = sum(returns) / len(returns) if returns else 0
    std_r = (sum((r - avg_r) ** 2 for r in returns) / len(returns)) ** 0.5 if len(returns) > 1 else 1
    sharpe = round(avg_r / std_r * (252 ** 0.5), 2) if std_r > 0 else 0
    
    backtest = {
        'total_days': len(history),
        'total_picks': total_picks,
        'win_rate': win_rate,
        'avg_pnl_per_pick': avg_pnl,
        'total_return': round(total_return, 2),
        'max_drawdown': round(max_dd, 2),
        'sharpe_ratio': sharpe,
        'daily_records': daily_records
    }
    
    # 注入到 daily_report
    daily_report['pickReview'] = pick_review
    daily_report['backtest'] = backtest
    daily_report['_review_updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    # 保存
    os.makedirs(os.path.dirname(DAILY_REPORT_FILE), exist_ok=True)
    with open(DAILY_REPORT_FILE, 'w', encoding='utf-8') as f:
        json.dump(daily_report, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 复盘数据已注入 DAILY_REPORT")
    print(f"   {len(history)} 天复盘, {total_picks} 次推荐")
    print(f"   胜率: {win_rate}%, 次均收益: {avg_pnl:+.2f}%")
    print(f"   累计收益: {total_return:+.2f}%, 夏普: {sharpe}")
    print(f"   数据写入: {DAILY_REPORT_FILE}")


if __name__ == '__main__':
    build_review_data()
