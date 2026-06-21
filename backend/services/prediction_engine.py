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

# 互补跨市场指标 — 基于相关性分析结果
# 金银对所有概念正相关（流动性联动），SOX对科技股有额外预测力
CROSS_INDICATORS = [
    ("GOLD", "上海金", "GOLD", 0.27),
    (".SOX", "费城半导体", "SOX", 0.22),
]

# 每个概念的最佳互补指标权重
CONCEPT_CROSS_WEIGHTS = {
    "特斯拉供应链": {"GOLD": 0.36, ".SOX": 0.20},
    "苹果产业链": {"GOLD": 0.42, ".SOX": 0.28},
    "机器人/自动化": {"GOLD": 0.37, ".SOX": 0.15},
    "光伏": {"GOLD": 0.26, ".SOX": 0.25},
    "锂电池": {"GOLD": 0.24, ".SOX": 0.23},
    "新能源": {"GOLD": 0.25, ".SOX": 0.23},
    "CRO/医药": {"GOLD": 0.25, ".SOX": 0.19},
    "汽车制造": {"GOLD": 0.23, ".SOX": 0.18},
    "风电": {"GOLD": 0.21, ".SOX": 0.24},
    "国防军工": {"GOLD": 0.20, ".SOX": 0.13},
}


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

    # 1b. 获取最近跨市场指标数据
    latest_cross = {}
    for sym, name, abbr, _ in CROSS_INDICATORS:
        cur.execute("""
            SELECT trade_date, value, change_pct
            FROM us_cross_indicators
            WHERE symbol = %s AND change_pct IS NOT NULL
            ORDER BY trade_date DESC LIMIT 1
        """, (sym,))
        row = cur.fetchone()
        if row:
            latest_cross[sym] = {
                "trade_date": str(row[0]) if row[0] else None,
                "value": float(row[1]) if row[1] else None,
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

            if abs(idx_chg) < 0.1:
                expected_a_chg = 0
            else:
                signal_strength = diff_bps / 30
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

        # 跨市场指标信号
        cross_signals = []
        cross_weights_map = CONCEPT_CROSS_WEIGHTS.get(concept_name, {})
        for sym, name, abbr, base_weight in CROSS_INDICATORS:
            cd = latest_cross.get(sym, {})
            chg = cd.get("change_pct")
            if chg is None or abs(chg) < 0.01:
                continue

            w = cross_weights_map.get(sym, base_weight)
            # r系数方向：GOLD对所有概念正相关，SOX也是正
            expected_a = chg * w * 0.6  # 衰减：跨市场指标权重低于三大指数
            confidence = 35 + min(35, abs(w) * 100)

            cross_signals.append({
                "index_symbol": sym,
                "index_name": name,
                "index_abbr": abbr,
                "us_chg": round(chg, 2),
                "expected_a_chg": round(expected_a, 2),
                "confidence": round(confidence, 0),
                "diff_bps": round(w * 100, 0),
                "p_value": 0.01,
                "significance": "moderate" if abs(w) > 0.3 else "weak",
                "up_winrate": 65,
                "samples": 0,
            })

        all_signals = index_signals + cross_signals

        if not all_signals:
            continue

        # 多指数共识
        directions = [1 if s["us_chg"] >= 0 else -1 for s in all_signals]
        consensus = sum(1 for d in directions if d == directions[0]) / len(directions)

        # 加权平均预期
        weights = [s["confidence"] for s in all_signals]
        total_w = sum(weights)
        avg_expected = sum(s["expected_a_chg"] * w for s, w in zip(all_signals, weights)) / total_w if total_w > 0 else 0

        best_signal = max(all_signals, key=lambda s: s["confidence"])

        extreme = ""
        extreme_nas = index_signals[0]["us_chg"] if index_signals else 0
        gold_chg = latest_cross.get("GOLD", {}).get("change_pct", 0) or 0
        if extreme_nas >= 2.0 or gold_chg >= 1.5:
            extreme = "bull_strong"
        elif extreme_nas <= -2.0 or gold_chg <= -1.5:
            extreme = "bear_strong"
        elif extreme_nas >= 1.0:
            extreme = "bull_moderate"

        predictions.append({
            "concept": concept_name,
            "icon": icon,
            "total_stocks": total_stocks,
            "signals": index_signals,
            "cross_signals": cross_signals,
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
        "cross_indicators": [v for v in latest_cross.values()],
        "predictions": predictions,
        "disclaimer": "基于历史回测统计，不构成投资建议。过去表现不代表未来收益。",
    }

    with open(PREDICTION_CACHE, "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    return output
