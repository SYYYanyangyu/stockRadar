"""基于本地 PostgreSQL 的趋势战法计算引擎 — 离线计算，不依赖东方财富"""
import pandas as pd
import numpy as np
from typing import Optional
from services.storage import get_conn, put_conn, upsert_many


def _ma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = _ema(close, fast)
    ema_slow = _ema(close, slow)
    dif = ema_fast - ema_slow
    dea = _ema(dif, signal)
    macd_hist = 2 * (dif - dea)
    return dif, dea, macd_hist


def compute_signals_from_df(df: pd.DataFrame) -> dict:
    """从 DataFrame 计算趋势信号（DataFrame 需包含 close/high/low/volume/change_pct 列）"""
    if df is None or len(df) < 60:
        return {"score": 0, "signals": [], "error": "数据不足"}

    close = df["close"]
    volume = df["volume"]
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest

    signals = []

    # 1. 均线多头排列
    ma5 = _ma(close, 5).iloc[-1]
    ma10 = _ma(close, 10).iloc[-1]
    ma20 = _ma(close, 20).iloc[-1]
    ma60 = _ma(close, 60).iloc[-1]
    mas = {"ma5": round(ma5, 2), "ma10": round(ma10, 2), "ma20": round(ma20, 2), "ma60": round(ma60, 2)}
    if not any(pd.isna(x) for x in [ma5, ma10, ma20, ma60]):
        if ma5 > ma10 > ma20 > ma60:
            signals.append({"type": "MA_BULL", "label": "均线多头", "weight": 25,
                           "desc": f"MA5({ma5:.2f})>MA10({ma10:.2f})>MA20({ma20:.2f})>MA60({ma60:.2f})"})

    # 2. 突破20日新高
    high_20 = df["high"].tail(20).max()
    if latest["high"] >= high_20 and latest["close"] > prev["close"]:
        signals.append({"type": "BREAK_HIGH", "label": "突破20日新高", "weight": 20,
                       "desc": f"最高{latest['high']:.2f} ≥ 20日高点{high_20:.2f}"})

    # 3. 量价齐升
    avg_vol_5 = _ma(volume, 5).iloc[-1]
    change = float(latest.get("change_pct", 0) or 0)
    if not pd.isna(avg_vol_5) and change > 3 and latest["volume"] > avg_vol_5 * 2:
        signals.append({"type": "VOL_PRICE", "label": "量价齐升", "weight": 20,
                       "desc": f"涨幅{change:.1f}%，量比{(latest['volume']/avg_vol_5):.1f}倍"})

    # 4. MACD
    dif, dea, hist = _macd(close)
    if len(dif) >= 2:
        if dif.iloc[-1] > dea.iloc[-1] and dif.iloc[-2] <= dea.iloc[-2]:
            signals.append({"type": "MACD_CROSS", "label": "MACD金叉", "weight": 15,
                           "desc": f"DIF({dif.iloc[-1]:.3f}) 上穿 DEA({dea.iloc[-1]:.3f})"})
        elif dif.iloc[-1] > dea.iloc[-1] and hist.iloc[-1] > hist.iloc[-2]:
            signals.append({"type": "MACD_BULL", "label": "MACD多头", "weight": 10,
                           "desc": f"MACD柱放大({hist.iloc[-1]:.3f})"})

    # 5. 站上60日线
    if not pd.isna(ma60) and latest["close"] > ma60:
        signals.append({"type": "ABOVE_MA60", "label": "站上60日线", "weight": 10,
                       "desc": f"收盘价{latest['close']:.2f} > MA60({ma60:.2f})"})

    score = sum(s["weight"] for s in signals)
    return {
        "price": float(latest["close"]),
        "change_pct": float(change),
        "score": int(score),
        "signals": signals,
        "ma5": float(ma5) if not pd.isna(ma5) else None,
        "ma10": float(ma10) if not pd.isna(ma10) else None,
        "ma20": float(ma20) if not pd.isna(ma20) else None,
        "ma60": float(ma60) if not pd.isna(ma60) else None,
    }


def scan_all_from_db(trade_date: str, top_n: int = 30, min_score: int = 20) -> list[dict]:
    """从本地 stock_hist 表扫描所有股票的趋势信号（只要有历史数据的都算）"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # 找出 stock_hist 里有最新交易日数据的股票
            cur.execute("""
                SELECT DISTINCT code FROM stock_hist
                WHERE trade_date <= %s
                ORDER BY code
            """, (trade_date,))
            codes = [r[0] for r in cur.fetchall()]
    finally:
        put_conn(conn)

    results = []
    for code in codes:
        df = _load_stock_hist(code, trade_date)
        if df is None:
            continue
        sig = compute_signals_from_df(df)
        if sig["score"] >= min_score:
            sig["code"] = code
            sig["name"] = _lookup_name(code)
            sig["trade_date"] = trade_date
            results.append(sig)

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_n]


def _load_stock_hist(code: str, end_date: str, days: int = 200) -> Optional[pd.DataFrame]:
    """从 stock_hist 表加载单只股票历史K线"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT trade_date, open, close, high, low, volume, amount, change_pct
                FROM stock_hist
                WHERE code = %s AND trade_date <= %s
                ORDER BY trade_date ASC
            """, (code, end_date))
            rows = cur.fetchall()
    finally:
        put_conn(conn)

    if not rows or len(rows) < 60:
        return None

    df = pd.DataFrame(rows, columns=["trade_date", "open", "close", "high", "low", "volume", "amount", "change_pct"])
    df = df.tail(days)
    return df


# 简单缓存
_name_cache: dict[str, str] = {}

def _lookup_name(code: str) -> str:
    if code in _name_cache:
        return _name_cache[code]
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # baostock code "sh.600519" -> strip prefix for lookup
            short = code.replace("sh.","").replace("sz.","")
            cur.execute("SELECT name FROM stock_name WHERE code = %s LIMIT 1", (short,))
            r = cur.fetchone()
    finally:
        put_conn(conn)
    name = r[0] if r else ""
    _name_cache[code] = name
    return name


def save_trend_signals(trade_date: str, signals: list[dict]):
    """保存趋势信号到 trend_signals 表"""
    from services.storage import delete_date
    if not signals:
        return
    import json
    wanted = ["trade_date","code","name","price","change_pct","score","signals","ma5","ma10","ma20","ma60"]
    rows = []
    for s in signals:
        r = {
            "trade_date": trade_date,
            "code": s.get("code", ""),
            "name": s.get("name", ""),
            "price": float(s.get("price", 0) or 0),
            "change_pct": float(s.get("change_pct", 0) or 0),
            "score": int(s.get("score", 0)),
            "signals": json.dumps(s.get("signals", []), ensure_ascii=False),
            "ma5": float(s.get("ma5", 0) or 0),
            "ma10": float(s.get("ma10", 0) or 0),
            "ma20": float(s.get("ma20", 0) or 0),
            "ma60": float(s.get("ma60", 0) or 0),
        }
        rows.append(r)
    delete_date("trend_signals", trade_date)
    upsert_many("trend_signals", rows)
