#!/usr/bin/env python3
"""
每日盘前精选自动复盘
在盘前精选生成后，次日收盘后自动查询腾讯行情，对比推荐表现
记录每只票的真实涨跌、是否在买入区间内、评分与表现的关系

运行方式: python3 auto_review.py
"""

import json
import os
import sys
import urllib.request
import urllib.parse
import ssl
from datetime import datetime, timedelta

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_FILE = os.path.join(REPO_DIR, '.review_history.json')
PICKS_FILE = os.path.join(REPO_DIR, '.closing_picks.json')
REVIEW_FILE = os.path.join(REPO_DIR, '.review_picks.json')
MARKET_SUMMARY_FILE = os.path.join(REPO_DIR, '.history.json')

def fetch_tencent_price(code):
    """查询腾讯实时行情"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    # 统一格式: 上交所加sh，深交所加sz
    if code.startswith('6'):
        full_code = f'sh{code}'
    else:
        full_code = f'sz{code}'
    
    api_url = f'http://qt.gtimg.cn/q={full_code}'
    
    try:
        req = urllib.request.Request(api_url)
        req.add_header('Referer', 'http://qt.gtimg.cn')
        resp = urllib.request.urlopen(req, timeout=10, context=ctx)
        raw = resp.read().decode('gbk')
        
        if 'FAILER' in raw or '=' not in raw:
            return None
        
        parts = raw.split('~')
        if len(parts) < 50:
            return None
        
        price = float(parts[3]) if parts[3] else 0
        prev_close = float(parts[4]) if parts[4] else price
        change_pct = float(parts[32]) if parts[32] else 0
        high = float(parts[33]) if parts[33] else 0
        low = float(parts[34]) if parts[34] else 0
        volume_ratio = float(parts[38]) if parts[38] else 0  # 换手率
        name = parts[1] if parts[1] else ''
        
        return {
            'price': price,
            'prev_close': prev_close,
            'change_pct': round(change_pct, 2),
            'high': high,
            'low': low,
            'volume_ratio': volume_ratio,
            'name': name
        }
    except Exception as e:
        print(f"  [WARN] 查询 {code} 失败: {e}")
        return None


def fetch_sina_market_summary():
    """获取大盘指数行情"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    indices = {
        'sh': 'sh000001',   # 上证
        'sz': 'sz399001',   # 深证
        'cyb': 'sz399006',  # 创业板
        'kc': 'sh000688',   # 科创50
    }
    
    result = {}
    
    for key, code in indices.items():
        try:
            api_url = f'http://qt.gtimg.cn/q={code}'
            req = urllib.request.Request(api_url)
            resp = urllib.request.urlopen(req, timeout=10, context=ctx)
            raw = resp.read().decode('gbk')
            parts = raw.split('~')
            if len(parts) > 32:
                result[key] = {
                    'price': float(parts[3]) if parts[3] else 0,
                    'change_pct': float(parts[32]) if parts[32] else 0
                }
        except:
            pass
    
    return result


def load_history():
    """加载历史复盘记录"""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_history(records):
    """保存历史复盘记录"""
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def load_review_picks():
    """加载已有复盘记录"""
    if os.path.exists(REVIEW_FILE):
        with open(REVIEW_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_review_picks(records):
    """保存复盘记录"""
    with open(REVIEW_FILE, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def review_yesterday_picks():
    """对昨天盘前精选的票进行复盘"""
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 计算昨天日期
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    # 尝试多个日期的盘前精选
    candidates = [yesterday, today]
    
    picks_data = None
    pick_date = None
    
    for d in candidates:
        # 检查是否有对应日期的精选文件
        alt_file = os.path.join(REPO_DIR, f'.closing_picks_{d}.json')
        if os.path.exists(alt_file):
            with open(alt_file, 'r', encoding='utf-8') as f:
                picks_data = json.load(f)
            pick_date = d
            break
    
    # 也尝试从当前精选文件识别日期
    if picks_data is None and os.path.exists(PICKS_FILE):
        with open(PICKS_FILE, 'r', encoding='utf-8') as f:
            cur = json.load(f)
        pick_date = cur.get('date', '')
        if pick_date and pick_date != today:
            picks_data = cur
    
    if picks_data is None:
        print(f"[SKIP] 未找到前一天的盘前精选数据 (日期: {yesterday})")
        return None
    
    top5 = picks_data.get('top5', [])
    if not top5:
        print(f"[SKIP] 盘前精选 {pick_date} 没有推荐股票")
        return None
    
    print(f"\n{'='*60}")
    print(f"📊 复盘日期: {pick_date} → {today}")
    print(f"推荐股票数: {len(top5)}")
    print(f"{'='*60}")
    
    # 获取大盘行情
    print("\n📈 大盘行情:")
    indices = fetch_sina_market_summary()
    for key, val in indices.items():
        direction = '🟢' if val['change_pct'] >= 0 else '🔴'
        print(f"  {direction} {key.upper()}: {val['price']:.2f} ({val['change_pct']:+.2f}%)")
    
    print(f"\n{'='*60}")
    print(f"📋 个股复盘详情:")
    print(f"{'='*60}")
    
    review_records = []
    total_up = 0
    total_flat = 0
    total_down = 0
    total_score = 0
    total_pnl = 0
    valid_picks = 0
    
    for pick in top5:
        rank = pick.get('rank', '?')
        name = pick.get('name', '未知')
        code = pick.get('code', '')
        rec_price = pick.get('price', 0)
        score = pick.get('score', 0)
        buy_low = pick.get('buy_low', 0)
        buy_high = pick.get('buy_high', 0)
        stop_loss = pick.get('stop_loss', 0)
        
        print(f"\n  [{rank}] {name} ({code})")
        print(f"     推荐价: {rec_price} | 评分: {score}")
        print(f"     买入区间: {buy_low}~{buy_high} | 止损: {stop_loss}")
        
        real = fetch_tencent_price(code)
        
        if real is None:
            print(f"     ⚠️  查询失败，跳过")
            continue
        
        # 计算真实涨跌幅
        if rec_price > 0:
            real_change_pct = round((real['price'] - rec_price) / rec_price * 100, 2)
        else:
            real_change_pct = real['change_pct']
        
        # 判定是否在买入区间内
        in_zone = buy_low <= real['price'] <= buy_high if buy_low > 0 and buy_high > 0 else 'N/A'
        
        # 判定胜负
        if abs(real_change_pct) < 0.3:
            verdict = '➖ 平'
            total_flat += 1
        elif real_change_pct > 0:
            verdict = '✅ 涨'
            total_up += 1
        else:
            verdict = '❌ 跌'
            total_down += 1
        
        total_score += score
        total_pnl += real_change_pct
        valid_picks += 1
        
        # 判定是否触及止损
        touched_stop = '⚠️ 是' if stop_loss > 0 and real['low'] <= stop_loss else '否'
        
        direction_emoji = '🟢' if real['change_pct'] >= 0 else '🔴'
        print(f"     {direction_emoji} 现价: {real['price']:.2f}")
        print(f"     {direction_emoji} 今日涨跌: {real['change_pct']:+.2f}%")
        print(f"     推荐至今: {real_change_pct:+.2f}%")
        print(f"     在买入区间: {'✅ 是' if in_zone == True else ('❌ 否' if in_zone == False else 'N/A')}")
        print(f"     触发止损: {touched_stop}")
        print(f"     判定: {verdict}")
        
        review_records.append({
            'rank': rank,
            'name': name,
            'code': code,
            'rec_price': rec_price,
            'rec_zone': f'{buy_low}~{buy_high}' if buy_low > 0 else 'N/A',
            'in_zone': bool(in_zone) if isinstance(in_zone, bool) else 'N/A',
            'today_price': real['price'],
            'today_change': real['change_pct'],
            'pnl_from_rec': real_change_pct,
            'score': score,
            'stop_loss': stop_loss,
            'touched_stop': touched_stop == '⚠️ 是',
            'verdict': verdict,
            'high': real['high'],
            'low': real['low']
        })
    
    if valid_picks == 0:
        print("\n⚠️  没有有效的复盘数据")
        return None
    
    win_rate = round(total_up / valid_picks * 100, 1)
    avg_pnl = round(total_pnl / valid_picks, 2)
    
    print(f"\n{'='*60}")
    print(f"📊 复盘总结 ({pick_date})")
    print(f"{'='*60}")
    print(f"  推荐数: {valid_picks}")
    print(f"  ✅ 涨: {total_up}  |  ➖ 平: {total_flat}  |  ❌ 跌: {total_down}")
    print(f"  胜率: {win_rate}%")
    print(f"  平均收益: {avg_pnl:+.2f}%")
    print(f"  平均评分: {round(total_score / valid_picks, 1)}")
    
    # 按评分分档统计
    if valid_picks >= 3:
        sorted_by_score = sorted(review_records, key=lambda x: x['score'], reverse=True)
        top_half = sorted_by_score[:len(sorted_by_score)//2 + 1]
        bottom_half = sorted_by_score[len(sorted_by_score)//2 + 1:]
        
        if top_half and bottom_half:
            top_avg = round(sum(p['pnl_from_rec'] for p in top_half) / len(top_half), 2)
            bot_avg = round(sum(p['pnl_from_rec'] for p in bottom_half) / len(bottom_half), 2)
            print(f"\n  评分有效性检验:")
            print(f"    高评分组平均收益: {top_avg:+.2f}%")
            print(f"    低评分组平均收益: {bot_avg:+.2f}%")
            delta = top_avg - bot_avg
            print(f"    差异: {delta:+.2f}% {'✅ 评分有效' if delta > 0 else '⚠️ 评分需修正' if delta < 0 else '➖ 无差异'}")
    
    # 构建复盘记录
    record = {
        'date': pick_date,
        'review_date': today,
        'market_change': indices.get('sh', {}).get('change_pct', 0),
        'total': valid_picks,
        'up': total_up,
        'flat': total_flat,
        'down': total_down,
        'win_rate': win_rate,
        'avg_pnl': avg_pnl,
        'avg_score': round(total_score / valid_picks, 1),
        'picks': review_records
    }
    
    return record


def aggregate_stats(records):
    """汇总所有历史复盘数据，生成累计统计"""
    if not records:
        return None
    
    total_picks = sum(r['total'] for r in records)
    total_up = sum(r['up'] for r in records)
    total_flat = sum(r['flat'] for r in records)
    total_down = sum(r['down'] for r in records)
    
    # 加权平均收益
    total_pnl = sum(r['avg_pnl'] * r['total'] for r in records)
    overall_avg_pnl = round(total_pnl / total_picks, 2) if total_picks > 0 else 0
    
    # 累计胜率
    overall_win_rate = round(total_up / (total_up + total_down) * 100, 1) if (total_up + total_down) > 0 else 0
    
    # 评分有效性：按评分高低分组
    all_picks = []
    for r in records:
        for p in r.get('picks', []):
            all_picks.append(p)
    
    # 评分-收益相关性
    high_score = mid_score = low_score = []
    if len(all_picks) >= 5:
        high_score = [p for p in all_picks if p.get('score', 0) >= 7.5]
        mid_score = [p for p in all_picks if 6 <= p.get('score', 0) < 7.5]
        low_score = [p for p in all_picks if p.get('score', 0) < 6]
    
    hs_avg = round(sum(p['pnl_from_rec'] for p in high_score) / len(high_score), 2) if high_score else None
    ms_avg = round(sum(p['pnl_from_rec'] for p in mid_score) / len(mid_score), 2) if mid_score else None
    ls_avg = round(sum(p['pnl_from_rec'] for p in low_score) / len(low_score), 2) if low_score else None
    
    # 评分分组胜率
    def calc_win_rate(picks_list):
        if not picks_list:
            return None
        ups = sum(1 for p in picks_list if p.get('pnl_from_rec', 0) > 0.3)
        downs = sum(1 for p in picks_list if p.get('pnl_from_rec', 0) < -0.3)
        total_valid = ups + downs
        return round(ups / total_valid * 100, 1) if total_valid > 0 else None
    
    hs_wr = calc_win_rate(high_score) if len(all_picks) >= 5 else None
    ms_wr = calc_win_rate(mid_score) if len(all_picks) >= 5 else None
    ls_wr = calc_win_rate(low_score) if len(all_picks) >= 5 else None
    
    stats = {
        'total_days': len(records),
        'total_picks': total_picks,
        'total_up': total_up,
        'total_flat': total_flat,
        'total_down': total_down,
        'win_rate': overall_win_rate,
        'avg_pnl_per_pick': overall_avg_pnl,
        'high_score_avg_pnl': hs_avg,
        'mid_score_avg_pnl': ms_avg,
        'low_score_avg_pnl': ls_avg,
        'high_score_win_rate': hs_wr,
        'mid_score_win_rate': ms_wr,
        'low_score_win_rate': ls_wr,
    }
    
    return stats


def generate_markdown_report(record, stats):
    """生成Markdown复盘报告"""
    if record is None:
        return None
    
    date_str = record['date']
    
    md = f"""# 📊 盘前精选复盘报告 · {date_str}

## 📈 大盘环境
- 上证指数: {record.get('market_change', 0):+.2f}%
- 总推荐: {record['total']} 只

## 📋 当日表现
| 状态 | 数量 |
|------|:----:|
| ✅ 上涨 | {record['up']} |
| ➖ 平盘 | {record['flat']} |
| ❌ 下跌 | {record['down']} |
| **胜率** | **{record['win_rate']}%** |
| **平均收益** | **{record['avg_pnl']:+.2f}%** |

## 📋 个股详情
| 排名 | 名称 | 代码 | 推荐价 | 评分 | 现价 | 今日涨跌 | 推荐至今 | 判定 |
|:----:|:---:|:---:|:-----:|:---:|:---:|:-------:|:--------:|:---:|
"""
    
    for p in record.get('picks', []):
        zone_str = f"{p['rec_zone']}" if p['rec_zone'] != 'N/A' else '-'
        md += f"| {p['rank']} | {p['name']} | {p['code']} | {p['rec_price']} | {p['score']} | {p['today_price']} | {p['today_change']:+.2f}% | {p['pnl_from_rec']:+.2f}% | {p['verdict']} |\n"
    
    # 累计统计
    if stats and stats['total_days'] > 0:
        md += f"""
## 📈 累计统计（{stats['total_days']}个交易日）
- 总推荐数: {stats['total_picks']}
- ✅ {stats['total_up']} / ➖ {stats['total_flat']} / ❌ {stats['total_down']}
- 累计胜率: **{stats['win_rate']}%**
- 单票平均收益: **{stats['avg_pnl_per_pick']:+.2f}%**

### 评分有效性验证
"""
        if stats['high_score_avg_pnl'] is not None:
            md += f"""
| 评分区间 | 平均收益 | 胜率 |
|:--------:|:-------:|:----:|
| 高分 (≥7.5) | {stats['high_score_avg_pnl']:+.2f}% | {stats['high_score_win_rate']}% |
| 中分 (6~7.4) | {stats['mid_score_avg_pnl']:+.2f}% | {stats['mid_score_win_rate']}% |
| 低分 (<6) | {stats['low_score_avg_pnl']:+.2f}% | {stats['low_score_win_rate']}% |
"""
        
        # 简单判断评分有效性
        if stats['high_score_avg_pnl'] is not None and stats['low_score_avg_pnl'] is not None:
            delta = stats['high_score_avg_pnl'] - stats['low_score_avg_pnl']
            if delta > 1:
                md += f"\n✅ **评分有效**: 高分组成绩明显优于低分组（差异 {delta:+.2f}%）"
            elif delta > 0:
                md += f"\n➖ **评分基本有效**: 高分略优于低分组（差异 {delta:+.2f}%）"
            elif delta == 0:
                md += "\n➖ **评分无差异**: 高分组和低分组收益相同"
            else:
                md += f"\n⚠️ **评分需修正**: 低分组表现反而优于高分组（差异 {delta:+.2f}%）"
    
    md += f"""

---
*报告生成于: {datetime.now().strftime('%Y-%m-%d %H:%M')}*
"""
    
    return md


def save_markdown_report(md, date_str):
    """保存复盘报告到Markdown文件"""
    report_file = os.path.join(REPO_DIR, f'复盘报告_{date_str}.md')
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(md)
    print(f"\n📝 报告已保存: {report_file}")
    return report_file


def main():
    print(f"🔄 盘前精选自动复盘系统")
    print(f"{'='*60}")
    
    # 1. 执行复盘
    record = review_yesterday_picks()
    
    if record is None:
        print("\n今天没有需要复盘的推荐记录。")
        return
    
    # 2. 加载历史
    history = load_history()
    
    # 3. 检查是否已经复盘过这个日期
    existing_dates = [r['date'] for r in history]
    if record['date'] in existing_dates:
        print(f"\nℹ️  {record['date']} 已经复盘过了，跳过")
        return
    
    # 4. 追加新记录
    history.append(record)
    save_history(history)
    
    # 5. 更新 review_picks.json (向后兼容)
    existing_review = load_review_picks()
    existing_dates_rp = [r['date'] for r in existing_review]
    if record['date'] not in existing_dates_rp:
        existing_review.append(record)
        save_review_picks(existing_review)
    
    # 6. 计算累计统计
    stats = aggregate_stats(history)
    
    # 7. 生成Markdown报告
    md = generate_markdown_report(record, stats)
    if md:
        report_file = save_markdown_report(md, record['date'])
    
    # 8. 输出累计统计
    if stats:
        print(f"\n{'='*60}")
        print(f"📈 累计统计（{stats['total_days']}个交易日）")
        print(f"{'='*60}")
        print(f"  总推荐: {stats['total_picks']} 只")
        print(f"  ✅ {stats['total_up']} / ➖ {stats['total_flat']} / ❌ {stats['total_down']}")
        print(f"  累计胜率: {stats['win_rate']}%")
        print(f"  单票平均收益: {stats['avg_pnl_per_pick']:+.2f}%")
        
        if stats['high_score_avg_pnl'] is not None:
            print(f"\n  评分有效性:")
            print(f"    高分 (≥7.5): {stats['high_score_avg_pnl']:+.2f}% (胜率 {stats['high_score_win_rate']}%)")
            print(f"    中分 (6~7.4): {stats['mid_score_avg_pnl']:+.2f}% (胜率 {stats['mid_score_win_rate']}%)")
            print(f"    低分 (<6):    {stats['low_score_avg_pnl']:+.2f}% (胜率 {stats['low_score_win_rate']}%)")
            
            if stats['high_score_avg_pnl'] is not None and stats['low_score_avg_pnl'] is not None:
                delta = stats['high_score_avg_pnl'] - stats['low_score_avg_pnl']
                if delta > 1:
                    print(f"  ✅ 评分有效: 差异 {delta:+.2f}%")
                elif delta > 0:
                    print(f"  ➖ 基本有效: 差异 {delta:+.2f}%")
                else:
                    print(f"  ⚠️ 评分失灵: 差异 {delta:+.2f}%")
    
    print(f"\n✅ 复盘完成！")


if __name__ == '__main__':
    main()
