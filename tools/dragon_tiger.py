#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
游资席位追踪模块 v1.0
从同花顺龙虎榜解析每日上榜数据
追踪知名游资买卖动向

游资数据库:
  炒股养家: 华鑫证券上海茅台路/宛平南路
  方新侠:  中信证券西安朱雀大街/兴业证券陕西分公司
  作手新一: 国泰君安证券南京太平南路
  赵老哥:  中国银河证券绍兴/浙商证券绍兴解放北路
  章盟主:  中信证券杭州延安路/国泰君安宁波彩虹北路
  小鳄鱼:  东方证券上海浦东新区源深路
  西湖国贸: 财通证券杭州体育场路/湘财证券杭州五星路
  佛山系:  光大证券佛山绿景路
  桑田路:  国盛证券宁波桑田路
  上塘路:  财通证券杭州上塘路
  湖州劳动路: 华泰证券湖州劳动路
  宁波解放南: 光大证券宁波解放南路
  欢乐海岸: 中泰证券深圳欢乐海岸/华泰证券深圳益田路
  溧阳路:  中信证券上海溧阳路
"""

import json, os, sys, urllib.request, ssl, re
from datetime import datetime

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_FILE = os.path.join(REPO_DIR, '.dragon_tiger.json')

# 知名游资营业部映射
FAMOUS_TRADERS = {
    "炒股养家": ["华鑫证券上海茅台路", "华鑫证券宛平南路", "华鑫证券上海宛平南路"],
    "方新侠": ["中信证券西安朱雀大街", "兴业证券陕西分公司", "中信证券西安朱雀"],
    "作手新一": ["国泰君安南京太平南路", "南京太平南路"],
    "赵老哥": ["银河证券绍兴", "浙商证券绍兴解放北路", "银河证券绍兴证券"],
    "章盟主": ["中信证券杭州延安路", "国泰君安宁波彩虹北路", "杭州延安路"],
    "小鳄鱼": ["东方证券上海浦东新区源深路", "源深路"],
    "西湖国贸": ["财通证券杭州体育场路", "湘财证券杭州五星路"],
    "佛山系": ["光大证券佛山绿景路", "佛山绿景路"],
    "桑田路": ["国盛证券宁波桑田路", "宁波桑田路"],
    "上塘路": ["财通证券杭州上塘路", "杭州上塘路"],
    "湖州劳动路": ["华泰证券湖州劳动路", "湖州劳动路"],
    "宁波解放南": ["光大证券宁波解放南路"],
    "欢乐海岸": ["中泰证券深圳欢乐海岸", "华泰证券深圳益田路"],
    "溧阳路": ["中信证券上海溧阳路", "上海溧阳路"],
    "机构专用": ["机构专用"],
}


def fetch_longhu_data():
    """从同花顺获取龙虎榜数据"""
    url = "https://data.10jqka.com.cn/market/longhu/"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.10jqka.com.cn",
    })
    raw = urllib.request.urlopen(req, timeout=10, context=CTX).read()
    text = raw.decode("gbk")
    
    stocks = []
    for m in re.finditer(r'<tr[^>]*>(.*?)</tr>', text, re.DOTALL):
        row = m.group(0)
        if 'class="stock"' not in row and 'stockcode=' not in row:
            continue
        
        code_m = re.search(r'stockcode="(\d+)"', row)
        name_m = re.search(r'class="stock"[^>]*>([^<]+)', row)
        label_m = re.search(r'class="label[^"]*"[^>]*>([^<]+)', row)
        tds = re.findall(r'<td[^>]*class="(?:tr|c-rise[^"]*|c-fall[^"]*)"[^>]*>([^<]*)</td>', row)
        
        code = code_m.group(1) if code_m else ""
        name = name_m.group(1) if name_m else ""
        label = label_m.group(1) if label_m else ""
        price = tds[0] if len(tds) > 0 else ""
        change = tds[1] if len(tds) > 1 else ""
        amount = tds[2] if len(tds) > 2 else ""
        net_buy = tds[3] if len(tds) > 3 else ""
        
        if code and name and (code, label) not in [(s["code"], s.get("label","")) for s in stocks]:
            stocks.append({
                "code": code, "name": name, "label": label,
                "price": price, "change": change,
                "amount": amount, "net_buy": net_buy,
            })
    
    return stocks


def identify_traders(stocks):
    """识别每只股票的游资参与情况"""
    results = []
    trader_stats = {name: {"buy_count": 0, "sell_count": 0, "stocks": []} for name in FAMOUS_TRADERS}
    
    for s in stocks:
        detected = []
        code = s["code"]
        net_buy_str = s.get("net_buy", "")
        net_buy_val = 0
        if net_buy_str:
            num_str = net_buy_str.replace(",", "").replace("亿", "e8").replace("万", "e4")
            try:
                net_buy_val = float(eval(num_str))
            except:
                pass
        
        # 查找该股票的详细买卖席位（TODO: 需要从页面细节解析）
        # 目前只记录净买入额较大的游资偏好
        
        # 根据营业部关键词识别（简化版）
        for trader, offices in FAMOUS_TRADERS.items():
            for office in offices:
                if office in code:  # 实际需要解析买入前5营业部
                    detected.append(trader)
                    if net_buy_val > 0:
                        trader_stats[trader]["buy_count"] += 1
                    else:
                        trader_stats[trader]["sell_count"] += 1
                    trader_stats[trader]["stocks"].append(s["name"])
                    break
        
        if detected:
            results.append({
                "code": code,
                "name": s["name"],
                "change": s["change"],
                "net_buy": net_buy_str,
                "traders": list(set(detected)),
            })
    
    return trader_stats, results


def main():
    now = datetime.now()
    print(f"{'='*50}")
    print(f"🐅 龙虎榜游资追踪 — {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")
    
    # 1. 获取数据
    print(f"\n📡 获取龙虎榜数据...")
    stocks = fetch_longhu_data()
    print(f"  获取到 {len(stocks)} 只股票")
    
    # 2. 龙虎榜概览
    print(f"\n📊 龙虎榜概览:")
    limit_ups = [s for s in stocks if s['change'].endswith('%') and float(s['change'].strip('%')) >= 9.5]
    limit_downs = [s for s in stocks if s['change'].endswith('%') and float(s['change'].strip('%')) <= -9.5]
    print(f"  涨停: {len(limit_ups)}只 | 跌停: {len(limit_downs)}只")
    
    # 净买入排行
    def parse_net(net_str):
        if not net_str: return 0
        try:
            num = net_str.replace(",","")
            if "亿" in num: return float(num.replace("亿","")) * 1e8
            if "万" in num: return float(num.replace("万","")) * 1e4
            return float(num)
        except:
            return 0
    
    sorted_net = sorted(stocks, key=lambda s: parse_net(s.get("net_buy","")), reverse=True)
    
    print(f"\n💰 净买入TOP10:")
    print(f"  {'名称':<10} {'代码':<8} {'涨跌':<8} {'净买入':<12}")
    print(f"  {'-'*40}")
    for s in sorted_net[:10]:
        print(f"  {s['name']:<10} {s['code']:<8} {s['change']:<8} {s['net_buy']:<12}")
    
    print(f"\n🔴 净卖出TOP5:")
    for s in sorted_net[-5:]:
        print(f"  {s['name']:<10} {s['code']:<8} {s['change']:<8} {s['net_buy']:<12}")
    
    # 3. 缓存
    cache = {
        "updated_at": now.strftime("%Y-%m-%d %H:%M"),
        "stock_count": len(stocks),
        "limit_up_count": len(limit_ups),
        "limit_down_count": len(limit_downs),
        "top_net_buy": [{"name": s["name"], "code": s["code"], "change": s["change"], "net_buy": s["net_buy"]} for s in sorted_net[:10]],
    }
    os.makedirs(os.path.dirname(CACHE_FILE) or ".", exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 缓存: {CACHE_FILE}")


if __name__ == "__main__":
    main()
