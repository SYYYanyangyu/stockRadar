"""
低调牛股挖掘 — 五大维度十六子维度评分模型

维度（每维 0-20，满分 100）：
1. 趋势 trend       — 偷偷涨：连阳+累计涨幅+月度胜率+MA多头排列
2. 低调 quiet       — 没曝光：热榜避险(0-10) + 避涨跌停(0-10)
3. 量价 volume      — 筹码稳：成交量CV(0-8) + 缩量上涨占比(0-6) + MA20上方占比(0-6)
4. 筹码 capital     — 资金锁：融资规模(0-4) + 日均振幅低(0-8) + 最大回撤小(0-8)
5. 形态 pattern     — 慢涨型：小阳线占比(0-8) + 窄幅震荡占比(0-6) + 连阳天数加成(0-6)
"""
from fastapi import APIRouter, Query
from services.storage import get_conn, put_conn, latest_trade_date
from psycopg2.extras import RealDictCursor
from statistics import mean, stdev

router = APIRouter()


def _strip_prefix(code: str) -> str:
    for p in ("sh", "sz", "bj"):
        if code.startswith(p):
            return code[len(p):]
    return code


def _compute_ma(values, window):
    if len(values) < window:
        return None
    return sum(values[-window:]) / window


# ── 子维度: 趋势 ──

def _compute_streak(rows_sorted_desc):
    """从最新日期往回数连阳天数 & 累计涨幅"""
    streak, total_pct = 0, 0.0
    prev_date = None
    for r in rows_sorted_desc:
        chg = float(r.get("change_pct") or 0)
        if chg > 0:
            if prev_date is not None:
                if (prev_date - r["trade_date"]).days > 4:
                    break
            streak += 1
            total_pct += chg
            prev_date = r["trade_date"]
        else:
            break
    return streak, round(total_pct, 2)


def _score_trend(rows, rows_sorted_desc):
    """趋势维度: 连阳分 + 累计涨幅分 + 月度胜率 + MA多头排列"""
    streak, total_pct = _compute_streak(rows_sorted_desc)

    # 子1: 连阳分 (0-10)
    streak_score = min(streak * 2, 10)

    # 子2: 累计涨幅分 (0-4) — streak期间总涨幅
    pct_score = min(abs(total_pct) / 5, 4)

    # 子3: 月度胜率 (0-4) — 近30天上涨日占比
    recent_30 = rows[-30:] if len(rows) >= 30 else rows
    up_days = sum(1 for r in recent_30 if (r.get("change_pct") or 0) > 0)
    win_rate = up_days / len(recent_30) if recent_30 else 0
    win_score = min(win_rate * 8, 4)

    # 子4: MA多头排列占比 (0-2) — close > MA5 > MA20 的天数
    closes = [float(r["close"]) for r in rows if r.get("close")]
    ma_bull_days = 0
    for i in range(19, len(closes)):
        ma5 = sum(closes[i - 4:i + 1]) / 5
        ma20 = sum(closes[i - 19:i + 1]) / 20
        if closes[i] > ma5 > ma20:
            ma_bull_days += 1
    bull_ratio = ma_bull_days / max(len(closes) - 19, 1)
    bull_score = min(bull_ratio * 5, 2)

    return min(streak_score + pct_score + win_score + bull_score, 20), streak, total_pct


# ── 子维度: 低调 ──

def _score_quiet(heat_count, rows):
    """低调维度: 热榜曝光(0-10) + 避涨跌停(0-10)"""
    # 子1: 热榜曝光 (0-10)
    if heat_count == 0:
        heat_score = 10
    elif heat_count == 1:
        heat_score = 6
    elif heat_count <= 3:
        heat_score = 3
    else:
        heat_score = 0

    # 子2: 避涨跌停 (0-10) — 近90天最大单日涨跌幅，越接近0越好
    recent = rows[-90:] if len(rows) >= 90 else rows
    max_chg = max(abs(float(r.get("change_pct") or 0)) for r in recent)
    # max_chg ≤ 3% → 10分, ≤5% → 8分, ≤7% → 5分, ≤9.5% → 2分, >9.5% → 0分
    if max_chg <= 3:
        avoid_score = 10
    elif max_chg <= 5:
        avoid_score = 8
    elif max_chg <= 7:
        avoid_score = 5
    elif max_chg <= 9.5:
        avoid_score = 2
    else:
        avoid_score = 0

    return heat_score + avoid_score


# ── 子维度: 量价 ──

def _score_volume(rows):
    """量价维度: 成交量稳定性(0-8) + 缩量上涨占比(0-6) + MA20上方占比(0-6)"""
    vols = [float(r["volume"]) for r in rows if r.get("volume") and float(r.get("volume") or 0) > 0]
    if len(vols) < 5:
        return 10

    avg_v = mean(vols)

    # 子1: 成交量稳定性 CV (0-8)
    try:
        cv = stdev(vols) / avg_v
    except (ValueError, ZeroDivisionError):
        cv = 0
    cv_score = 8 * (1 - min(cv / 0.6, 1))

    # 子2: 缩量上涨占比 (0-6) — 近90天: volume < MA20_vol 且 change_pct > 0
    vol_ma20_window = 20
    shrink_up_days = 0
    valid = 0
    for i in range(vol_ma20_window, min(len(vols), len(rows))):
        ma20_v = sum(vols[i - vol_ma20_window:i]) / vol_ma20_window
        chg = float(rows[i].get("change_pct") or 0) if i < len(rows) else 0
        if vols[i] < ma20_v and chg > 0:
            shrink_up_days += 1
        valid += 1
    shrink_ratio = shrink_up_days / max(valid, 1)
    shrink_score = min(shrink_ratio * 15, 6)

    # 子3: 价格在MA20上方占比 (0-6)
    closes = [float(r["close"]) for r in rows if r.get("close")]
    above_ma20 = 0
    for i in range(19, len(closes)):
        ma20 = sum(closes[i - 19:i + 1]) / 20
        if closes[i] > ma20:
            above_ma20 += 1
    above_ratio = above_ma20 / max(len(closes) - 19, 1)
    above_score = min(above_ratio * 8, 6)

    return min(cv_score + shrink_score + above_score, 20)


# ── 子维度: 筹码 ──

def _score_capital(rows, margin_balance):
    """筹码维度: 融资规模(0-4) + 日均振幅极低(0-8) + 最大回撤小(0-8)"""
    recent_60 = rows[-60:] if len(rows) >= 60 else rows

    # 子1: 融资余额规模 (0-4)
    size_score = 0
    if margin_balance and float(margin_balance) > 0:
        bal = float(margin_balance)
        if bal > 50_000_000_000:
            size_score = 4
        elif bal > 10_000_000_000:
            size_score = 3
        elif bal > 1_000_000_000:
            size_score = 2
        elif bal > 100_000_000:
            size_score = 1

    # 子2: 日均振幅极低 (0-8) — 近60天平均振幅 < 2% 满分
    amps = []
    for r in recent_60:
        high = float(r.get("high") or 0)
        low = float(r.get("low") or 0)
        close = float(r.get("close") or 0)
        if high > 0 and low > 0 and close > 0:
            amps.append((high - low) / close)
    avg_amp = mean(amps) if amps else 0.05
    # avg_amp ≤ 1.5% → 8分, ≤2% → 6分, ≤2.5% → 4分, ≤3% → 2分, >3% → 0分
    if avg_amp <= 0.015:
        amp_score = 8
    elif avg_amp <= 0.02:
        amp_score = 6
    elif avg_amp <= 0.025:
        amp_score = 4
    elif avg_amp <= 0.03:
        amp_score = 2
    else:
        amp_score = 0

    # 子3: 近60天最大回撤 (0-8)
    closes = [float(r["close"]) for r in recent_60 if r.get("close")]
    if len(closes) >= 10:
        peak = closes[0]
        max_dd = 0.0
        for c in closes:
            if c > peak:
                peak = c
            dd = (peak - c) / peak
            if dd > max_dd:
                max_dd = dd
        # max_dd ≤ 3% → 8分, ≤5% → 6分, ≤8% → 4分, ≤12% → 2分, >12% → 0分
        if max_dd <= 0.03:
            dd_score = 8
        elif max_dd <= 0.05:
            dd_score = 6
        elif max_dd <= 0.08:
            dd_score = 4
        elif max_dd <= 0.12:
            dd_score = 2
        else:
            dd_score = 0
    else:
        dd_score = 4

    return size_score + amp_score + dd_score


# ── 子维度: 形态 ──

def _score_pattern(rows):
    """形态维度: 小阳线占比(0-8) + 窄幅震荡占比(0-6) + 连阳加成(0-6)"""
    recent_90 = rows[-90:] if len(rows) >= 90 else rows

    # 子1: 小阳线占比 0% < 涨幅 < 3% (0-8)
    small_up = 0
    valid = 0
    for r in recent_90:
        chg = float(r.get("change_pct") or 0)
        if chg > 0 and chg < 3:
            small_up += 1
        valid += 1
    small_up_ratio = small_up / max(valid, 1)
    small_up_score = min(small_up_ratio * 12, 8)

    # 子2: 窄幅震荡占比 振幅<3% (0-6)
    narrow = 0
    amp_valid = 0
    for r in recent_90:
        high = float(r.get("high") or 0)
        low = float(r.get("low") or 0)
        close = float(r.get("close") or 0)
        if high > 0 and low > 0 and close > 0:
            if (high - low) / close < 0.03:
                narrow += 1
            amp_valid += 1
    narrow_ratio = narrow / max(amp_valid, 1)
    narrow_score = min(narrow_ratio * 8, 6)

    # 子3: 连阳天数加成 (0-6)
    desc = sorted(rows, key=lambda r: r["trade_date"], reverse=True)
    streak, _ = _compute_streak(desc)
    streak_bonus = min(streak * 1.2, 6)

    return min(small_up_score + narrow_score + streak_bonus, 20)


# ── 综合评分 ──

def _score_stock(code, rows, heat_count, margin_balance, name):
    if not rows or len(rows) < 5:
        return None

    rows_sorted = sorted(rows, key=lambda r: r["trade_date"])
    rows_desc = sorted(rows, key=lambda r: r["trade_date"], reverse=True)

    trend_score, streak, total_pct = _score_trend(rows_sorted, rows_desc)
    quiet_score = _score_quiet(heat_count, rows_sorted)
    volume_score = _score_volume(rows_sorted)
    capital_score = _score_capital(rows_sorted, margin_balance)
    pattern_score = _score_pattern(rows_sorted)

    latest = rows_sorted[-1]
    total = trend_score + quiet_score + volume_score + capital_score + pattern_score

    return {
        "code": code,
        "name": name or "",
        "price": float(latest.get("close") or 0),
        "change_pct": float(latest.get("change_pct") or 0),
        "total_score": round(total, 0),
        "scores": {
            "trend": round(trend_score, 0),
            "quiet": round(quiet_score, 0),
            "volume": round(volume_score, 0),
            "institution": round(capital_score, 0),
            "pattern": round(pattern_score, 0),
        },
        "streak_days": streak,
        "total_pct": total_pct,
    }


@router.get("")
async def quiet_bulls(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    min_score: int = Query(50, ge=0, le=100),
):
    d = latest_trade_date("stock_hist")
    if not d:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}

    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1. 建立热榜映射
            cur.execute("""
                SELECT code, COUNT(*) as cnt FROM (
                    SELECT code FROM zt_pool
                    UNION ALL
                    SELECT code FROM dragon_tiger
                    UNION ALL
                    SELECT code FROM hot_stocks
                ) t GROUP BY code
            """)
            heat_map = {r["code"]: r["cnt"] for r in cur.fetchall()}

            # 2. 融资余额
            cur.execute("SELECT code, margin_balance FROM margin_trading")
            margin_map = {r["code"]: r["margin_balance"] for r in cur.fetchall()}

            # 3. 股票名称
            cur.execute("SELECT code, name FROM stock_name")
            name_map = {r["code"]: r["name"] for r in cur.fetchall()}

            # 4. 所有股票(含热榜)的近90天K线数据
            cur.execute("""
                WITH normalized AS (
                    SELECT
                        REPLACE(REPLACE(REPLACE(sh.code, 'sh.', 'sh'), 'sz.', 'sz'), 'bj.', 'bj') as code,
                        sh.trade_date, sh.close, sh.volume, sh.high, sh.low,
                        sh.open, sh.change_pct, sh.amount
                    FROM stock_hist sh
                    WHERE sh.volume IS NOT NULL AND sh.volume > 0 AND sh.close > 0
                )
                SELECT * FROM normalized
                ORDER BY code, trade_date ASC
            """)
            all_rows = cur.fetchall()

            # 5. 按股票分组
            stock_rows = {}
            for r in all_rows:
                plain = _strip_prefix(r["code"])
                if plain not in stock_rows:
                    stock_rows[plain] = []
                stock_rows[plain].append(r)

            # 6. 逐只评分
            results = []
            for code, rows in stock_rows.items():
                if len(rows) < 10:
                    continue
                heat_count = heat_map.get(code, 0)
                margin_bal = margin_map.get(code)
                name = name_map.get(code, "")
                result = _score_stock(code, rows, heat_count, margin_bal, name)
                if result is None:
                    continue
                if result["total_score"] >= min_score:
                    results.append(result)

            # 7. 排序分页
            results.sort(key=lambda x: x["total_score"], reverse=True)
            total = len(results)
            start = (page - 1) * page_size
            paged = results[start:start + page_size]

            return {
                "items": paged,
                "total": total,
                "page": page,
                "page_size": page_size,
            }
    finally:
        put_conn(conn)
