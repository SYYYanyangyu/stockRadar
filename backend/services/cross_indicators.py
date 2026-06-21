"""跨市场联动指标 — 拉取和存储"""
import sys, os, time, threading
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import akshare as ak
import pandas as pd
from datetime import date, timedelta

from services.storage import get_conn, put_conn, upsert_many

_lock = threading.Lock()
_last_call = 0


def _wait():
    global _last_call
    with _lock:
        elapsed = time.time() - _last_call
        if elapsed < 2.0:
            time.sleep(2.0 - elapsed)
        _last_call = time.time()


def _ak(fn, name: str):
    _wait()
    try:
        return fn()
    except Exception as e:
        print(f"  [{name}] ⚠️ {type(e).__name__}: {str(e)[:60]}")
        return None


# ══════════════════════════════════════════
# 1. SOX 费城半导体指数 (.SOX via sina)
# ══════════════════════════════════════════
def pull_sox_index():
    print("\n🔧 费城半导体指数 (.SOX)")
    df = _ak(lambda: ak.index_us_stock_sina(symbol=".SOX"), "SOX")
    if df is None or df.empty:
        print("  ❌ 无数据")
        return

    rows = []
    for _, rd in df.iterrows():
        rows.append({
            "symbol": ".SOX",
            "trade_date": str(rd.get("date", "")),
            "close": float(rd["close"]),
            "change_pct": None,  # will be computed
            "open": float(rd["open"]) if rd.get("open") else None,
            "high": float(rd["high"]) if rd.get("high") else None,
            "low": float(rd["low"]) if rd.get("low") else None,
            "volume": float(rd["volume"]) if rd.get("volume") else None,
        })

    # compute change_pct
    for i in range(1, len(rows)):
        if rows[i]["close"] and rows[i - 1]["close"] and rows[i - 1]["close"] > 0:
            rows[i]["change_pct"] = round(
                (rows[i]["close"] / rows[i - 1]["close"] - 1) * 100, 2
            )

    if rows:
        upsert_many("us_cross_indicators", [
            {
                "symbol": r["symbol"],
                "trade_date": r["trade_date"],
                "name": "费城半导体",
                "value": r["close"],
                "change_pct": r["change_pct"],
            }
            for r in rows
        ], conflict_cols=["symbol", "trade_date"])
        print(f"  ✅ {len(rows)} rows")


# ══════════════════════════════════════════
# 2. US Treasury 10Y yield (from bond_zh_us_rate)
# ══════════════════════════════════════════
def pull_us10y_yield():
    print("\n💰 美国10年期国债收益率")
    df = _ak(lambda: ak.bond_zh_us_rate(), "US10Y")
    if df is None or df.empty:
        print("  ❌ 无数据")
        return

    rows = []
    for _, rd in df.iterrows():
        dt = str(rd.get("日期", ""))
        yld = rd.get("美国国债收益率10年")
        if pd.isna(yld) or not dt:
            continue

        rows.append({
            "symbol": "US10Y",
            "trade_date": dt,
            "name": "美国10年国债",
            "value": float(yld),
            "change_pct": None,
        })

    # compute daily change
    for i in range(1, len(rows)):
        if rows[i]["value"] is not None:
            diff = rows[i]["value"] - rows[i - 1]["value"]
            rows[i]["change_pct"] = round(diff, 2)  # absolute bp change

    if rows:
        upsert_many("us_cross_indicators", rows, conflict_cols=["symbol", "trade_date"])
        print(f"  ✅ {len(rows)} rows")


# ══════════════════════════════════════════
# 3. CNY/USD exchange rate (from currency_boc_sina)
# ══════════════════════════════════════════
def pull_cny_rate():
    print("\n💱 人民币汇率 (美元兑人民币)")
    df = _ak(lambda: ak.currency_boc_sina(symbol="美元"), "CNY")
    if df is None or df.empty:
        print("  ❌ 无数据")
        return

    rows = []
    for _, rd in df.iterrows():
        dt = str(rd.get("日期", ""))
        mid = rd.get("央行中间价")
        if pd.isna(mid) or not dt:
            continue

        rows.append({
            "symbol": "USDCNY",
            "trade_date": dt,
            "name": "美元兑人民币中间价",
            "value": float(mid),
            "change_pct": None,
        })

    for i in range(1, len(rows)):
        if rows[i]["value"] and rows[i - 1]["value"] and rows[i - 1]["value"] > 0:
            rows[i]["change_pct"] = round(
                (rows[i]["value"] / rows[i - 1]["value"] - 1) * 100, 2
            )

    if rows:
        upsert_many("us_cross_indicators", rows, conflict_cols=["symbol", "trade_date"])
        print(f"  ✅ {len(rows)} rows")


# ══════════════════════════════════════════
# 4. Gold price (上海金基准价)
# ══════════════════════════════════════════
def pull_gold_price():
    print("\n🥇 黄金价格 (上海金基准价)")
    df = _ak(lambda: ak.spot_golden_benchmark_sge(), "GOLD")
    if df is None or df.empty:
        print("  ❌ 无数据")
        return

    rows = []
    for _, rd in df.iterrows():
        dt = str(rd.get("交易时间", ""))
        # Use 早盘价 as daily value
        val = rd.get("早盘价")
        if pd.isna(val) or not dt:
            continue

        rows.append({
            "symbol": "GOLD",
            "trade_date": dt,
            "name": "上海金基准价",
            "value": float(val),
            "change_pct": None,
        })

    for i in range(1, len(rows)):
        if rows[i]["value"] and rows[i - 1]["value"] and rows[i - 1]["value"] > 0:
            rows[i]["change_pct"] = round(
                (rows[i]["value"] / rows[i - 1]["value"] - 1) * 100, 2
            )

    if rows:
        upsert_many("us_cross_indicators", rows, conflict_cols=["symbol", "trade_date"])
        print(f"  ✅ {len(rows)} rows")


# ══════════════════════════════════════════
# Pull all cross indicators
# ══════════════════════════════════════════
def pull_all_cross_indicators():
    pull_sox_index()
    pull_us10y_yield()
    pull_cny_rate()
    pull_gold_price()


if __name__ == "__main__":
    pull_all_cross_indicators()
