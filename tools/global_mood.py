#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨市场联动预警模块 v1.0
监控隔夜美股(纳斯达克/道指/标普) + 港股(恒生/恒生科技)
输出风险等级 + A股开盘预测

数据源: 腾讯行情接口 qt.gtimg.cn
运行时间: 盘前9:00 / 盘中每30分钟
"""

import json, os, sys, urllib.request, ssl, re
from datetime import datetime

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_FILE = os.path.join(REPO_DIR, '.global_mood.json')

# 全球指数腾讯代码
GLOBAL_CODES = {
    "道琼斯": "usDJI",
    "纳斯达克": "usIXIC", 
    "标普500": "usSPX",
    "恒生指数": "hkHSI",
    "恒生科技指数": "hkHSTECH",
}


def fetch_global_data():
    """获取全球主要指数实时数据"""
    codes = list(GLOBAL_CODES.values())
    url = "https://qt.gtimg.cn/q=" + ",".join(codes)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=10, context=CTX).read().decode("gbk")
    
    result = {}
    for line in raw.strip().split("\n"):
        if not line.strip(): continue
        vals = line.split("~")
        if len(vals) < 40: continue
        name = vals[1]
        price = float(vals[3]) if vals[3] else 0
        change_pct = float(vals[32]) if vals[32] else 0
        pre_close = float(vals[4]) if vals[4] else 0
        result[name] = {
            "price": price,
            "change_pct": change_pct,
            "prev_close": pre_close,
        }
    return result


def analyze_global_risk(global_data):
    """综合分析全球市场风险，返回风险等级和建议"""
    signals = []
    risk_level = 0
    
    nas = global_data.get("纳斯达克", {})
    dow = global_data.get("道琼斯", {})
    sp = global_data.get("标普500", {})
    hsi = global_data.get("恒生指数", {})
    hktech = global_data.get("恒生科技指数", {})
    
    nas_chg = nas.get("change_pct", 0) or 0
    sp_chg = sp.get("change_pct", 0) or 0
    dow_chg = dow.get("change_pct", 0) or 0
    hsi_chg = hsi.get("change_pct", 0) or 0
    hk_chg = hktech.get("change_pct", 0) or 0
    
    # ── 美股综合 ──
    us_composite = nas_chg * 0.5 + sp_chg * 0.3 + dow_chg * 0.2
    if us_composite < -1.5:
        signals.append(f"🛑 美股大跌{us_composite:.1f}%，A股可能显著承压低开")
        risk_level += 2
    elif us_composite < -0.5:
        signals.append(f"⚠️ 美股偏弱{us_composite:.1f}%，A股开盘可能受影响")
        risk_level += 1
    elif us_composite < 0:
        signals.append(f"➖ 美股小幅下跌{us_composite:.1f}%，影响有限")
        risk_level += 0.5
    elif us_composite > 1.5:
        signals.append(f"✅ 美股大涨{us_composite:+.1f}%，对A股情绪正面带动")
        risk_level -= 1
    elif us_composite > 0.5:
        signals.append(f"✅ 美股温和上涨{us_composite:+.1f}%，偏正面")
        risk_level -= 0.5
    
    # ── 恒生科技（对A股科技股指引最强）──
    if hk_chg < -3:
        signals.append(f"🛑 恒生科技暴跌{hk_chg:.1f}%，A股科技板块高度警惕")
        risk_level += 2
    elif hk_chg < -1.5:
        signals.append(f"⚠️ 恒生科技大跌{hk_chg:.1f}%，A股科技板块承压")
        risk_level += 1.5
    elif hk_chg < -0.5:
        signals.append(f"➖ 恒生科技偏弱{hk_chg:.1f}%，科技股需谨慎")
        risk_level += 0.5
    elif hk_chg > 2:
        signals.append(f"✅ 恒生科技大涨{hk_chg:+.1f}%，A股科技有望跟涨")
        risk_level -= 1
    
    # ── 恒生指数（对A股整体指引）──
    if hsi_chg < -2:
        signals.append(f"⚠️ 恒生指数下跌{hsi_chg:.1f}%，港股情绪偏弱")
        risk_level += 0.5
    elif hsi_chg > 1.5:
        signals.append(f"✅ 恒生指数上涨{hsi_chg:+.1f}%，港股情绪偏暖")
        risk_level -= 0.5
    
    # ── 美港科技双杀（重磅信号）──
    if nas_chg < -1 and hk_chg < -1.5:
        signals.append(f"🔴 美港科技双杀！A股科技板块今日高度警惕")
        risk_level += 1
    
    # ── 美港共振反弹 ──
    if nas_chg > 1 and hk_chg > 1:
        signals.append(f"🟢 美港科技共振反弹，A股科技有望跟涨")
        risk_level -= 1
    
    # ── 综合评估 ──
    risk_level = max(-3, min(5, risk_level))
    
    if risk_level >= 3:
        level_name = "🔴 高风险"
        open_pred = "预计低开0.5~1.5%，防御为主"
        advice = "不开新仓，已有仓位注意止损"
    elif risk_level >= 1.5:
        level_name = "🟡 中等风险"
        open_pred = "预计小幅低开0.2~0.5%，注意方向选择"
        advice = "谨慎参与，控制仓位3成以下"
    elif risk_level >= -0.5:
        level_name = "🟢 低风险"
        open_pred = "预计平开或小幅震荡"
        advice = "正常参与，关注开盘量能"
    elif risk_level >= -1.5:
        level_name = "🔵 偏暖"
        open_pred = "预计小幅高开，日内偏强"
        advice = "可适度加仓，关注热点板块"
    else:
        level_name = "🟣 积极"
        open_pred = "预计高开，积极做多"
        advice = "可积极参与，关注科技+金融主线"
    
    return {
        "risk_level": risk_level,
        "level_name": level_name,
        "open_prediction": open_pred,
        "advice": advice,
        "signals": signals,
        "us_composite": round(us_composite, 2),
        "nasdaq": nas_chg,
        "hsi": hsi_chg,
        "hk_tech": hk_chg,
    }


def main():
    now = datetime.now()
    print(f"{'='*50}")
    print(f"🌍 跨市场联动预警 — {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")
    
    # 1. 获取全球数据
    print(f"\n📡 全球市场数据:")
    global_data = fetch_global_data()
    for name, data in global_data.items():
        icon = "🔴" if data["change_pct"] > 0 else ("🟢" if data["change_pct"] < 0 else "⚪")
        print(f"  {icon} {name:<8} {data['price']:>8.2f} ({data['change_pct']:+.2f}%)")
    
    # 2. 分析风险
    print(f"\n📊 风险分析:")
    analysis = analyze_global_risk(global_data)
    print(f"  风险等级: {analysis['level_name']} (评分: {analysis['risk_level']})")
    for s in analysis["signals"]:
        print(f"  {s}")
    
    # 3. 预测和建议
    print(f"\n🎯 A股开盘预测: {analysis['open_prediction']}")
    print(f"💡 操作建议: {analysis['advice']}")
    
    # 4. 缓存
    cache = {
        "updated_at": now.strftime("%Y-%m-%d %H:%M"),
        "global_data": {
            k: {"price": v["price"], "change_pct": v["change_pct"]}
            for k, v in global_data.items()
        },
        "analysis": analysis,
    }
    os.makedirs(os.path.dirname(CACHE_FILE) or ".", exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 缓存: {CACHE_FILE}")
    
    # JSON输出
    print(f"\nJSON_OUTPUT:")
    print(json.dumps(analysis, ensure_ascii=False))


if __name__ == "__main__":
    main()
