#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
板块资金热度扫描器
从东方财富获取行业/概念板块资金流向, 输出板块热度评分
供选股引擎调用
"""
import json, subprocess, re, os, sys
from datetime import datetime

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECTOR_CACHE_FILE = os.path.join(REPO_DIR, '.sector_flow.json')

def fetch_sector_flow():
    """从东方财富获取行业板块资金流向, 按净流入+涨跌幅两次取数合并"""
    def do_fetch(fid, po):
        url = ("https://push2.eastmoney.com/api/qt/clist/get?cb=&pn=1&pz=100&po=" + str(po) + "&np=1"
               "&fields=f2,f3,f4,f12,f14,f62,f184,f66&fid=" + fid + "&fs=m:90+t:2")
        r = subprocess.run(
            f'curl -s --max-time 10 "{url}" -H "User-Agent: Mozilla/5.0" -H "Referer: https://data.eastmoney.com/"',
            shell=True, capture_output=True, text=True, timeout=10
        )
        data = json.loads(r.stdout)
        return data.get('data', {}).get('diff', [])
    
    # 按净流入倒序 + 按涨跌幅倒序，合并去重
    all_items = {}
    for fid, po in [("f62", 1), ("f3", 1)]:
        items = do_fetch(fid, po)
        for item in items:
            bid = item.get('f12', '')
            if bid not in all_items:
                all_items[bid] = item
    
    sectors = {}
    for bid, item in all_items.items():
        name = item.get('f14', '').strip()
        chg = float(item.get('f3', 0) or 0) / 100
        flow = float(item.get('f62', 0) or 0) / 100000000
        flow_ratio = float(item.get('f184', 0) or 0) / 100
        sectors[name] = {
            'change_pct': round(chg, 2),
            'flow': round(flow, 2),
            'flow_ratio': round(flow_ratio, 2),
        }
    return sectors

def fetch_concept_flow():
    """概念板块资金流向, 同理合并取数"""
    def do_fetch(fid, po):
        url = ("https://push2.eastmoney.com/api/qt/clist/get?cb=&pn=1&pz=100&po=" + str(po) + "&np=1"
               "&fields=f2,f3,f4,f12,f14,f62,f184,f66&fid=" + fid + "&fs=m:90+t:3")
        r = subprocess.run(
            f'curl -s --max-time 10 "{url}" -H "User-Agent: Mozilla/5.0" -H "Referer: https://data.eastmoney.com/"',
            shell=True, capture_output=True, text=True, timeout=10
        )
        data = json.loads(r.stdout)
        return data.get('data', {}).get('diff', [])
    
    all_items = {}
    for fid, po in [("f62", 1), ("f3", 1)]:
        items = do_fetch(fid, po)
        for item in items:
            bid = item.get('f12', '')
            if bid not in all_items:
                all_items[bid] = item
    
    concepts = {}
    for bid, item in all_items.items():
        name = item.get('f14', '').strip()
        chg = float(item.get('f3', 0) or 0) / 100
        flow = float(item.get('f62', 0) or 0) / 100000000
        concepts[name] = {
            'change_pct': round(chg, 2),
            'flow': round(flow, 2),
        }
    return concepts

# 板块名映射: 我们的板块名 -> 东方财富关键词
# 板块名映射: 我们的板块名 -> 东方财富关键词
SECTOR_KEYWORDS = {
    "半导体": ["半导体", "芯片", "集成电路", "封测", "印制电路板", "晶圆", "分立器件", "电子元器件"],
    "AI/算力": ["AI", "人工智能", "算力", "服务器", "华为昇腾", "华为欧拉", "ChatGPT", "计算机", "软件", "IT服务", "IT服务Ⅲ", "IT服务Ⅱ", "软件开发", "垂直应用软件"],
    "新能源汽车": ["新能源汽车", "乘用车", "电动乘用车", "汽车整车", "充电桩", "锂电池", "动力电池", "汽车电子"],
    "消费/白酒": ["白酒", "食品饮料", "饮料", "白酒概念", "调味品", "乳品", "白酒Ⅲ", "白酒Ⅱ"],
    "医药/医疗": ["医药", "医疗", "器械", "医院", "创新药", "生物制品", "中药", "原料药", "体外诊断", "血液制品", "医美"],
    "金融/券商": ["券商", "银行", "保险", "证券", "多元金融", "期货", "金融", "金融信息服务"],
    "有色金属": ["有色", "黄金", "铜", "铝", "小金属", "有色金属", "稀土", "钢铁"],
    "家电": ["家电", "白色家电", "黑色家电", "小家电", "品牌消费电子"],
    "军工": ["军工", "航天", "航空", "船舶", "无人机", "高端装备"],
    "光伏": ["光伏", "太阳能", "储能", "HIT电池", "TOPCon", "逆变器", "光伏加工设备"],
    "传媒/游戏": ["传媒", "游戏", "影视", "短剧", "广告", "动漫", "影院", "数字媒体", "营销"],
    "房地产": ["房地产", "住宅开发", "商业地产", "物业管理", "房地产开发"],
    "通信": ["通信", "5G", "6G", "光模块", "光通信"],
}


def map_stock_to_sectors(sectors, concepts):
    """将板块热度映射到关注板块"""
    result = {}
    
    for our_name, keywords in SECTOR_KEYWORDS.items():
        matched_sectors = []
        matched_concepts = []
        
        for s_name, s_data in sectors.items():
            if any(kw in s_name for kw in keywords):
                matched_sectors.append(s_data)
        
        for c_name, c_data in concepts.items():
            if any(kw in c_name for kw in keywords):
                matched_concepts.append(c_data)
        
        total_flow = sum(s['flow'] for s in matched_sectors) + sum(c['flow'] for c in matched_concepts)
        count = len(matched_sectors) + len(matched_concepts)
        
        avg_change = 0
        if count > 0:
            total_chg = sum(s['change_pct'] for s in matched_sectors) + sum(c['change_pct'] for c in matched_concepts)
            avg_change = round(total_chg / count, 2)
        
        # 热度评分 1-10
        heat = 5.0
        if total_flow > 0:
            if total_flow > 50: heat = 9.0
            elif total_flow > 30: heat = 8.0
            elif total_flow > 15: heat = 7.0
            elif total_flow > 5: heat = 6.0
            else: heat = 5.5
        else:
            if total_flow < -50: heat = 2.0
            elif total_flow < -20: heat = 3.0
            elif total_flow < -10: heat = 4.0
            else: heat = 4.5
        
        # 涨跌幅修正
        if avg_change > 2: heat = min(10, heat + 1)
        elif avg_change < -2: heat = max(1, heat - 1)
        
        # 有多个匹配板块则加分(确认度高)
        if count >= 3: heat = min(10, heat + 0.5)
        
        result[our_name] = {
            'heat_score': round(heat, 1),
            'total_flow': round(total_flow, 2),
            'avg_change': avg_change,
            'matched_count': count,
        }
    
    return result

def main():
    now = datetime.now()
    print(f"{'='*50}")
    print(f"板块资金热度扫描 -- {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")
    
    sectors = fetch_sector_flow()
    print(f"\n行业板块: {len(sectors)} 个")
    
    concepts = fetch_concept_flow()
    print(f"概念板块: {len(concepts)} 个")
    
    sector_heat = map_stock_to_sectors(sectors, concepts)
    
    print(f"\n{'='*60}")
    print(f"关注板块热度排行 (按主力净流入排序)")
    print(f"{'='*60}")
    print(f"{'排名':>3} {'板块':<12} {'热度':>4} {'净流入':>10} {'涨跌':>7} {'匹配':>4}")
    print("-"*42)
    
    sorted_heat = sorted(sector_heat.items(), key=lambda x: x[1]['heat_score'], reverse=True)
    for i, (name, data) in enumerate(sorted_heat):
        flow = data['total_flow']
        d = '🟢' if flow > 0 else '🔴'
        icon = '🔥' if data['heat_score'] >= 7 else '✅' if data['heat_score'] >= 5 else '⚠️'
        print(f"{i+1:>3} {icon} {name:<10} {data['heat_score']:>4.1f} {d} {flow:>+7.1f}亿 {data['avg_change']:>+5.1f}% {data['matched_count']:>4}")
    
    # 保存
    cache = {
        'updated_at': now.strftime('%Y-%m-%d %H:%M'),
        'sector_heat': sector_heat,
        'raw_sectors': sectors,
    }
    with open(SECTOR_CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    print(f"\n缓存: {SECTOR_CACHE_FILE}")
    
    # 输出 JSON 供调用
    output = {
        'sector_heat': sector_heat,
        'updated_at': now.strftime('%Y-%m-%d %H:%M'),
    }
    print(f"\nJSON_OUTPUT:")
    print(json.dumps(output, ensure_ascii=False))

if __name__ == '__main__':
    main()
