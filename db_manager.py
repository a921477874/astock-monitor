#!/usr/bin/env python3
"""
宝宝量化系统 — 本地数据管理器
==============================
在桌面 market_data.db 中存取所有市场数据。
优先读本地，本地没有再爬网络，爬完自动存本地。

用法:
    from db_manager import DB
    db = DB()
    
    # 存
    db.save_index_daily(date, code, name, close=..., change_pct=...)
    db.save_stock_daily(date, code, name, close=..., ...)
    db.save_picks_history(date, rank, code, name, ...)
    db.save_mood_daily(date, score, phase, ...)
    db.save_sector_daily(date, name, change_pct, ...)
    
    # 读（无数据返回None/空列表）
    idx = db.get_index_daily(code, date)      # 单日单指数
    idxs = db.get_index_history(code, days)   # 最近N天某指数
    stk = db.get_stock_daily(code, date)      # 单日单股
    stks = db.get_stock_history(code, days)   # 最近N天
    picks = db.get_picks_by_date(date)        # 某天推荐
    last_picks = db.get_latest_picks(n_days)  # 最近N天所有推荐
    mood = db.get_mood(date)                  # 某天情绪
    mood_series = db.get_mood_history(days)   # 最近N天情绪
    
    # 实用
    db.get_trading_days(days)                 # 最近N个交易日（去周末）
"""

import sqlite3
import os
import json
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'market_data.db')

class DB:
    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH
        self._ensure_tables()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_tables(self):
        """建表（幂等，重复调用无副作用）"""
        conn = self._connect()
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS index_daily (
          date TEXT, index_code TEXT, name TEXT,
          open REAL, close REAL, high REAL, low REAL,
          volume REAL, amount REAL, change_pct REAL,
          PRIMARY KEY(date, index_code)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS stock_daily (
          date TEXT, code TEXT, name TEXT,
          open REAL, close REAL, high REAL, low REAL,
          volume REAL, amount REAL, change_pct REAL,
          pe REAL, mkt_cap REAL, turnover REAL,
          PRIMARY KEY(date, code)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS stock_weekly (
          week TEXT, code TEXT, name TEXT,
          open REAL, close REAL, high REAL, low REAL,
          volume REAL, change_pct REAL,
          ma5 REAL, ma20 REAL, ma60 REAL,
          PRIMARY KEY(week, code)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS picks_history (
          date TEXT, rank INTEGER, code TEXT, name TEXT,
          score REAL, channel TEXT,
          price_t0 REAL, price_t1 REAL, price_t3 REAL, price_t5 REAL,
          change_t1 REAL, change_t3 REAL, change_t5 REAL,
          stop_loss REAL, take_profit REAL,
          outcome TEXT, note TEXT,
          PRIMARY KEY(date, rank)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS sector_daily (
          date TEXT, sector_name TEXT, sector_type TEXT DEFAULT '行业',
          change_pct REAL, hot_score REAL, rank INTEGER,
          lead_stock TEXT, lead_change REAL,
          PRIMARY KEY(date, sector_name)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS mood_daily (
          date TEXT PRIMARY KEY,
          score REAL, phase TEXT,
          up_down_ratio REAL, limit_up REAL, limit_down REAL,
          strong_weak_ratio REAL,
          ma20_direction TEXT, ma20_strength REAL,
          volume_health REAL,
          cross_market REAL,
          detail TEXT
        )''')
        conn.commit()
        conn.close()

    def _dict_to_row(self, row):
        if row is None:
            return None
        return dict(row)

    # ═══════════════════════════════════════
    # 存数据
    # ═══════════════════════════════════════

    def save_index_daily(self, date, index_code, name=None, **kw):
        kw['date'] = date
        kw['index_code'] = index_code
        if name: kw['name'] = name
        return self._upsert('index_daily', kw, ['date', 'index_code'])

    def save_stock_daily(self, date, code, name=None, **kw):
        kw['date'] = date
        kw['code'] = code
        if name: kw['name'] = name
        return self._upsert('stock_daily', kw, ['date', 'code'])

    def save_picks_history(self, date, rank, code, name=None, **kw):
        kw['date'] = date
        kw['rank'] = rank
        kw['code'] = code
        if name: kw['name'] = name
        return self._upsert('picks_history', kw, ['date', 'rank'])

    def save_mood_daily(self, date, score, phase=None, **kw):
        kw['date'] = date
        kw['score'] = score
        if phase: kw['phase'] = phase
        return self._upsert('mood_daily', kw, ['date'])

    def save_sector_daily(self, date, sector_name, change_pct, **kw):
        kw['date'] = date
        kw['sector_name'] = sector_name
        kw['change_pct'] = change_pct
        return self._upsert('sector_daily', kw, ['date', 'sector_name'])

    def _upsert(self, table, data, pk_cols):
        """INSERT OR REPLACE"""
        cols = list(data.keys())
        placeholders = ','.join(['?' for _ in cols])
        sql = f"INSERT OR REPLACE INTO {table} ({','.join(cols)}) VALUES ({placeholders})"
        vals = [data[c] if data[c] is not None else None for c in cols]
        conn = self._connect()
        try:
            conn.execute(sql, vals)
            conn.commit()
        except Exception as e:
            print(f"[DB] upsert {table} 失败: {e}")
            return False
        finally:
            conn.close()
        return True

    def save_many(self, table, records):
        """批量存，records是dict列表"""
        if not records:
            return
        cols = list(records[0].keys())
        placeholders = ','.join(['?' for _ in cols])
        sql = f"INSERT OR REPLACE INTO {table} ({','.join(cols)}) VALUES ({placeholders})"
        conn = self._connect()
        try:
            conn.executemany(sql, [[r.get(c) for c in cols] for r in records])
            conn.commit()
        except Exception as e:
            print(f"[DB] save_many {table} 失败: {e}")
        finally:
            conn.close()

    # ═══════════════════════════════════════
    # 读数据 — 找不到返回None/空列表，不抛异常
    # ═══════════════════════════════════════

    def get_index_daily(self, index_code, date=None):
        """单日单指数"""
        if date is None: date = datetime.now().strftime('%Y-%m-%d')
        conn = self._connect()
        row = conn.execute(
            "SELECT * FROM index_daily WHERE index_code=? AND date=?",
            (index_code, date)
        ).fetchone()
        conn.close()
        return self._dict_to_row(row)

    def get_index_history(self, index_code, days=30):
        """最近N天某指数"""
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM index_daily WHERE index_code=? ORDER BY date DESC LIMIT ?",
            (index_code, days)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_all_index_latest(self):
        """所有指数的最新一天"""
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM index_daily WHERE date=(SELECT MAX(date) FROM index_daily)"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_stock_daily(self, code, date=None):
        """单日单股"""
        if date is None: date = datetime.now().strftime('%Y-%m-%d')
        conn = self._connect()
        row = conn.execute(
            "SELECT * FROM stock_daily WHERE code=? AND date=?", (code, date)
        ).fetchone()
        conn.close()
        return self._dict_to_row(row)

    def get_stock_history(self, code, days=60):
        """最近N天个股日线"""
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM stock_daily WHERE code=? ORDER BY date DESC LIMIT ?",
            (code, days)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_stocks_by_date(self, date):
        """某天所有入库的个股"""
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM stock_daily WHERE date=?", (date,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_picks_by_date(self, date):
        """某天推荐记录"""
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM picks_history WHERE date=? ORDER BY rank", (date,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_latest_picks(self, n_days=5):
        """最近N天的所有推荐"""
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM picks_history WHERE date IN "
            "(SELECT DISTINCT date FROM picks_history ORDER BY date DESC LIMIT ?) "
            "ORDER BY date DESC, rank", (n_days,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_mood(self, date=None):
        if date is None: date = datetime.now().strftime('%Y-%m-%d')
        conn = self._connect()
        row = conn.execute("SELECT * FROM mood_daily WHERE date=?", (date,)).fetchone()
        conn.close()
        return self._dict_to_row(row)

    def get_mood_history(self, days=30):
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM mood_daily ORDER BY date DESC LIMIT ?", (days,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_sector_history(self, days=5):
        """最近N天的板块数据"""
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM sector_daily WHERE date IN "
            "(SELECT DISTINCT date FROM sector_daily ORDER BY date DESC LIMIT ?) "
            "ORDER BY date DESC, rank", (days,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_trading_days(self, days=30):
        """获取最近N个交易日（去周末）"""
        dates = []
        d = datetime.now()
        while len(dates) < days:
            if d.weekday() < 5:  # 周一到周五
                dates.append(d.strftime('%Y-%m-%d'))
            d -= timedelta(days=1)
        return sorted(dates)

    def get_earliest_date(self, table):
        """某张表的最早数据日期"""
        conn = self._connect()
        row = conn.execute(f"SELECT MIN(date) as d FROM {table}").fetchone()
        conn.close()
        return row['d'] if row and row['d'] else None

    def get_latest_date(self, table):
        """某张表的最新数据日期"""
        conn = self._connect()
        row = conn.execute(f"SELECT MAX(date) as d FROM {table}").fetchone()
        conn.close()
        return row['d'] if row and row['d'] else None

    def count_records(self, table):
        conn = self._connect()
        row = conn.execute(f"SELECT COUNT(*) as n FROM {table}").fetchone()
        conn.close()
        return row['n'] if row else 0

    def delete_older_than(self, table, days=180):
        """删除某表下N天前的数据"""
        cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        conn = self._connect()
        conn.execute(f"DELETE FROM {table} WHERE date < ?", (cutoff,))
        affected = conn.total_changes
        conn.commit()
        conn.close()
        return affected

    def vacuum(self):
        conn = self._connect()
        conn.execute("VACUUM")
        conn.close()

    def stats(self):
        """打印数据库统计"""
        tables = ['index_daily', 'stock_daily', 'stock_weekly', 'picks_history', 'sector_daily', 'mood_daily']
        out = {}
        conn = self._connect()
        for tbl in tables:
            try:
                r = conn.execute(f"SELECT COUNT(*) as n, MIN(date) as e, MAX(date) as l FROM {tbl}").fetchone()
                out[tbl] = {'count': r['n'], 'earliest': r['e'], 'latest': r['l']}
            except:
                out[tbl] = {'count': 0, 'earliest': None, 'latest': None}
        conn.close()
        return out


# ═══════════════════════════════════════
# 独立测试
# ═══════════════════════════════════════
if __name__ == '__main__':
    db = DB()
    st = db.stats()
    print("=" * 50)
    print("  📊 market_data.db 数据统计")
    print("=" * 50)
    for tbl, info in st.items():
        print(f"  {tbl:20s} {info['count']:6d}条  {info['earliest'] or '--':12s} → {info['latest'] or '--':12s}")
    print("=" * 50)
    print(f"  DB路径: {db.db_path}")
    print(f"  文件大小: {os.path.getsize(db.db_path)/1024:.1f} KB")
