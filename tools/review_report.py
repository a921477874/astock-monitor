#!/usr/bin/env python3
"""
每日收盘复盘报告生成器
输出结构化复盘数据和Dashboard JSON

配合auto_review.py使用，在收盘后自动分析当日盘前精选的表现
"""

import json
import os
import sys
from datetime import datetime, timedelta

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAILY_REVIEW_DIR = os.path.join(REPO_DIR, 'daily_reviews')

def generate_comprehensive_review():
    """生成综合复盘数据，包括最近5日的累计表现"""
    history_file = os.path.join(REPO_DIR, '.review_history.json')
    
    if not os.path.exists(history_file):
        print(json.dumps({"error": "No review history found"}, ensure_ascii=False))
        return
    
    with open(history_file, 'r', encoding='utf-8') as f:
        history = json.load(f)
    
    # 最近5日详细记录
    recent = history[-5:] if len(history) > 5 else history
    
    # 全部累计统计
    total_picks = sum(r['total'] for r in history)
    total_up = sum(r['up'] for r in history)
    total_flat = sum(r['flat'] for r in history)
    total_down = sum(r['down'] for r in history)
    total_pnl_weighted = sum(r['avg_pnl'] * r['total'] for r in history)
    overall_avg_pnl = round(total_pnl_weighted / total_picks, 2) if total_picks > 0 else 0
    win_rate = round(total_up / (total_up + total_down) * 100, 1) if (total_up + total_down) > 0 else 0
    
    # 收集所有个股的推荐至今收益
    all_picks = []
    for r in history:
        for p in r.get('picks', []):
            all_picks.append(p)
    
    # 评分分档
    high_score = [p for p in all_picks if p.get('score', 0) >= 7.5]
    mid_score = [p for p in all_picks if 6 <= p.get('score', 0) < 7.5]
    low_score = [p for p in all_picks if p.get('score', 0) < 6]
    
    def avg_pnl(picks_list):
        return round(sum(p['pnl_from_rec'] for p in picks_list) / len(picks_list), 2) if picks_list else None
    
    def calc_win_rate(picks_list):
        if not picks_list:
            return None
        ups = sum(1 for p in picks_list if p.get('pnl_from_rec', 0) > 0.3)
        downs = sum(1 for p in picks_list if p.get('pnl_from_rec', 0) < -0.3)
        total = ups + downs
        return round(ups / total * 100, 1) if total > 0 else None
    
    # 近期趋势 (最近5日胜率)
    recent_win_rates = []
    for r in recent:
        valid = r.get('up', 0) + r.get('down', 0)
        wr = round(r['up'] / valid * 100, 1) if valid > 0 else 0
        recent_win_rates.append({
            'date': r['date'],
            'win_rate': wr,
            'total': r['total'],
            'up': r['up'],
            'down': r['down']
        })
    
    # 评分有效性趋势
    score_effectiveness = []
    if len(history) >= 3:
        # 分两段看：前一半 vs 后一半
        mid = len(history) // 2
        early = history[:mid]
        late = history[mid:]
        
        for period_name, period in [('早期', early), ('近期', late)]:
            period_picks = []
            for r in period:
                for p in r.get('picks', []):
                    period_picks.append(p)
            if period_picks:
                hs = [p for p in period_picks if p.get('score', 0) >= 7.5]
                ls = [p for p in period_picks if p.get('score', 0) < 7]
                score_effectiveness.append({
                    'period': period_name,
                    'days': len(period),
                    'high_score_avg': avg_pnl(hs) if hs else None,
                    'low_score_avg': avg_pnl(ls) if ls else None
                })
    
    report = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'total_days': len(history),
        'total_picks': total_picks,
        'total_up': total_up,
        'total_flat': total_flat,
        'total_down': total_down,
        'win_rate': win_rate,
        'avg_pnl_per_pick': overall_avg_pnl,
        'recent_trend': recent_win_rates,
        'score_analysis': {
            'high_score': {
                'count': len(high_score),
                'avg_pnl': avg_pnl(high_score),
                'win_rate': calc_win_rate(high_score)
            },
            'mid_score': {
                'count': len(mid_score),
                'avg_pnl': avg_pnl(mid_score),
                'win_rate': calc_win_rate(mid_score)
            },
            'low_score': {
                'count': len(low_score),
                'avg_pnl': avg_pnl(low_score),
                'win_rate': calc_win_rate(low_score)
            }
        },
        'score_effectiveness_trend': score_effectiveness,
        'last_review': history[-1] if history else None
    }
    
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    generate_comprehensive_review()
