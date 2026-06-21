"""回测引擎：验证美股→A股联动预测能力"""
import json
import os
import numpy as np
from collections import defaultdict
from scipy.stats import ttest_ind

from services.storage import get_conn, put_conn

BACKTEST_CACHE = os.path.join(os.path.dirname(__file__), "..", "backtest_cache.json")

CONCEPTS = [
    ("苹果产业链", ["苹果概念"]),
    ("特斯拉供应链", ["特斯拉"]),
    ("锂电池/动力电池", ["锂电池", "钠电池", "固态电池"]),
    ("光伏", ["光伏概念", "光伏", "BC电池", "HIT电池"]),
    ("风电", ["风电"]),
    ("新能源", ["新能源"]),
    ("机器人/自动化", ["机器人概念"]),
    ("汽车制造", ["汽车制造业", "汽车电子", "华为汽车"]),
    ("CRO/医药", ["CRO概念", "医药制造业"]),
    ("国防军工", ["国防军工", "军工航天"]),
]

INDICES = [('.IXIC', '纳斯达克'), ('.INX', '标普500'), ('.DJI', '道琼斯')]

BINS = [
    ("↑↑↑ >+2%", 2.0, float('inf')),
    ("↑↑ +1~2%", 1.0, 2.0),
    ("↑ 0~1%", 0.0, 1.0),
    ("↓ -1~0%", -1.0, 0.0),
    ("↓↓ -2~-1%", -2.0, -1.0),
    ("↓↓↓ <-2%", -float('inf'), -2.0),
]


def _clean_code(code: str) -> str:
    for p in ('sh.', 'sz.', 'bj.'):
        if code.startswith(p):
            return code[len(p):]
    return code


def compute_backtest():
    conn = get_conn()
    cur = conn.cursor()

    # 概念→成分股映射
    cur.execute("""
        SELECT sector_code, code FROM sector_stocks
        WHERE trade_date = (SELECT MAX(trade_date) FROM sector_stocks)
        AND code IS NOT NULL AND code != ''
    """)
    sector_map = defaultdict(set)
    for r in cur.fetchall():
        sector_map[r[0]].add(r[1])

    # 三指数日线
    index_data = {}
    for sym, name in INDICES:
        cur.execute(
            "SELECT trade_date, change_pct FROM us_indices WHERE symbol = %s AND change_pct IS NOT NULL ORDER BY trade_date",
            (sym,))
        index_data[sym] = {str(r[0]): float(r[1]) for r in cur.fetchall()}

    # A股全量日线
    cur.execute("SELECT trade_date, code, change_pct FROM stock_hist WHERE trade_date >= '2025-01-01' ORDER BY trade_date, code")
    stock_data = defaultdict(lambda: defaultdict(float))
    for r in cur.fetchall():
        d, code, chg = str(r[0]), r[1], r[2]
        if chg is None:
            continue
        stock_data[d][_clean_code(code)] = float(chg)
    stock_dates = sorted(stock_data.keys())

    # ===== 1. 全量回测：概念 × 指数 =====
    by_concept = []

    for concept_name, keywords in CONCEPTS:
        constituents = set()
        for kw in keywords:
            for sn, codes in sector_map.items():
                if kw in sn:
                    constituents |= codes

        for sym, idx_name in INDICES:
            nas_dict = index_data[sym]
            nas_dates = sorted(nas_dict.keys())

            results = []
            for a_date in stock_dates:
                prev_idx = None
                for nd in nas_dates:
                    if nd >= a_date:
                        break
                    prev_idx = nd
                if not prev_idx:
                    continue
                idx_chg = nas_dict[prev_idx]
                chgs = [v for c in constituents if (v := stock_data.get(a_date, {}).get(c)) is not None]
                if len(chgs) < 5:
                    continue
                results.append({'idx_chg': idx_chg, 'a_chg': np.mean(chgs)})

            if len(results) < 20:
                continue

            up = [r['a_chg'] for r in results if r['idx_chg'] >= 0]
            down = [r['a_chg'] for r in results if r['idx_chg'] < 0]
            extreme_up = [r['a_chg'] for r in results if r['idx_chg'] >= 2.0]
            extreme_down = [r['a_chg'] for r in results if r['idx_chg'] <= -2.0]

            up_avg = float(np.mean(up)) if up else 0
            down_avg = float(np.mean(down)) if down else 0
            diff = up_avg - down_avg
            up_wr = sum(1 for v in up if v > 0) / len(up) * 100 if up else 0
            down_wr = sum(1 for v in down if v > 0) / len(down) * 100 if down else 0

            pval = 1.0
            if len(up) >= 3 and len(down) >= 3:
                try:
                    _, pval = ttest_ind(up, down)
                    pval = float(pval)
                except Exception:
                    pass

            if pval < 0.01:
                sig = "strong"
            elif pval < 0.1:
                sig = "moderate"
            elif pval < 0.3:
                sig = "weak"
            else:
                sig = "none"

            all_vals = np.array([r['a_chg'] for r in results])
            ir = diff / float(all_vals.std()) if all_vals.std() > 0 else 0

            by_concept.append({
                "concept": concept_name,
                "index_symbol": sym,
                "index_name": idx_name,
                "samples": len(results),
                "up_avg": round(up_avg * 100, 3),
                "down_avg": round(down_avg * 100, 3),
                "diff_bps": round(diff * 100, 2),
                "up_winrate": round(up_wr, 1),
                "down_winrate": round(down_wr, 1),
                "p_value": round(pval, 4),
                "significance": sig,
                "info_ratio": round(ir, 3),
                "extreme_up_n": len(extreme_up),
                "extreme_up_avg": round(float(np.mean(extreme_up)) * 100, 3) if extreme_up else None,
                "extreme_down_n": len(extreme_down),
                "extreme_down_avg": round(float(np.mean(extreme_down)) * 100, 3) if extreme_down else None,
            })

    # ===== 2. 按指数汇总 =====
    by_index = []
    for sym, idx_name in INDICES:
        items = [c for c in by_concept if c["index_symbol"] == sym]
        if not items:
            continue
        avg_diff = np.mean([c["diff_bps"] for c in items])
        sig_count = sum(1 for c in items if c["significance"] in ("strong", "moderate"))
        by_index.append({
            "index_symbol": sym,
            "index_name": idx_name,
            "concepts_tested": len(items),
            "avg_diff_bps": round(float(avg_diff), 1),
            "significant_concepts": sig_count,
            "best_concept": max(items, key=lambda c: c["diff_bps"])["concept"],
        })

    # ===== 3. 时间稳定性（锂电池 × 纳指）=====
    constituents = set()
    for kw in ["锂电池", "钠电池", "固态电池"]:
        for sn, codes in sector_map.items():
            if kw in sn:
                constituents |= codes

    nas_dict = index_data['.IXIC']
    nas_dates = sorted(nas_dict.keys())

    all_results = []
    for a_date in stock_dates:
        prev_idx = None
        for nd in nas_dates:
            if nd >= a_date:
                break
            prev_idx = nd
        if not prev_idx:
            continue
        idx_chg = nas_dict[prev_idx]
        chgs = [v for c in constituents if (v := stock_data.get(a_date, {}).get(c)) is not None]
        if len(chgs) < 20:
            continue
        all_results.append({'a_date': a_date, 'idx_chg': idx_chg, 'a_chg': np.mean(chgs)})

    all_results.sort(key=lambda x: x['a_date'])

    WINDOW = 60
    time_stability = []
    for i in range(0, len(all_results) - WINDOW, 10):
        win = all_results[i:i + WINDOW]
        up = [r['a_chg'] for r in win if r['idx_chg'] >= 0]
        down = [r['a_chg'] for r in win if r['idx_chg'] < 0]
        if len(up) < 5 or len(down) < 5:
            continue
        pv = 1.0
        try:
            _, pv = ttest_ind(up, down)
            pv = float(pv)
        except Exception:
            pass
        time_stability.append({
            "window_start": win[0]['a_date'],
            "window_end": win[-1]['a_date'],
            "n": len(win),
            "diff_bps": round(float(np.mean(up) - np.mean(down)) * 100, 2),
            "p_value": round(pv, 4),
            "up_avg": round(float(np.mean(up)) * 100, 3),
            "down_avg": round(float(np.mean(down)) * 100, 3),
        })

    # ===== 4. 极端行情分档 =====
    extreme_analysis = []
    for concept_name, keywords in CONCEPTS:
        constituents = set()
        for kw in keywords:
            for sn, codes in sector_map.items():
                if kw in sn:
                    constituents |= codes

        concept_results = []
        for r in all_results:
            chgs = [v for c in constituents if (v := stock_data.get(r['a_date'], {}).get(c)) is not None]
            if len(chgs) < 5:
                continue
            concept_results.append({
                'idx_chg': r['idx_chg'],
                'a_chg': np.mean(chgs),
                'up_n': sum(1 for v in chgs if v > 0),
                'n': len(chgs),
            })

        bin_data = []
        for label, lo, hi in BINS:
            sub = [r for r in concept_results if lo <= r['idx_chg'] < hi]
            if len(sub) >= 2:
                bin_data.append({
                    "label": label, "n": len(sub),
                    "avg_a_chg": round(float(np.mean([r['a_chg'] for r in sub])) * 100, 3),
                    "winrate": round(sum(1 for r in sub if r['a_chg'] > 0) / len(sub) * 100, 1),
                })
            else:
                bin_data.append({"label": label, "n": 0, "avg_a_chg": None, "winrate": None})

        extreme_analysis.append({"concept": concept_name, "bins": bin_data})

    # ===== 5. Summary =====
    strong = [c for c in by_concept if c["significance"] == "strong"]
    moderate = [c for c in by_concept if c["significance"] == "moderate"]

    output = {
        "summary": {
            "total_tests": len(by_concept),
            "strong_signals": len(strong),
            "moderate_signals": len(moderate),
            "best_signal": max(by_concept, key=lambda c: c["diff_bps"]),
            "data_period": f"{stock_dates[0]} ~ {stock_dates[-1]}",
            "total_aligned_days": len(all_results),
        },
        "by_concept": by_concept,
        "by_index": by_index,
        "extreme_analysis": extreme_analysis,
        "time_stability": time_stability,
        "generated_at": max(stock_dates) if stock_dates else "",
    }

    put_conn(conn)

    with open(BACKTEST_CACHE, 'w') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    return output
