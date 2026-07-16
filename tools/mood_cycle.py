#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
市场情绪周期择时模块 v1.0
从多个维度综合评估当日市场情绪
输出情绪评分 + 对应的选股策略建议
"""
import json, subprocess, re, os, sys
from datetime import datetime

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOOD_CACHE = os.path.join(REPO_DIR, '.mood_score.json')

def fetch_market_mood():
    """综合评估市场情绪, 返回情绪评分和策略建议"""
    ctx = 'curl -s --max-time 8'
    now = datetime.now()
    
    # 维度1: 涨跌家数比 (按量比排序取200只)
    mood_factors = {}
    
    try:
        url = ("https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
               "Market_Center.getHQNodeData?page=1&num=200&sort=turnoverratio&asc=0&node=hs_a&symbol=")
        r = subprocess.run(f'{ctx} "{url}" -H "Referer: https://finance.sina.com.cn"',
                          shell=True, capture_output=True, text=True, timeout=10)
        m = re.search(r'\[.*\]', r.stdout)
        if m:
            items = json.loads(m.group())
            changes = [float(d.get('changepercent',0) or 0) for d in items]
            
            up = sum(1 for c in changes if c > 0)
            down = sum(1 for c in changes if c < -0.5)
            limit_up = sum(1 for c in changes if c >= 9.5)
            limit_down = sum(1 for c in changes if c <= -9.5)
            big_up = sum(1 for c in changes if 5 <= c < 9.5)
            big_down = sum(1 for c in changes if -9.5 < c <= -5)
            total = len(changes)
            
            up_ratio = up / total
            limit_up_ratio = limit_up / total
            limit_down_ratio = limit_down / total
            
            width_score = 5.0
            if up_ratio > 0.65: width_score = 8.0
            elif up_ratio > 0.55: width_score = 6.5
            elif up_ratio > 0.45: width_score = 5.0
            elif up_ratio > 0.35: width_score = 3.5
            else: width_score = 2.0
            
            extra = min(2, limit_up_ratio * 30) - min(2, limit_down_ratio * 30)
            limit_score = min(10, max(1, 5 + extra * 2.5))
            
            profit_score = 5.0
            if big_up > big_down * 2: profit_score = 8.0
            elif big_up > big_down: profit_score = 6.5
            elif big_down > big_up * 2: profit_score = 2.0
            elif big_down > big_up: profit_score = 3.5
            
            mood_factors['涨跌家数'] = round(width_score, 1)
            mood_factors['涨停密度'] = round(limit_score, 1)
            mood_factors['赚钱效应'] = round(profit_score, 1)
            mood_factors['_up_ratio'] = round(up_ratio, 3)
            mood_factors['_limit_up'] = limit_up
            mood_factors['_limit_down'] = limit_down
    except Exception as e:
        mood_factors['涨跌家数'] = 5.0
        mood_factors['涨停密度'] = 5.0
    
    # 维度2: 大盘趋势
    try:
        url2 = 'http://qt.gtimg.cn/q=sh000001,sz399001,sz399006,sh000688'
        r2 = subprocess.run(f'{ctx} "{url2}"', shell=True, capture_output=True, timeout=10)
        text = r2.stdout.decode('gbk')
        indices = {}
        for line in text.strip().split('\n'):
            mm = re.match(r'v_(\w+)="(.+)"', line)
            if mm:
                vals = mm.group(2).split('~')
                name = vals[1]
                change = float(vals[32]) if vals[32] else 0
                indices[name] = change
        
        sh_chg = indices.get('上证指数', 0)
        kc_chg = indices.get('科创50', 0)
        cyb_chg = indices.get('创业板指', 0)
        
        trend_score = 5.0
        if sh_chg > 0.5: trend_score = 7.0
        elif sh_chg > 0: trend_score = 5.5
        elif sh_chg > -0.5: trend_score = 4.5
        elif sh_chg > -1.5: trend_score = 3.5
        else: trend_score = 2.0
        
        divergence = kc_chg - sh_chg
        struct_score = 5.0
        if divergence > 2: struct_score = 8.0
        elif divergence > 0: struct_score = 6.0
        elif divergence > -2: struct_score = 4.0
        else: struct_score = 2.0
        
        mood_factors['大盘趋势'] = round(trend_score, 1)
        mood_factors['结构分化'] = round(struct_score, 1)
        mood_factors['_sh'] = sh_chg
        mood_factors['_kc'] = kc_chg
        mood_factors['_cyb'] = cyb_chg
    except:
        mood_factors['大盘趋势'] = 5.0
        mood_factors['结构分化'] = 5.0
    
    # ── 维度3: 跨市场联动 ──
    global_score = 5.0
    try:
        url3 = 'http://qt.gtimg.cn/q=hkHSI,hkHSTECH,usDJI,usIXIC,usSPX'
        r3 = subprocess.run(f'{ctx} "{url3}"', shell=True, capture_output=True, timeout=8)
        text3 = r3.stdout.decode('gbk')
        
        global_data = {}
        for line3 in text3.strip().split('\n'):
            mm3 = re.match(r'v_(\w+)="(.+)"', line3)
            if mm3:
                vals3 = mm3.group(2).split('~')
                name3 = vals3[1]
                change3 = float(vals3[32]) if vals3[32] else 0
                global_data[name3] = change3
        
        hk_tech = global_data.get('恒生科技指数', 0)
        us_nasdaq = global_data.get('纳斯达克', 0)
        us_spx = global_data.get('标普500', 0)
        hk_hsi = global_data.get('恒生指数', 0)
        
        # 恒生科技强 → A股科技次日偏暖
        if hk_tech > 1.5: global_score = 7.5
        elif hk_tech > 0.5: global_score = 6.5
        elif hk_tech > 0: global_score = 5.5
        elif hk_tech > -1: global_score = 4.5
        else: global_score = 3.0
        
        # 美股+港股双弱 → 加强信号
        if us_nasdaq < -1 and hk_tech < -1:
            global_score = max(1, global_score - 1)
        
        mood_factors['跨市场'] = round(global_score, 1)
        mood_factors['_hk_tech'] = hk_tech
        mood_factors['_us_nasdaq'] = us_nasdaq
        mood_factors['_hk_hsi'] = hk_hsi
    except:
        mood_factors['跨市场'] = 5.0
    # 综合评分
    weights = {
        '涨跌家数': 0.25,
        '涨停密度': 0.15,
        '赚钱效应': 0.15,
        '大盘趋势': 0.20,
        '结构分化': 0.10,
        '跨市场': 0.15,
    }
    
    total_score = 5.0
    for factor, weight in weights.items():
        if factor in mood_factors:
            total_score += (mood_factors[factor] - 5.0) * weight
    
    total_score = round(min(10, max(1, total_score)), 1)
    
    # 判定周期阶段
    if total_score >= 8:
        phase = '亢奋'
        label = '🔥 亢奋'
        advice = '市场过热, 注意风险, 不追高'
        position = '3~5成(减仓)'
        pick_threshold = 7.5
        risk_bias = '防守'
    elif total_score >= 6.5:
        phase = '活跃'
        label = '📊 活跃'
        advice = '结构性行情, 精选个股, 积极操作'
        position = '5~7成'
        pick_threshold = 7.0
        risk_bias = '积极'
    elif total_score >= 5:
        phase = '中性'
        label = '➖ 中性'
        advice = '震荡格局, 控制仓位, 等回调建仓'
        position = '3~5成'
        pick_threshold = 7.0
        risk_bias = '中性'
    elif total_score >= 3.5:
        phase = '低迷'
        label = '🌧️ 低迷'
        advice = '亏钱效应明显, 防守为主, 低吸不追涨'
        position = '2~3成'
        pick_threshold = 7.5
        risk_bias = '防守'
    else:
        phase = '冰点'
        label = '❄️ 冰点'
        advice = '情绪冰点, 可能酝酿反弹, 但不轻易抄底'
        position = '1~2成'
        pick_threshold = 8.0
        risk_bias = '防守'
    
    result = {
        'updated_at': now.strftime('%Y-%m-%d %H:%M'),
        'score': total_score,
        'phase': phase,
        'label': label,
        'advice': advice,
        'position': position,
        'pick_threshold': pick_threshold,
        'risk_bias': risk_bias,
        'factors': {k: v for k, v in mood_factors.items() if not k.startswith('_')},
        'raw': {k: v for k, v in mood_factors.items() if k.startswith('_')},
    }
    
    with open(MOOD_CACHE, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    return result

def print_report(mood):
    """打印情绪报告"""
    print(f"\n{'='*50}")
    print(f"市场情绪周期报告")
    print(f"{'='*50}")
    print(f"  综合评分: {mood['score']}/10 -> {mood['label']}")
    print(f"  仓位建议: {mood['position']}")
    print(f"  操作建议: {mood['advice']}")
    print(f"  选股阈值: >={mood['pick_threshold']}分")
    print(f"  风险偏向: {mood['risk_bias']}")
    print(f"\n  分项评分:")
    for factor, score in mood['factors'].items():
        bar = chr(9608) * int(score) + chr(9617) * (10 - int(score))
        print(f"    {factor:<8} {score:>4.1f} {bar}")
    print(f"\n  大盘: 上证{mood['raw'].get('_sh',0):+.2f}% | "
          f"科创{mood['raw'].get('_kc',0):+.2f}% | "
          f"创业{mood['raw'].get('_cyb',0):+.2f}%")
    print(f"  涨停{mood['raw'].get('_limit_up',0)}家 | "
          f"跌停{mood['raw'].get('_limit_down',0)}家 | "
          f"涨跌比{mood['raw'].get('_up_ratio',0):.0%}")
    print(f"  更新: {mood['updated_at']}")

if __name__ == '__main__':
    mood = fetch_market_mood()
    print_report(mood)
    print(f"\nJSON_OUTPUT:")
    print(json.dumps(mood, ensure_ascii=False))
