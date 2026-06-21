"""两融数据 Router — 读本地 PostgreSQL"""
from fastapi import APIRouter, Query
from services.storage import query_page, latest_trade_date, get_conn, put_conn
from psycopg2.extras import RealDictCursor

router = APIRouter()


def _date() -> str:
    return latest_trade_date("margin_trading") or ""


@router.get("/today")
async def margin_today(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    return query_page("margin_trading", page=page, page_size=page_size, trade_date=_date(), order_by="margin_balance DESC")


@router.get("/summary")
async def margin_summary():
    d = _date()
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    COUNT(*) as stock_count,
                    SUM(margin_buy) as total_margin_buy,
                    SUM(margin_balance) as total_margin_balance,
                    SUM(total_balance) as total_balance
                FROM margin_trading WHERE trade_date = %s
            """, (d,))
            row = cur.fetchone()
            if row and row["stock_count"]:
                return dict(row)
            return {"stock_count": 0, "total_margin_buy": 0, "total_margin_balance": 0, "total_balance": 0}
    finally:
        put_conn(conn)


@router.get("/history")
async def margin_history(days: int = Query(120, ge=30, le=730)):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT trade_date, total_margin_balance, total_margin_buy, total_balance
                FROM margin_daily
                ORDER BY trade_date DESC
                LIMIT %s
            """, (days,))
            margin_rows = {r["trade_date"].isoformat(): r for r in cur.fetchall()}

            cur.execute("""
                SELECT trade_date, SUM(volume) as total_volume, SUM(amount) as total_amount
                FROM stock_hist
                WHERE trade_date >= (SELECT MIN(trade_date) FROM (SELECT trade_date FROM margin_daily ORDER BY trade_date DESC LIMIT %s) t)
                GROUP BY trade_date
                ORDER BY trade_date DESC
            """, (days,))
            volume_rows = {r["trade_date"].isoformat(): r for r in cur.fetchall()}

        all_dates = sorted(set(margin_rows.keys()) | set(volume_rows.keys()))
        data = []
        for d in all_dates:
            m = margin_rows.get(d, {})
            v = volume_rows.get(d, {})
            data.append({
                "trade_date": d,
                "margin_balance": float(m.get("total_margin_balance") or 0),
                "margin_buy": float(m.get("total_margin_buy") or 0),
                "total_volume": float(v.get("total_volume") or 0),
                "total_amount": float(v.get("total_amount") or 0),
            })
        return data
    finally:
        put_conn(conn)


# ─── 两融深度分析 ───

@router.get("/trend/{code}")
async def margin_trend(code: str, days: int = Query(60, ge=10, le=500)):
    """个股融资余额走势 + 股价对比"""
    d = _date()
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # margin_trading 只有最新一天的数据，查历史仅从 margin_daily 做市场级别
            # 个股融资趋势需要 stock_hist 结合最新融资余额
            cur.execute("""
                SELECT trade_date, margin_balance, margin_buy, short_balance
                FROM margin_trading
                WHERE code = %s AND trade_date = %s
            """, (code, d))
            margin_row = cur.fetchone()
            latest_margin = float(margin_row["margin_balance"] or 0) if margin_row else 0

            # 查stock_hist的近N天价格和量
            cur.execute("""
                WITH normalized AS (
                    SELECT
                        REPLACE(REPLACE(REPLACE(sh.code, 'sh.', 'sh'), 'sz.', 'sz'), 'bj.', 'bj') as code,
                        sh.trade_date, sh.close, sh.change_pct, sh.volume, sh.amount
                    FROM stock_hist sh
                )
                SELECT trade_date, close, change_pct, volume, amount
                FROM normalized
                WHERE code = %s
                ORDER BY trade_date DESC
                LIMIT %s
            """, (code, days))
            rows = cur.fetchall()
            rows.reverse()

            results = []
            for r in rows:
                results.append({
                    "trade_date": r["trade_date"].isoformat() if hasattr(r["trade_date"], "isoformat") else str(r["trade_date"]),
                    "margin_balance": latest_margin,
                    "margin_buy": 0,
                    "short_balance": 0,
                    "stock_price": float(r["close"] or 0),
                    "change_pct": float(r["change_pct"] or 0),
                })
            return results
    finally:
        put_conn(conn)


@router.get("/top-changes")
async def margin_top_changes(
    period: str = Query("weekly", regex="^(daily|weekly|monthly)$"),
    direction: str = Query("increase", regex="^(increase|decrease)$"),
    limit: int = Query(10, ge=5, le=100),
):
    """融资余额变动排行 — 当前仅有一日数据，后续收集多日后再做差分"""
    d = _date()
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if direction == "increase":
                order = "margin_balance DESC NULLS LAST"
            else:
                order = "margin_balance ASC NULLS LAST"
            cur.execute(f"""
                SELECT mt.code, mt.name, mt.margin_balance, mt.margin_buy,
                       mt.total_balance, mt.margin_balance as balance_change,
                       sh.change_pct
                FROM margin_trading mt
                LEFT JOIN LATERAL (
                    SELECT change_pct FROM stock_hist sh
                    WHERE sh.code = mt.code AND sh.trade_date = mt.trade_date
                    LIMIT 1
                ) sh ON true
                WHERE mt.trade_date = %s
                  AND mt.margin_balance > 0
                ORDER BY mt.margin_balance DESC
                LIMIT %s
            """, (d, limit))
            rows = cur.fetchall()
            return [{
                "code": r["code"],
                "name": r["name"] or "",
                "margin_balance": float(r["margin_balance"] or 0),
                "margin_buy": float(r["margin_buy"] or 0),
                "total_balance": float(r["total_balance"] or 0),
                "balance_change": float(r["balance_change"] or 0),
                "change_pct": float(r["change_pct"]) if r.get("change_pct") is not None else None,
            } for r in rows]
    finally:
        put_conn(conn)


@router.get("/sector-summary")
async def margin_sector_summary():
    """按板块汇总融资余额"""
    conn = get_conn()
    d = _date()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT ss.sector_code, SUM(mt.margin_balance) as total_margin,
                       COUNT(DISTINCT mt.code) as stock_count
                FROM margin_trading mt
                JOIN sector_stocks ss ON mt.code = ss.code
                WHERE mt.trade_date = %s
                GROUP BY ss.sector_code
                HAVING SUM(mt.margin_balance) > 0
                ORDER BY SUM(mt.margin_balance) DESC
                LIMIT 30
            """, (d,))
            rows = cur.fetchall()
            return [{
                "sector_code": r["sector_code"] or "未知",
                "total_margin": float(r["total_margin"] or 0),
                "stock_count": r["stock_count"] or 0,
            } for r in rows]
    finally:
        put_conn(conn)
