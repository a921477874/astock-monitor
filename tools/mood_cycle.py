#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
市场情绪周期择时模块 v2.0
从多个维度综合评估当日市场情绪
v2.0新增: 涨跌家数比(全市场)、20日均线方向、成交量变化
输出情绪评分 + 对应的选股策略建议
"""
import json, subprocess, re, os, sys, urllib.request, ssl, time
from datetime import datetime, timedelta

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOOD_CACHE = os.path.join(REPO_DIR, '.mood_score.json')
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

def fetch_ma20_trend():
    """获取上证20日均线方向和成交量变化
    通过新浪历史K线计算: 今日20日均线 vs 5日前20日均线 判断方向
    成交量: 今日量/20日均量
    """
    result = {"ma20_dir": 0, "vol_ratio": 1.0, "trend_strength": 0}
    try:
        today = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=60)).strftime("%Y%m%d")
        url = f"https://q.stock.sohu.com/hisHq?code=cn_000001&start={start}&end={today}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = json.loads(urllib.request.urlopen(req, timeout=6, context=CTX).read())
        if data and data[0].get("hq"):
            days = data[0]["hq"]
            closes = [float(d[2]) for d in days]
            volumes = [float(d[7]) for d in days]
            closes.reverse()
            volumes.reverse()
            
            if len(closes) >= 25:
                ma20_today = sum(closes[-20:]) / 20
                ma20_5ago = sum(closes[-25:-5]) / 20
                ma20_dir = 1 if ma20_today > ma20_5ago else (-1 if ma20_today < ma20_5ago else 0)
                
                vol_ma20 = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else 1
                vol_today = volumes[-1] if len(volumes) >= 1 else vol_ma20
                vol_ratio = vol_today / vol_ma20 if vol_ma20 > 0 else 1.0
                
                # 趋势强度: (今日-5日前)/5日前 * 100
                trend_strength = (ma20_today - ma20_5ago) / ma20_5ago * 100 if ma20_5ago > 0 else 0
                
                result = {
                    "ma20_dir": ma20_dir,
                    "vol_ratio": round(vol_ratio, 2),
                    "trend_strength": round(trend_strength, 2),
                    "ma20_today": round(ma20_today, 2),
                    "ma20_5ago": round(ma20_5ago, 2),
                }
    except:
        pass
    return result

def fetch_market_mood():
    """综合评估市场情绪, 返回情绪评分和策略建议"""
    ctx = 'curl -s --max-time 8'
    now = datetime.now()
    
    # 维度1: 全市场涨跌家数比 + 新高新低比
    # 从新浪分页获取全市场（沪A+深A），排除创业/科创
    mood_factors = {}
    
    try:
        all_changes = []
        page = 1
        while True:
            url = (f"https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
                   f"Market_Center.getHQNodeData?page={page}&num=100&sort=turnoverratio"
                   f"&asc=0&node=hs_a&symbol=")
            r = subprocess.run(f'{ctx} "{url}" -H "Referer: https://finance.sina.com.cn"',
                              shell=True, capture_output=True, text=True, timeout=10)
            m = re.search(r'\[.*\]', r.stdout)
            if not m: break
            items = json.loads(m.group())
            if not items: break
            for d in items:
                code = d.get("code","")
                prefix = code[:3]
                if prefix in ("300","301","688","920","900","200","204"): continue
                change = float(d.get("changepercent",0) or 0)
                all_changes.append(change)
            if len(items) < 100: break
            page += 1
            time.sleep(0.2)
        
        if all_changes:
            total = len(all_changes)
            up = sum(1 for c in all_changes if c > 0)
            down = sum(1 for c in all_changes if c < 0)
            limit_up = sum(1 for c in all_changes if c >= 9.5)
            limit_down = sum(1 for c in all_changes if c <= -9.5)
            big_up = sum(1 for c in all_changes if 5 <= c < 9.5)
            big_down = sum(1 for c in all_changes if -9.5 < c <= -5)
            
            # 涨跌家数比评分
            up_ratio = up / total
            if up_ratio > 0.65:
                width_score = 8.5
            elif up_ratio > 0.55:
                width_score = 7.0
            elif up_ratio > 0.45:
                width_score = 5.5
            elif up_ratio > 0.35:
                width_score = 4.0
            elif up_ratio > 0.25:
                width_score = 2.5
            else:
                width_score = 1.5  # 只有不到25%的票上涨，极度弱势
            
            # 涨跌停比评分
            ld_ratio = limit_down / max(limit_up, 1)
            if ld_ratio > 5:
                ld_score = 1.5  # 跌停远超涨停
            elif ld_ratio > 2:
                ld_score = 3.0
            elif ld_ratio > 1:
                ld_score = 4.5
            else:
                ld_score = 6.5
            
            # 强势弱势比（+5%以上 vs -5%以下）
            sb_ratio = big_up / max(big_down, 1)
            if sb_ratio > 3:
                sb_score = 8.0
            elif sb_ratio > 1:
                sb_score = 6.5
            elif sb_ratio > 0.5:
                sb_score = 5.0
            elif sb_ratio > 0.2:
                sb_score = 3.5
            else:
                sb_score = 2.0  # 弱势股远超强势股
            
            mood_factors['涨跌家数'] = round(width_score, 1)
            mood_factors['涨跌停比'] = round(ld_score, 1)
            mood_factors['强势弱势'] = round(sb_score, 1)
            mood_factors['_up_ratio'] = round(up_ratio, 3)
            mood_factors['_limit_up'] = limit_up
            mood_factors['_limit_down'] = limit_down
            mood_factors['_total_stocks'] = total
            mood_factors['_big_up'] = big_up
            mood_factors['_big_down'] = big_down
    except Exception as e:
        mood_factors['涨跌家数'] = 5.0
        mood_factors['涨跌停比'] = 5.0
        mood_factors['强势弱势'] = 5.0
    
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
    
    # ── 维度2.5: 20日均线趋势 + 量能 ──
    ma20 = fetch_ma20_trend()
    ma20_dir = ma20.get('ma20_dir', 0)
    vol_ratio = ma20.get('vol_ratio', 1.0)
    trend_strength = ma20.get('trend_strength', 0)
    
    # MA20方向评分
    if ma20_dir > 0:
        if trend_strength > 0.5:
            ma20_score = 7.5  # 强势上升
        else:
            ma20_score = 6.0  # 温和上升
    elif ma20_dir < 0:
        if trend_strength < -0.5:
            ma20_score = 2.5  # 明显下降
        else:
            ma20_score = 4.0  # 偏弱
    else:
        ma20_score = 5.0  # 横盘
    
    # 量能评分（缩量下跌=不好，放量下跌=恐慌，缩量企稳=好）
    if vol_ratio < 0.7 and ma20_dir < 0:
        vol_score = 2.0  # 缩量下跌，无人接盘
    elif vol_ratio > 1.5 and ma20_dir < 0:
        vol_score = 2.5  # 放量下跌，恐慌
    elif vol_ratio < 0.7 and ma20_dir > 0:
        vol_score = 7.5  # 缩量上涨，健康
    elif vol_ratio > 1.5 and ma20_dir > 0:
        vol_score = 6.5  # 放量上涨，强势
    else:
        vol_score = 5.0
    
    mood_factors['均线趋势'] = round(ma20_score, 1)
    mood_factors['量能健康'] = round(vol_score, 1)
    mood_factors['_ma20_dir'] = ma20_dir
    mood_factors['_vol_ratio'] = vol_ratio
    mood_factors['_ma20_today'] = ma20.get('ma20_today', 0)
    mood_factors['_ma20_5ago'] = ma20.get('ma20_5ago', 0)
    
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
        '涨跌家数': 0.20,
        '涨跌停比': 0.10,
        '强势弱势': 0.10,
        '大盘趋势': 0.15,
        '结构分化': 0.08,
        '均线趋势': 0.15,
        '量能健康': 0.10,
        '跨市场': 0.12,
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
          f"大涨+5%:{mood['raw'].get('_big_up',0)} 大跌-5%:{mood['raw'].get('_big_down',0)} | "
          f"全{mood['raw'].get('_total_stocks',0)}只 | "
          f"涨跌比{mood['raw'].get('_up_ratio',0):.0%}")
    print(f"  更新: {mood['updated_at']}")

if __name__ == '__main__':
    mood = fetch_market_mood()
    print_report(mood)
    print(f"\nJSON_OUTPUT:")
    print(json.dumps(mood, ensure_ascii=False))
