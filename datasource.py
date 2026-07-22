#!/usr/bin/env python3
"""
宝宝量化系统 — 数据统一数据源层
================================
所有数据统一从这里读取，优先本地SQLite，本地没有自动去网络拉。

用法示例:
    from datasource import DataSource
    ds = DataSource()
    
    # 大盘指数（自动缓存到本地SQLite）
    indices = ds.get_indices()  # 6大指数实时行情
    sh = indices.get('sh000001')  # {'price': 3230, 'change': 0.5}
    
    # 个股行情（自动缓存）
    stocks = ds.get_stocks(['600519', '000333'])
    
    # 选股数据
    picks = ds.get_closing_picks()   # 今天的收盘精选
    morning = ds.get_morning_picks() # 今天的盘前推荐
    
    # 情绪评分
    mood = ds.get_mood_score()
    
    # K线（自动存到SQLite）
    kline = ds.get_kline('600519', days=60)  # {日期->收盘价}
    
    # 板块行情
    sectors = ds.get_sectors()
    
    # 当本地数据是最新时，网络调用自动跳过
"""

import urllib.request
import json
import os
import re
import subprocess as sp
from datetime import datetime, timedelta

from db_manager import DB

DESKTOP = "/mnt/c/Users/Administrator/Desktop/A股报告"

class DataSource:
    """统一数据源 — 优先本地，再网络，爬完自动缓存"""
    
    def __init__(self, db_path=None):
        self.db = DB(db_path)
        self._today = datetime.now().strftime('%Y-%m-%d')
        self._now_hour = datetime.now().hour

    # ═══════════════════════════════════════
    # 公共：判断数据时效
    # ═══════════════════════════════════════
    
    def _is_today(self, date_str):
        return date_str == self._today
    
    def _is_trading_time(self):
        """是否交易时段（9:00-16:00），交易时段优先拉网络"""
        h = self._now_hour
        return h >= 9 and h < 16
    
    def _has_today_index(self):
        """本地有没有今天指数数据"""
        return self.db.get_index_daily('sh000001', self._today) is not None
    
    def _has_today_mood(self):
        """本地有没有今天情绪评分"""
        return self.db.get_mood(self._today) is not None

    # ═══════════════════════════════════════
    # 大盘指数
    # ═══════════════════════════════════════
    
    def get_indices(self, force_network=False):
        """
        获取6大指数行情。
        交易时段 + 没有今天数据 → 网络拉取并缓存
        非交易时段 / 有缓存 → 从SQLite读
        """
        # 如果本地有今天的数据且非交易时段，直接读本地
        if not force_network and not self._is_trading_time() and self._has_today_index():
            return self._read_indices_from_db()
        
        # 尝试网络拉取
        try:
            return self._fetch_indices_from_sina()
        except Exception as e:
            print(f"[DS] 网络拉指数失败: {e}，回退到本地")
            return self._read_indices_from_db()
    
    def _fetch_indices_from_sina(self):
        """从新浪拉指数并缓存到SQLite"""
        codes = ["sh000001", "sz399001", "sz399006", "sh000688", "sh000300", "sh000016"]
        url = f"https://hq.sinajs.cn/list={','.join(codes)}"
        req = urllib.request.Request(url, headers={"Referer": "https://finance.sina.com.cn"})
        resp = urllib.request.urlopen(req, timeout=10)
        raw = resp.read().decode("gbk")
        
        results = {}
        index_names = {
            'sh000001': '上证指数', 'sz399001': '深证成指', 'sz399006': '创业板指',
            'sh000688': '科创50', 'sh000300': '沪深300', 'sh000016': '上证50'
        }
        for line in raw.strip().split("\n"):
            if not line.strip(): continue
            try:
                var_name = line.split('"')[0].split("hq_str_")[-1].strip().rstrip("=")
                values = line.split('"')[1].split(",")
                current = float(values[3])
                prev_close = float(values[2])
                high = float(values[4])
                low = float(values[5])
                open_p = float(values[1])
                volume = float(values[8])
                amount = float(values[9])
                change_pct = round((current - prev_close) / prev_close * 100, 2) if prev_close else 0
                
                results[var_name] = {
                    'price': current, 'change': change_pct,
                    'open': open_p, 'high': high, 'low': low,
                    'volume': volume, 'amount': amount,
                }
                
                # 存到SQLite
                self.db.save_index_daily(
                    self._today, var_name, index_names.get(var_name, ''),
                    open=open_p, close=current, high=high, low=low,
                    volume=volume, amount=amount, change_pct=change_pct
                )
            except: continue
        return results
    
    def _read_indices_from_db(self):
        """从SQLite读最新一天的所有指数"""
        rows = self.db.get_all_index_latest()
        results = {}
        for r in rows:
            results[r['index_code']] = {
                'price': r['close'],
                'change': r['change_pct'],
                'open': r['open'],
                'high': r['high'],
                'low': r['low'],
                'volume': r.get('volume', 0),
                'amount': r.get('amount', 0),
            }
        # 补齐缺失的指数
        missing = {
            'sh000001': '上证指数', 'sz399001': '深证成指', 'sz399006': '创业板指',
            'sh000688': '科创50', 'sh000300': '沪深300', 'sh000016': '上证50'
        }
        for code, name in missing.items():
            if code not in results:
                # 找最近的
                rows = self.db.get_index_history(code, 3)
                if rows:
                    r = rows[0]
                    results[code] = {
                        'price': r['close'], 'change': r['change_pct'],
                        'open': r['open'], 'high': r['high'], 'low': r['low'],
                        'volume': r.get('volume', 0), 'amount': r.get('amount', 0),
                    }
        return results
    
    # ═══════════════════════════════════════
    # 个股行情
    # ═══════════════════════════════════════
    
    def get_stocks(self, codes, force_network=False):
        """
        获取个股行情。交易时段尽量网络拉，非交易时段读本地。
        codes: ['600519', '000333'] 不带sh/sz前缀
        返回: {'sh600519': {'price':..., 'change':..., ...}, ...}
        """
        if not codes:
            return {}
        
        # 非交易时段先尝试从本地读
        if not force_network and not self._is_trading_time():
            local = self._read_stocks_from_db(codes)
            if local:
                return local
        
        # 网络拉
        try:
            return self._fetch_stocks_from_tencent(codes)
        except Exception as e:
            print(f"[DS] 网络拉个股失败: {e}，回退到本地")
            return self._read_stocks_from_db(codes)
    
    def _fetch_stocks_from_tencent(self, codes):
        """腾讯批量接口拉个股，自动存到SQLite"""
        results = {}
        for i in range(0, len(codes), 50):
            batch = codes[i:i+50]
            qs = [('sh' if c.startswith('6') else 'sz')+c for c in batch]
            url = 'https://qt.gtimg.cn/q=' + ','.join(qs)
            raw = sp.run(['curl', '-s', '--max-time', '10', url], capture_output=True, timeout=15).stdout
            if not raw: continue
            text = raw.decode('gbk')
            for line in text.strip().split('\n'):
                m = re.match(r'v_(\w+)="(.+)"', line)
                if not m: continue
                vals = m.group(2).split('~')
                k = m.group(1).lower()
                try:
                    d = {
                        'name': vals[1], 'code': vals[2],
                        'price': float(vals[3]) if vals[3] else 0,
                        'change': float(vals[32]) if vals[32] else 0,
                        'turnover': float(vals[38]) if vals[38] else 0,
                        'pe': float(vals[39]) if vals[39] else 0,
                        'mcap': float(vals[44]) if vals[44] else 0,
                        'high52': float(vals[67]) if vals[67] else 0,
                        'low52': float(vals[68]) if vals[68] else 0,
                    }
                    results[k] = d
                    
                    # 存到SQLite
                    self.db.save_stock_daily(
                        self._today, vals[2], vals[1],
                        close=d['price'], change_pct=d['change'],
                        pe=d['pe'], mkt_cap=d['mcap'],
                        turnover=d['turnover'],
                    )
                except: continue
        return results
    
    def _read_stocks_from_db(self, codes):
        """从SQLite读个股最新数据"""
        results = {}
        for code in codes:
            r = self.db.get_stock_daily(code)
            if r:
                key = ('sh' if code.startswith('6') else 'sz') + code
                results[key] = {
                    'name': r.get('name', ''), 'code': code,
                    'price': r['close'], 'change': r['change_pct'],
                    'turnover': r.get('turnover', 0),
                    'pe': r.get('pe', 0), 'mcap': r.get('mkt_cap', 0),
                }
        return results

    # ═══════════════════════════════════════
    # K线 + 多日收益
    # ═══════════════════════════════════════
    
    def get_kline(self, code, days=16):
        """
        拉个股日K线，缓存到SQLite。
        返回: {日期->收盘价}
        """
        pref = "sh" if code.startswith("6") else "sz"
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={pref}{code},day,,,{days},qfq"
        result = {}
        try:
            raw = sp.run(["curl", "-s", "--max-time", "8", url], capture_output=True, timeout=10).stdout
            if not raw: return result
            data = json.loads(raw.decode("utf-8", errors="replace"))
            for key in data.get("data", {}):
                if "qfqday" in data["data"][key]:
                    for k in data["data"][key]["qfqday"]:
                        date_str = k[0]
                        close = float(k[2])
                        result[date_str] = close
                        # 同时存到stock_daily（如果有日期对应）
                        self.db.save_stock_daily(date_str, code, open=float(k[1]) if len(k)>1 else 0,
                                                  close=close, high=float(k[3]) if len(k)>3 else 0,
                                                  low=float(k[4]) if len(k)>4 else 0,
                                                  volume=float(k[5]) if len(k)>5 else 0)
                    break
        except: pass
        return result
    
    def calc_multi_day_returns(self, code, rec_price, rec_date, kline_map=None):
        """
        计算T+1/T+3/T+5收益率。
        如果没传kline_map会自动拉。
        """
        if kline_map is None:
            kline_map = self.get_kline(code, 16)
        
        rd = datetime.strptime(rec_date, "%Y-%m-%d")
        result = {"d1": None, "d3": None, "d5": None}
        trading_days = []
        for i in range(1, 16):
            d = (rd + timedelta(days=i)).strftime("%Y-%m-%d")
            if d in kline_map:
                trading_days.append(d)
        if len(trading_days) >= 1:
            close1 = kline_map.get(trading_days[0], 0)
            result["d1"] = round((close1 - rec_price) / rec_price * 100, 2) if rec_price and close1 else None
        if len(trading_days) >= 3:
            close3 = kline_map.get(trading_days[2], 0)
            result["d3"] = round((close3 - rec_price) / rec_price * 100, 2) if rec_price and close3 else None
        if len(trading_days) >= 5:
            close5 = kline_map.get(trading_days[4], 0)
            result["d5"] = round((close5 - rec_price) / rec_price * 100, 2) if rec_price and close5 else None
        return result
    
    # ═══════════════════════════════════════
    # 选股数据（JSON文件读取 + 存SQLite）
    # ═══════════════════════════════════════
    
    def get_closing_picks(self):
        """读取尾盘精选JSON文件，同时缓存到SQLite"""
        path = os.path.join(DESKTOP, ".closing_picks.json")
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 存到SQLite
            top = data.get("top5") or data.get("top3") or []
            for i, p in enumerate(top):
                self.db.save_picks_history(
                    data.get("date", self._today), i+1,
                    p.get("code", ""), p.get("name", ""),
                    score=p.get("score"), channel=p.get("channel", ""),
                    price_t0=p.get("price", 0),
                    stop_loss=p.get("stop_loss", 0),
                    take_profit=p.get("take_profit", 0),
                )
            return data
        except: return None
    
    def get_morning_picks(self):
        """读取盘前精选JSON文件"""
        path = os.path.join(DESKTOP, ".morning_picks.json")
        if not os.path.exists(path): return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return None

    # ═══════════════════════════════════════
    # 情绪评分
    # ═══════════════════════════════════════
    
    def get_mood_score(self):
        """
        获取情绪评分。优先读本地SQLite（非交易时段）。
        如果.mood_score.json存在，读取并缓存到SQLite。
        """
        # 先看JSON文件（最新数据）
        path = os.path.join(DESKTOP, ".mood_score.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # 缓存到SQLite
                self.db.save_mood_daily(
                    data.get("date", self._today),
                    data.get("score", 5),
                    data.get("phase", ""),
                    up_down_ratio=data.get("factors", {}).get("up_down_ratio"),
                    limit_up=data.get("factors", {}).get("limit_up"),
                    limit_down=data.get("factors", {}).get("limit_down"),
                    detail=json.dumps(data, ensure_ascii=False),
                )
                return data
            except: pass
        # 没有JSON文件，从SQLite读
        row = self.db.get_mood(self._today)
        if row:
            return {
                "score": row["score"],
                "phase": row.get("phase", ""),
                "label": self._phase_to_label(row.get("phase", "")),
                "date": row["date"],
            }
        return None
    
    def _phase_to_label(self, phase):
        labels = {"冰点": "❄️ 冰点", "低迷": "🌧️ 低迷", "中性": "📊 中性", "活跃": "🔥 活跃", "亢奋": "⚡ 亢奋"}
        return labels.get(phase, "📊 中性")
    
    # ═══════════════════════════════════════
    # 复盘数据
    # ═══════════════════════════════════════
    
    def get_review_history(self):
        """读取复盘数据"""
        path = os.path.join(DESKTOP, ".review_history.json")
        if not os.path.exists(path): return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return []
    
    def get_history_json(self):
        """大盘走势历史记录"""
        path = os.path.join(DESKTOP, ".history.json")
        if not os.path.exists(path): return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return []
    
    # ═══════════════════════════════════════
    # 产业新闻
    # ═══════════════════════════════════════
    
    def get_industry_news(self):
        """产业新闻数据"""
        path = os.path.join(DESKTOP, ".industry_news.json")
        if not os.path.exists(path): return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return None

    # ═══════════════════════════════════════
    # 数据状态检查
    # ═══════════════════════════════════════
    
    def get_data_status(self):
        """返回所有数据源的当前状态摘要"""
        st = self.db.stats()
        lines = ["📊 本地数据状态"]
        lines.append(f"{'='*40}")
        for tbl, info in st.items():
            status = "✅" if info['count'] > 0 else "⬜"
            name = tbl.replace('_', ' ').title()
            lines.append(f"  {status} {name:20s} {info['count']:5d}条  {info.get('latest','--')}")
        
        # 检查今天的文件
        for fname in ['.closing_picks.json', '.morning_picks.json', '.mood_score.json', '.review_history.json']:
            fpath = os.path.join(DESKTOP, fname)
            if os.path.exists(fpath):
                mtime = os.path.getmtime(fpath)
                mdate = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
                lines.append(f"  📄 {fname:25s} {mdate}")
            else:
                lines.append(f"  📄 {fname:25s} ⬜ 不存在")
        
        lines.append(f"{'='*40}")
        lines.append(f"  DB大小: {os.path.getsize(self.db.db_path)/1024:.1f} KB")
        return "\n".join(lines)


# 快速测试
if __name__ == '__main__':
    ds = DataSource()
    print(ds.get_data_status())
