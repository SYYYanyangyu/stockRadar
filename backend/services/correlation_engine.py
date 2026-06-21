"""美股→A股联动计算引擎 — 滚动Pearson相关系数 + Beta + 隔夜预期差 + 概念聚合"""
from datetime import date
from collections import defaultdict
import json

import numpy as np
from scipy.stats import pearsonr

from services.storage import get_conn, put_conn


def _d(rows, field):
    """安全取数值字段"""
    v = rows.get(field)
    return float(v) if v is not None else None


def compute_us_correlation():
    """
    预计算所有A股与美股三大指数的联动指标，写入 us_correlation_result 表。

    时间对齐：A股 T日 收益率 ↔ 美股 T-1日 收益率
    """
    conn = get_conn()
    try:
        cur = conn.cursor()

        # 1. 获取最新 calc_date (A股最近交易日)
        cur.execute("SELECT MAX(trade_date) FROM stock_hist")
        row = cur.fetchone()
        if not row or not row[0]:
            print("  [联动] ⚠️ stock_hist 无数据")
            return
        calc_date = str(row[0])

        # 2. 读取美股指数最近 60 天数据
        cur.execute("""
            SELECT symbol, trade_date, close, change_pct
            FROM us_indices
            WHERE trade_date <= %s
            ORDER BY symbol, trade_date
        """, (calc_date,))
        us_rows = cur.fetchall()
        if not us_rows:
            print("  [联动] ⚠️ us_indices 无数据")
            return

        us_data: dict[str, list[tuple[str, float, float]]] = defaultdict(list)
        for r in us_rows:
            # r: (symbol, trade_date, close, change_pct)
            us_data[r[0]].append((r[1], float(r[2]) if r[2] else None, float(r[3]) if r[3] else None))

        # 3. 读取所有A股最近 90 天数据 (含 open)
        cur.execute("""
            SELECT code, trade_date, close, open, change_pct
            FROM stock_hist
            WHERE trade_date >= (SELECT MAX(trade_date) FROM stock_hist) - INTERVAL '90 days'
            ORDER BY code, trade_date
        """)
        a_rows = cur.fetchall()

        # 按股票分组
        a_stock_data: dict[str, list[tuple[str, float, float, float]]] = defaultdict(list)
        for r in a_rows:
            # r: (code, trade_date, close, open, change_pct)
            a_stock_data[r[0]].append((
                r[1],
                float(r[2]) if r[2] else None,
                float(r[3]) if r[3] else None,
                float(r[4]) if r[4] else None,
            ))

        # 4. 获取股票名称映射 (stock_hist code is like "sh.600000", stock_name is "600000")
        cur.execute("SELECT code, name FROM stock_name")
        name_map: dict[str, str] = {r[0]: r[1] for r in cur.fetchall()}

        def _get_name(code: str) -> str:
            """strip prefix for name lookup: sh.600000 → 600000"""
            return name_map.get(code.replace("sh.", "").replace("sz.", "").replace("bj.", ""), "")

        # 5. 对每个美股指数，计算所有A股联动
        all_results = []
        for us_symbol, us_rows_list in us_data.items():
            # 构建美股日期→收益率映射
            us_date_ret: dict[str, float] = {}
            for i in range(1, len(us_rows_list)):
                prev_close = us_rows_list[i - 1][1]
                curr_close = us_rows_list[i][1]
                if prev_close and prev_close > 0 and curr_close is not None:
                    us_date_ret[us_rows_list[i][0]] = (curr_close / prev_close - 1) * 100

            if len(us_date_ret) < 15:
                print(f"  [{us_symbol}] ⚠️ 有效数据不足15天，跳过")
                continue

            # 取最近一天美股涨跌幅
            latest_us_row = us_rows_list[-1]
            latest_us_date = latest_us_row[0]
            latest_us_change = latest_us_row[2] or 0

            for stock_code, stock_rows in a_stock_data.items():
                if len(stock_rows) < 20:
                    continue

                # 构建 A股日期→日收益率 (按时间顺序)
                a_dates = []
                a_rets = []
                for i in range(1, len(stock_rows)):
                    prev_close = stock_rows[i - 1][1]
                    curr_close = stock_rows[i][1]
                    if prev_close and prev_close > 0 and curr_close is not None:
                        a_dates.append(stock_rows[i][0])
                        a_rets.append((curr_close / prev_close - 1) * 100)

                if len(a_rets) < 20:
                    continue

                # 时间对齐：A股 T日 收益率 ↔ 美股 T-1日 收益率（最近一个严格小于A日的美股日）
                aligned = []
                us_dates_sorted = sorted(us_date_ret.keys())
                for ai, a_date in enumerate(a_dates):
                    # Find latest US date strictly before this A-share date
                    prev_us_date = None
                    for usd in us_dates_sorted:
                        if usd >= a_date:
                            break
                        prev_us_date = usd
                    if prev_us_date and prev_us_date in us_date_ret:
                        aligned.append((a_rets[ai], us_date_ret[prev_us_date]))

                if len(aligned) < 20:
                    continue

                a_aligned = np.array([x[0] for x in aligned])
                us_aligned = np.array([x[1] for x in aligned])

                # 滚动相关系数（10/15/20日 — 避免5日n太小导致的伪相关）
                corr_10d = _pearson(a_aligned[-10:], us_aligned[-10:])
                corr_15d = _pearson(a_aligned[-15:], us_aligned[-15:])
                corr_20d = _pearson(a_aligned[-20:], us_aligned[-20:])

                # Beta: 用最近20对齐点
                beta = _beta(a_aligned[-20:], us_aligned[-20:])

                # 隔夜预期差: 美股涨幅 × beta - A股今日涨跌幅
                # A股当日涨跌幅（取最后一行）
                a_stock_change = stock_rows[-1][3] or 0
                overnight_gap = round(latest_us_change * beta - a_stock_change, 2) if beta is not None else None

                all_results.append({
                    "calc_date": calc_date,
                    "us_index": us_symbol,
                    "stock_code": stock_code,
                    "stock_name": _get_name(stock_code),
                    "corr_10d": float(round(corr_10d, 4)) if corr_10d is not None else None,
                    "corr_15d": float(round(corr_15d, 4)) if corr_15d is not None else None,
                    "corr_20d": float(round(corr_20d, 4)) if corr_20d is not None else None,
                    "beta": float(round(beta, 4)) if beta is not None else None,
                    "overnight_gap": float(overnight_gap) if overnight_gap is not None else None,
                    "a_stock_change": float(round(a_stock_change, 2)),
                    "us_change": float(round(latest_us_change, 2)),
                })

        # Deduplicate
        seen = set()
        final_results = []
        for r in sorted(all_results, key=lambda x: x["corr_10d"] or 0, reverse=True):
            key = (r["calc_date"], r["us_index"], r["stock_code"])
            if key in seen:
                continue
            seen.add(key)
            final_results.append(r)

        # 6. 清空当日旧结果并写入（存储全部有效结果，概念聚合需要完整的成分股覆盖）
        if final_results:
            for us_symbol in [".IXIC", ".DJI", ".INX"]:
                cur.execute(
                    "DELETE FROM us_correlation_result WHERE calc_date = %s AND us_index = %s",
                    (calc_date, us_symbol),
                )

            for r in final_results:
                cur.execute("""
                    INSERT INTO us_correlation_result
                        (calc_date, us_index, stock_code, stock_name,
                         corr_10d, corr_15d, corr_20d, beta, overnight_gap,
                         a_stock_change, us_change)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (calc_date, us_index, stock_code) DO UPDATE SET
                        stock_name=EXCLUDED.stock_name,
                        corr_10d=EXCLUDED.corr_10d,
                        corr_15d=EXCLUDED.corr_15d,
                        corr_20d=EXCLUDED.corr_20d,
                        beta=EXCLUDED.beta,
                        overnight_gap=EXCLUDED.overnight_gap,
                        a_stock_change=EXCLUDED.a_stock_change,
                        us_change=EXCLUDED.us_change
                """, (
                    r["calc_date"], r["us_index"], r["stock_code"], r["stock_name"],
                    r["corr_10d"], r["corr_15d"], r["corr_20d"], r["beta"],
                    r["overnight_gap"], r["a_stock_change"], r["us_change"],
                ))

            conn.commit()
            per_idx = {sym: sum(1 for r in final_results if r["us_index"] == sym) for sym in [".IXIC", ".DJI", ".INX"]}
            print(f"  [联动] ✅ {len(final_results)} 条写入 us_correlation_result (calc_date={calc_date}) "
                  f"| IXIC:{per_idx['.IXIC']} DJI:{per_idx['.DJI']} INX:{per_idx['.INX']}")
        else:
            print("  [联动] ⚠️ 无有效结果")

    finally:
        put_conn(conn)


def _pearson(a: np.ndarray, b: np.ndarray) -> float | None:
    """安全计算 Pearson 相关系数，最少需要10个样本点"""
    if len(a) < 10 or len(b) < 10:
        return None
    if np.std(a) < 1e-8 or np.std(b) < 1e-8:
        return None
    try:
        r, _ = pearsonr(a, b)
        return float(r) if not np.isnan(r) else None
    except Exception:
        return None


def _beta(a: np.ndarray, b: np.ndarray) -> float | None:
    """线性回归斜率 Beta = cov(a,b) / var(b)，最少需要10个样本点"""
    if len(a) < 10 or len(b) < 10:
        return None
    var_b = np.var(b)
    if var_b < 1e-8:
        return None
    return float(np.cov(a, b)[0, 1] / var_b)


# ── 概念聚合 ────────────────────────────────────────────

# 概念定义：(展示名, sector_stocks 匹配关键词, 美股映射权重, 图标)
CONCEPT_DEFS = [
    ("苹果产业链", ["苹果概念"], 1.0, "📱"),
    ("特斯拉供应链", ["特斯拉"], 1.0, "🚗"),
    ("锂电池/动力电池", ["锂电池", "钠电池", "固态电池"], 0.9, "🔋"),
    ("光伏", ["光伏概念", "光伏", "BC电池", "HIT电池"], 0.85, "☀️"),
    ("风电", ["风电"], 0.80, "🌬️"),
    ("新能源", ["新能源"], 0.78, "⚡"),
    ("机器人/自动化", ["机器人概念"], 0.75, "🤖"),
    ("汽车制造", ["汽车制造业", "汽车电子", "华为汽车"], 0.72, "🏭"),
    ("CRO/医药", ["CRO概念", "医药制造业"], 0.65, "💊"),
    ("国防军工", ["国防军工", "军工航天"], 0.60, "🛡️"),
]


def _strip_code(code: str) -> str:
    """sz.300118 → 300118, sz300118 → 300118"""
    for p in ("sh.", "sz.", "bj.", "sh", "sz", "bj"):
        if code.lower().startswith(p.lower()):
            return code[len(p):].lstrip(".")
    return code


def compute_concept_correlation():
    """
    从 us_correlation_result（个股）聚合到概念维度，写入 us_concept_correlation。
    需要先运行 compute_us_correlation()。
    """
    conn = get_conn()
    try:
        cur = conn.cursor()

        cur.execute("SELECT MAX(calc_date) FROM us_correlation_result")
        row = cur.fetchone()
        if not row or not row[0]:
            print("  [概念聚合] ⚠️ us_correlation_result 无数据，跳过")
            return
        calc_date = str(row[0])

        # 读取所有 sector_stocks 最新日期的概念→代码映射
        cur.execute("SELECT MAX(trade_date) FROM sector_stocks")
        latest_ss = cur.fetchone()[0]
        cur.execute(
            "SELECT sector_code, code FROM sector_stocks WHERE trade_date = %s AND code IS NOT NULL AND code != ''",
            (latest_ss,),
        )
        sector_map: dict[str, set[str]] = defaultdict(set)
        for r in cur.fetchall():
            sector_map[r[0]].add(r[1])

        # 读取 us_correlation_result 中所有个股数据
        cur.execute(
            """SELECT stock_code, stock_name, us_index,
                      corr_10d, corr_15d, corr_20d,
                      beta, overnight_gap, a_stock_change, us_change
               FROM us_correlation_result WHERE calc_date = %s""",
            (calc_date,),
        )
        stock_data: dict[str, dict] = {}
        for r in cur.fetchall():
            code = _strip_code(r[0])
            stock_data[code] = {
                "name": r[1], "us_index": r[2],
                "corr_10d": float(r[3]) if r[3] else None,
                "corr_15d": float(r[4]) if r[4] else None,
                "corr_20d": float(r[5]) if r[5] else None,
                "beta": float(r[6]) if r[6] else None,
                "gap": float(r[7]) if r[7] else None,
                "a_chg": float(r[8]) if r[8] else None,
                "us_chg": float(r[9]) if r[9] else None,
            }

        # 拉取当日成交额作为市值/流动性代理权重（log scale）
        cur.execute("SELECT MAX(trade_date) FROM gainers")
        gd = cur.fetchone()
        amount_map: dict[str, float] = {}
        if gd and gd[0]:
            cur.execute("SELECT code, amount FROM gainers WHERE trade_date = %s", (str(gd[0]),))
            for r in cur.fetchall():
                code = _strip_code(r[0])
                amt = float(r[1]) if r[1] else 0
                if amt > 0:
                    amount_map[code] = amt

        all_results = []
        for us_index in [".IXIC", ".INX", ".DJI"]:
            for concept_name, keywords, weight, icon in CONCEPT_DEFS:
                # 收集该概念的成分股
                constituents = set()
                for kw in keywords:
                    for sector_name, codes in sector_map.items():
                        if kw in sector_name:
                            constituents |= codes

                if len(constituents) < 5:
                    continue

                # 筛选有相关数据的成分股
                period_data: dict[str, list[float]] = {
                    "10d": [], "15d": [], "20d": []
                }
                betas = []
                all_candidates: list[tuple[str, dict]] = []

                for code in constituents:
                    sd = stock_data.get(code)
                    if not sd or sd["us_index"] != us_index:
                        continue
                    all_candidates.append((code, sd))

                # 只取有显著相关性的成分股 (|corr| ≥ 0.3) 计算聚合指标
                significant_10d = [sd for _, sd in all_candidates if sd["corr_10d"] is not None and abs(sd["corr_10d"]) >= 0.3]
                significant_15d = [sd for _, sd in all_candidates if sd["corr_15d"] is not None and abs(sd["corr_15d"]) >= 0.3]
                significant_20d = [sd for _, sd in all_candidates if sd["corr_20d"] is not None and abs(sd["corr_20d"]) >= 0.3]

                for code, sd in all_candidates:
                    for p in ["10d", "15d", "20d"]:
                        v = sd[f"corr_{p}"]
                        if v is not None:
                            period_data[p].append(v)
                    if sd["beta"] is not None:
                        betas.append((code, sd["beta"], sd["name"],
                                      sd.get("corr_10d") or 0,
                                      sd.get("gap"),
                                      sd.get("a_chg"),
                                      sd.get("corr_15d") or 0,
                                      sd.get("corr_20d") or 0))

                total_with_data = len(period_data["10d"])
                if total_with_data < 3:
                    continue

                # 各周期统计（基于显著相关性股票）
                stats = {}
                for p, sig_data in [("10d", significant_10d), ("15d", significant_15d), ("20d", significant_20d)]:
                    if len(sig_data) >= 3:
                        corr_vals = np.array([s[f"corr_{p}"] for s in sig_data])
                        avg = float(corr_vals.mean())
                        std = float(corr_vals.std()) if len(corr_vals) > 1 else 0.0
                        consist = max(0.0, 1.0 - std / max(abs(avg), 0.01))
                        signal_ratio = len(sig_data) / max(total_with_data, 1)
                        composite = round(abs(avg) * consist * weight * (0.5 + 0.5 * signal_ratio), 4)
                        stats[p] = {
                            "avg": round(avg, 4), "std": round(std, 4),
                            "consistency": round(consist, 4),
                            "composite_score": composite,
                            "signal_count": len(sig_data),
                        }
                    else:
                        stats[p] = {
                            "avg": round(float(np.mean(period_data[p])), 4) if period_data[p] else 0.0,
                            "std": 0.0, "consistency": 0.0, "composite_score": 0.0,
                            "signal_count": 0,
                        }

                avg_beta = round(float(np.mean([b[1] for b in betas])), 2) if betas else None

                # 成分股排序：|corr| × log(amount) × |beta| — 大市值+强传导优先
                # log(amount) 压缩成交额差异，|beta| 反映隔夜传导强度
                def _rank_score(b: tuple) -> float:
                    corr = abs(b[3])
                    beta_abs = abs(b[1]) if b[1] else 0
                    amt = amount_map.get(b[0], 1e7)  # default ~1千万
                    log_amt = np.log10(max(amt, 1e6))
                    return corr * log_amt * max(beta_abs, 0.2)

                betas.sort(key=_rank_score, reverse=True)
                top_stocks = [
                    {"code": b[0], "name": b[2], "corr": round(b[3], 4),
                     "beta": round(b[1], 2) if b[1] else None,
                     "gap": round(b[4], 2) if b[4] else None,
                     "a_chg": round(b[5], 2) if b[5] else None,
                     "amount": round(amount_map.get(b[0], 0) / 1e8, 1)}  # 亿元
                    for b in betas[:8]
                ]

                all_results.append({
                    "calc_date": calc_date,
                    "us_index": us_index,
                    "concept_name": concept_name,
                    "icon": icon,
                    "stock_count": stats["10d"].get("signal_count", 0),
                    "total_constituents": len(constituents),
                    "corr_10d_avg": stats["10d"]["avg"],
                    "corr_15d_avg": stats["15d"]["avg"],
                    "corr_20d_avg": stats["20d"]["avg"],
                    "corr_10d_std": stats["10d"]["std"],
                    "corr_15d_std": stats["15d"]["std"],
                    "corr_20d_std": stats["20d"]["std"],
                    "consistency_10d": stats["10d"]["consistency"],
                    "consistency_15d": stats["15d"]["consistency"],
                    "consistency_20d": stats["20d"]["consistency"],
                    "composite_score_10d": stats["10d"]["composite_score"],
                    "composite_score_15d": stats["15d"]["composite_score"],
                    "composite_score_20d": stats["20d"]["composite_score"],
                    "avg_beta": avg_beta,
                    "top_stocks": json.dumps(top_stocks, ensure_ascii=False),
                })

        # 写入
        if all_results:
            cur.execute("DELETE FROM us_concept_correlation WHERE calc_date = %s", (calc_date,))
            for r in all_results:
                cur.execute("""
                    INSERT INTO us_concept_correlation
                        (calc_date, us_index, concept_name, icon,
                         stock_count, total_constituents,
                         corr_10d_avg, corr_15d_avg, corr_20d_avg,
                         corr_10d_std, corr_15d_std, corr_20d_std,
                         consistency_10d, consistency_15d, consistency_20d,
                         composite_score_10d, composite_score_15d, composite_score_20d,
                         avg_beta, top_stocks)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (calc_date, us_index, concept_name) DO UPDATE SET
                        icon=EXCLUDED.icon,
                        stock_count=EXCLUDED.stock_count,
                        total_constituents=EXCLUDED.total_constituents,
                        corr_10d_avg=EXCLUDED.corr_10d_avg,
                        corr_15d_avg=EXCLUDED.corr_15d_avg,
                        corr_20d_avg=EXCLUDED.corr_20d_avg,
                        corr_10d_std=EXCLUDED.corr_10d_std,
                        corr_15d_std=EXCLUDED.corr_15d_std,
                        corr_20d_std=EXCLUDED.corr_20d_std,
                        consistency_10d=EXCLUDED.consistency_10d,
                        consistency_15d=EXCLUDED.consistency_15d,
                        consistency_20d=EXCLUDED.consistency_20d,
                        composite_score_10d=EXCLUDED.composite_score_10d,
                        composite_score_15d=EXCLUDED.composite_score_15d,
                        composite_score_20d=EXCLUDED.composite_score_20d,
                        avg_beta=EXCLUDED.avg_beta,
                        top_stocks=EXCLUDED.top_stocks
                """, (
                    r["calc_date"], r["us_index"], r["concept_name"], r["icon"],
                    r["stock_count"], r["total_constituents"],
                    r["corr_10d_avg"], r["corr_15d_avg"], r["corr_20d_avg"],
                    r["corr_10d_std"], r["corr_15d_std"], r["corr_20d_std"],
                    r["consistency_10d"], r["consistency_15d"], r["consistency_20d"],
                    r["composite_score_10d"], r["composite_score_15d"], r["composite_score_20d"],
                    r["avg_beta"], r["top_stocks"],
                ))
            conn.commit()
            print(f"  [概念聚合] ✅ {len(all_results)} 条写入 us_concept_correlation (calc_date={calc_date})")
        else:
            print("  [概念聚合] ⚠️ 无有效概念数据")

    finally:
        put_conn(conn)
