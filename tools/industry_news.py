#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
产业逻辑深度扫描器 v1.0
从新浪财经新闻自动扫描板块相关利好/利空
为选股评分提供产业逻辑因子

数据源：
  1. 新浪财经新闻 (feed.mix.sina.com.cn)
  2. 新浪全市场股票聚合板块涨跌
  3. 板块资金流向（同花顺/腾讯）
"""

import json, urllib.request, re, os, sys, ssl
from datetime import datetime

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_FILE = os.path.join(REPO_DIR, '.industry_news.json')

# 关注的板块及其关键词（用于匹配新闻）
INDUSTRY_KEYWORDS = {
    "半导体": ["半导体", "芯片", "集成电路", "封测", "晶圆", "光刻", "国产替代", "电子元器件"],
    "AI/算力": ["人工智能", "AI", "算力", "大模型", "ChatGPT", "DeepSeek", "服务器", "数据中心", "华为昇腾"],
    "新能源汽车": ["新能源汽车", "电动车", "锂电池", "充电桩", "整车", "比亚迪", "特斯拉", "理想汽车"],
    "消费/白酒": ["白酒", "消费", "食品饮料", "啤酒", "乳业", "调味品", "免税", "预制菜"],
    "医药/医疗": ["医药", "医疗", "创新药", "CXO", "中药", "医疗器械", "生物制药", "医保", "集采"],
    "金融/券商": ["券商", "银行", "保险", "证券", "金融", "降息", "降准", "货币政策"],
    "有色金属": ["有色金属", "黄金", "铜", "铝", "稀土", "锂矿", "钴", "镍"],
    "家电": ["家电", "空调", "冰箱", "洗衣机", "消费电子"],
    "军工": ["军工", "航天", "航空", "船舶", "无人机", "国防"],
    "光伏": ["光伏", "太阳能", "储能", "逆变器", "HIT", "TOPCon"],
    "传媒/游戏": ["传媒", "游戏", "影视", "短剧", "广告", "动漫", "AIGC"],
    "房地产": ["房地产", "地产", "楼市", "购房", "房贷", "降首付", "城中村"],
    "通信": ["通信", "5G", "6G", "光模块", "卫星", "量子"],
    "电力": ["电力", "电网", "发电", "绿电", "电改", "电价", "储能"],
    "化工": ["化工", "化学", "氟化工", "磷化工", "有机硅", "化肥"],
    "机械设备": ["机械", "高端装备", "机器人", "工业母机", "智能制造"],
}


def fetch_sina_news():
    """获取新浪财经新闻，返回新闻列表"""
    all_news = []
    try:
        url = "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2509&knum=50"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        raw = urllib.request.urlopen(req, timeout=8, context=CTX).read().decode("utf-8")
        d = json.loads(raw)
        items = d.get("result", {}).get("data", [])
        for item in items:
            title = item.get("title", "").strip()
            intro = item.get("intro", "").strip()
            if title:
                all_news.append(f"{title} {intro}")
    except:
        pass
    
    # 再加一组财经要闻
    try:
        url2 = "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2510&knum=30"
        req2 = urllib.request.Request(url2, headers={"User-Agent": "Mozilla/5.0"})
        raw2 = urllib.request.urlopen(req2, timeout=8, context=CTX).read().decode("utf-8")
        d2 = json.loads(raw2)
        items2 = d2.get("result", {}).get("data", [])
        for item in items2:
            title = item.get("title", "").strip()
            if title and title not in all_news:
                all_news.append(title)
    except:
        pass
    
    return all_news


def match_industry_news(news_list):
    """将新闻匹配到关注的板块，统计利好/利空信号"""
    industry_signals = {}
    
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        matched_news = []
        for news in news_list:
            for kw in keywords:
                if kw in news:
                    matched_news.append(news[:80])
                    break
        
        # 判断情绪：简单关键字分析
        positive_count = 0
        negative_count = 0
        for news in matched_news:
            pos_words = ["涨", "升", "利好", "突破", "增长", "放量", "新高", "景气", "政策支持",
                        "加码", "扩产", "订单", "创新高", "反弹", "复苏", "反攻", "走强"]
            neg_words = ["跌", "降", "利空", "减持", "风险", "处罚", "调查", "亏损", "下滑",
                        "萎缩", "停产", "诉讼", "违约", "制裁", "受限", "被套"]
            
            pos_count = sum(1 for w in pos_words if w in news)
            neg_count = sum(1 for w in neg_words if w in news)
            if pos_count > neg_count:
                positive_count += 1
            elif neg_count > pos_count:
                negative_count += 1
        
        if matched_news:
            sentiment = "利好" if positive_count > negative_count else "利空" if negative_count > positive_count else "中性"
            signal_score = 5.0
            if sentiment == "利好":
                signal_score = min(10, 5.0 + positive_count * 0.8)
            elif sentiment == "利空":
                signal_score = max(1, 5.0 - negative_count * 0.8)
            
            industry_signals[industry] = {
                "news_count": len(matched_news),
                "positive": positive_count,
                "negative": negative_count,
                "sentiment": sentiment,
                "signal_score": round(signal_score, 1),
                "news_samples": [n[:60] for n in matched_news[:3]],
            }
    
    return industry_signals


def fetch_sector_changes():
    """从新浪全市场数据聚合板块涨跌"""
    sector_stocks = {s: [] for s in INDUSTRY_KEYWORDS}
    
    try:
        for page in range(1, 4):  # 取300只活跃股
            url = (f"https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
                   f"Market_Center.getHQNodeData?page={page}&num=100&sort=turnoverratio"
                   f"&asc=0&node=hs_a&symbol=")
            req = urllib.request.Request(url, headers={"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"})
            raw = urllib.request.urlopen(req, timeout=10, context=CTX).read().decode("gbk")
            m = re.search(r"\[.*\]", raw)
            if not m: break
            items = json.loads(m.group())
            if not items: break
            
            for d in items:
                name = d.get("name", "")
                change = float(d.get("changepercent", 0) or 0)
                code = d.get("code", "")
                prefix = code[:3]
                if prefix in ("300", "301", "688", "920", "900", "200", "204"):
                    continue
                
                for sector, keywords in INDUSTRY_KEYWORDS.items():
                    for kw in keywords:
                        if kw in name:
                            sector_stocks[sector].append(change)
                            break
    except:
        pass
    
    result = {}
    for sector, changes in sector_stocks.items():
        if changes:
            avg = sum(changes) / len(changes)
            up = sum(1 for c in changes if c > 0)
            result[sector] = {
                "stock_count": len(changes),
                "avg_change": round(avg, 2),
                "up_ratio": round(up / len(changes), 3),
            }
    return result


def main():
    now = datetime.now()
    print(f"{'='*50}")
    print(f"产业逻辑深度扫描 — {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")
    
    # 1. 新闻扫描
    print(f"\n📰 Step 1: 财经新闻扫描...")
    news = fetch_sina_news()
    print(f"  获取到 {len(news)} 条新闻")
    
    # 2. 行业新闻匹配
    print(f"\n📊 Step 2: 行业新闻匹配...")
    signals = match_industry_news(news)
    print(f"  匹配到 {len(signals)} 个行业")
    
    # 3. 板块涨跌聚合
    print(f"\n📈 Step 3: 板块涨跌聚合...")
    sector_data = fetch_sector_changes()
    print(f"  获取到 {len(sector_data)} 个板块数据")
    
    # 4. 综合评分输出
    print(f"\n{'='*60}")
    print(f"🏭 产业逻辑评分排行")
    print(f"{'='*60}")
    print(f"{'板块':<12} {'新闻':>4} {'情绪':>6} {'信号':>4} {'涨跌':>7} {'热度':>4}")
    print("-"*42)
    
    combined = {}
    for sector in INDUSTRY_KEYWORDS:
        sig = signals.get(sector, {})
        sd = sector_data.get(sector, {})
        
        score = 5.0
        parts = []
        
        if sig:
            score += (sig["signal_score"] - 5) * 0.4  # 新闻情绪权重40%
            parts.append(f"新闻{sig['signal_score']:.1f}")
        
        if sd:
            avg_chg = sd.get("avg_change", 0)
            if avg_chg > 2:
                score += 1.5
            elif avg_chg > 0.5:
                score += 0.5
            elif avg_chg < -2:
                score -= 1.5
            elif avg_chg < -0.5:
                score -= 0.5
            parts.append(f"板块{sd['avg_change']:+.1f}%")
        
        score = max(1, min(10, round(score, 1)))
        sentiment = sig.get("sentiment", "中性") if sig else "中性"
        news_count = sig.get("news_count", 0) if sig else 0
        
        combined[sector] = {
            "score": score,
            "news_count": news_count,
            "sentiment": sentiment,
            "avg_change": sd.get("avg_change", 0) if sd else 0,
        }
        
        if score >= 7 or score <= 3 or news_count >= 2:
            icon = "🔥" if score >= 7 else ("⚠️" if score <= 3 else "➖")
            d = "🟢" if sd.get("avg_change", 0) > 0 else ("🔴" if sd.get("avg_change", 0) < 0 else "⚪") if sd else "⚪"
            print(f"{icon} {sector:<10} {news_count:>4} {sentiment:>6} {score:>4.1f} {d} {sd.get('avg_change',0):>+5.1f}% {score:>3.0f}%")
    
    # 保存缓存
    cache = {
        "updated_at": now.strftime("%Y-%m-%d %H:%M"),
        "industries": combined,
        "news_count": len(news),
    }
    os.makedirs(os.path.dirname(CACHE_FILE) or ".", exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 缓存: {CACHE_FILE}")
    
    # 输出JSON
    output = {"industries": combined, "updated_at": cache["updated_at"]}
    print(f"\nJSON_OUTPUT:")
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
