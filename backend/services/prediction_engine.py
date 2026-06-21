"""预测引擎：基于当晚美股 → 预测明日A股概念走势"""
import json
import os
import numpy as np
from datetime import date, timedelta, datetime
from collections import defaultdict

from services.storage import get_conn, put_conn

PREDICTION_CACHE = os.path.join(os.path.dirname(__file__), "..", "prediction_cache.json")

CONCEPTS = [
    ("锂电池", ["锂电池", "钠电池", "固态电池"], "🔋"),
    ("光伏", ["光伏概念", "光伏", "BC电池", "HIT电池"], "☀️"),
    ("新能源", ["新能源"], "⚡"),
    ("风电", ["风电"], "🌬️"),
    ("特斯拉供应链", ["特斯拉"], "🚗"),
    ("苹果产业链", ["苹果概念"], "🍎"),
    ("国防军工", ["国防军工", "军工航天"], "🛡️"),
    ("机器人/自动化", ["机器人概念"], "🤖"),
    ("汽车制造", ["汽车制造业", "汽车电子", "华为汽车"], "🏭"),
    ("CRO/医药", ["CRO概念", "医药制造业"], "💊"),
]

INDICES = [(".IXIC", "纳斯达克", "IXIC"), (".INX", "标普500", "SPX"), (".DJI", "道琼斯", "DJI")]


def _clean_code(code: str) -> str:
    for p in ("sh.", "sz.", "bj."):
        if code.startswith(p):
            return code[len(p):]
    return code


def _load_backtest_stats():
    """从回测数据里提取每个(概念x指数)的均值差/显著性用于置信度计算"""
    cache_path = os.path.join(os.path.dirname(__file__), "..", "backtest_cache.json")
    if os.path.exists(cache_path):
        with open(cache_path) as f:
            data = json.load(f)
        stats = {}
        for c in data.get("by_concept", []):
            key = f"{c['concept']}|{c['index_symbol']}"
            stats[key] = {
                "diff_bps": c["diff_bps"],
                "p_value": c["p_value"],
                "significance": c["significance"],
                "up_winrate": c["up_winrate"],
                "samples": c["samples"],
            }
        return stats
    return {}


def compute_prediction():
    conn = get_conn()
    cur = conn.cursor()

    # 1. 获取最近美股收盘数据
    latest_idx = {}
    for sym, name, abbr in INDICES:
        cur.execute("""
            SELECT trade_date, close, change_pct
            FROM us_indices
            WHERE symbol = %s AND change_pct IS NOT NULL
            ORDER BY trade_date DESC LIMIT 1
        """, (sym,))
        row = cur.fetchone()
        if row:
            latest_idx[sym] = {
                "trade_date": str(row[0]) if row[0] else None,
                "close": float(row[1]) if row[1] else None,
                "change_pct": float(row[2]) if row[2] else None,
                "name": name,
                "abbr": abbr,
            }

    # 2. 获取回测统计数据
    stats = _load_backtest_stats()

    # 3. 获取概念成分股数量
    cur.execute("SELECT sector_code, code FROM sector_stocks WHERE trade_date = (SELECT MAX(trade_date) FROM sector_stocks) AND code IS NOT NULL AND code != ''")
    sector_map = defaultdict(set)
    for r in cur.fetchall():
        sector_map[r[0]].add(r[1])

    # 4. 获取A股最近交易日
    cur.execute("SELECT MAX(trade_date) FROM stock_hist")
    row = cur.fetchone()
    last_a_date = str(row[0]) if row and row[0] else ""

    put_conn(conn)

    # 5. 为每个概念生成预测
    predictions = []
    for concept_name, keywords, icon in CONCEPTS:
        constituents = set()
        for kw in keywords:
            for sn, codes in sector_map.items():
                if kw in sn:
                    constituents |= codes

        total_stocks = len(constituents) if constituents else 1

        # 对每个指数的信号评分
        index_signals = []
        for sym, name, abbr in INDICES:
            idx_data = latest_idx.get(sym, {})
            idx_chg = idx_data.get("change_pct")
            if idx_chg is None:
                continue

            stat_key = f"{concept_name}|{sym}"
            bt = stats.get(stat_key, {})
            diff_bps = bt.get("diff_bps", 0)
            p_val = bt.get("p_value", 1.0)
            sig_level = bt.get("significance", "none")
            up_wr = bt.get("up_winrate", 50)
            samples = bt.get("samples", 0)

            # 基于回测diff_bps估算预期涨幅
            # 如果纳指涨X%，回测显示概念均值差D bps
            # 简单线性映射：预期概念涨幅 ≈ idx_chg * (diff_bps/100) / avg_idx_move
            # 更保守：直接用 up_avg - down_avg 的方向性
            expected_sign = 1 if idx_chg >= 0 else -1

            if sig_level == "strong":
                confidence = 80 + min(20, (1 - p_val) * 200)
            elif sig_level == "moderate":
                confidence = 55 + min(25, (1 - p_val) * 150)
            elif sig_level == "weak":
                confidence = 40 + (1 - p_val) * 50
            else:
                confidence = 30 + min(20, (1 - p_val) * 30)

            confidence = min(95, max(5, confidence))

            # 预期A股涨跌幅（保守估计）
            # 用回测 mean diff 的 50% 映射到当前美股涨跌幅
            if abs(idx_chg) < 0.1:
                expected_a_chg = 0
            else:
                # diff_bps 是 up_avg - down_avg 的差值（基点）
                # 乘以相关性衰减因子
                signal_strength = diff_bps / 30  # normalize: 30bp算是中等信号
                expected_a_chg = idx_chg * max(0.05, min(0.25, abs(signal_strength))) * expected_sign
                if abs(expected_a_chg) > 5:
                    expected_a_chg = np.sign(expected_a_chg) * 5

            index_signals.append({
                "index_symbol": sym,
                "index_name": name,
                "index_abbr": abbr,
                "us_chg": round(idx_chg, 2),
                "expected_a_chg": round(expected_a_chg, 2),
                "confidence": round(confidence, 0),
                "diff_bps": diff_bps,
                "p_value": round(p_val, 4),
                "significance": sig_level,
                "up_winrate": up_wr,
                "samples": samples,
            })

        if not index_signals:
            continue

        # 多指数共识：指数方向相同时增强置信度
        directions = [1 if s["us_chg"] >= 0 else -1 for s in index_signals]
        consensus = sum(1 for d in directions if d == directions[0]) / len(directions)

        # 加权平均预期
        weights = [s["confidence"] for s in index_signals]
        total_w = sum(weights)
        avg_expected = sum(s["expected_a_chg"] * w for s, w in zip(index_signals, weights)) / total_w if total_w > 0 else 0

        # 获取最高置信度的单个指数预测
        best_signal = max(index_signals, key=lambda s: s["confidence"])

        # 极端行情标记
        extreme = ""
        extreme_nas = index_signals[0]["us_chg"] if index_signals else 0
        if extreme_nas >= 2.0:
            extreme = "bull_strong"
        elif extreme_nas <= -2.0:
            extreme = "bear_strong"
        elif extreme_nas >= 1.0:
            extreme = "bull_moderate"

        predictions.append({
            "concept": concept_name,
            "icon": icon,
            "total_stocks": total_stocks,
            "signals": index_signals,
            "consensus": round(consensus * 100, 0),
            "avg_expected": round(avg_expected, 2),
            "direction": "bull" if avg_expected > 0.05 else "bear" if avg_expected < -0.05 else "neutral",
            "extreme_alert": extreme,
            "best_signal": best_signal,
        })

    # 按 预期幅度绝对值 排序
    predictions.sort(key=lambda p: abs(p["avg_expected"]), reverse=True)

    output = {
        "generated_at": datetime.now().isoformat(),
        "us_market_date": latest_idx.get(".IXIC", {}).get("trade_date", ""),
        "a_market_date": last_a_date,
        "indices": [v for v in latest_idx.values()],
        "predictions": predictions,
        "disclaimer": "基于历史回测统计，不构成投资建议。过去表现不代表未来收益。",
    }

    with open(PREDICTION_CACHE, "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    return output
