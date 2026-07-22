#!/usr/bin/env python3
"""生成股票代码缓存（静态+盘中动态更新）"""
import json, os, time

CACHE_PATH = "/mnt/c/Users/Administrator/Desktop/A股报告/.stock_code_cache.json"

# 先用已知活跃股票（沪深主板前3000只常用代码）
def build_cache():
    cache = []
    codes = []
    # 沪A 600XXX
    for i in range(0, 1000):
        codes.append(f"600{i:03d}")
    # 沪A 601XXX
    for i in range(0, 1000):
        codes.append(f"601{i:03d}")
    # 沪A 603XXX  
    for i in range(0, 600):
        codes.append(f"603{i:03d}")
    # 深A 000XXX
    for i in range(0, 1000):
        codes.append(f"000{i:03d}")
    # 深A 001XXX
    for i in range(0, 200):
        codes.append(f"001{i:03d}")
    # 深A 002XXX
    for i in range(0, 1000):
        codes.append(f"002{i:03d}")
    
    # 批量查腾讯，过滤有效代码
    print(f"查询 {len(codes)} 只股票代码...")
    batch_size = 50
    seen = set()
    for start in range(0, len(codes), batch_size):
        batch = codes[start:start+batch_size]
        qs = ["sh"+c if c.startswith("6") else "sz"+c for c in batch]
        url = "https://qt.gtimg.cn/q=" + ",".join(qs)
        try:
            import urllib.request, re
            req = urllib.request.Request(url, headers={"Referer": "https://qt.gtimg.cn"})
            raw = urllib.request.urlopen(req, timeout=5).read().decode("gbk")
            for line in raw.strip().split("\n"):
                m = re.match(r'v_(\w+)="(.+)"', line)
                if not m:
                    continue
                v = m.group(2).split("~")
                if len(v) > 1 and v[1]:  # 有名字说明是有效股票
                    code_key = m.group(1)
                    code = code_key[2:] if code_key.startswith(("sh", "sz")) else code_key
                    if code not in seen:
                        seen.add(code)
                        cache.append({"code": code, "name": v[1]})
        except:
            pass
        time.sleep(0.1)
    
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f)
    print(f"✅ 缓存 {len(cache)} 只有效股票代码到 {CACHE_PATH}")
    return cache

if __name__ == "__main__":
    build_cache()
