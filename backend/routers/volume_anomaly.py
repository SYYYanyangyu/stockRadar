"""成交量异动监控 — 量比异常但未涨停的股票"""
from fastapi import APIRouter, Query
from services.storage import get_conn, put_conn, latest_trade_date
from psycopg2.extras import RealDictCursor

router = APIRouter()


def strip_prefix(code: str) -> str:
    for p in ("sh", "sz", "bj"):
        if code.startswith(p):
            return code[len(p):]
    return code


@router.get("")
async def volume_anomaly(
    days: int = Query(5, ge=1, le=30),
    base_days: int = Query(50, ge=20, le=250),
    min_ratio: float = Query(2.0, ge=1.0, le=20.0),
    exclude_zt: bool = Query(True),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    d = latest_trade_date("stock_hist")
    if not d:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}

    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            zt_clause = ""
            if exclude_zt:
                zt_clause = """
                    AND REPLACE(REPLACE(REPLACE(r.code, 'sh', ''), 'sz', ''), 'bj', '')
                    NOT IN (SELECT code FROM zt_pool WHERE trade_date = %(d)s)
                """

            # HAVING thresholds: relaxed so 10-day windows work
            short_min = max(2, int(days * 0.4))
            base_min = max(10, int(base_days * 0.3))

            count_sql = f"""
                WITH max_dt AS (SELECT MAX(trade_date) as dt FROM stock_hist),
                normalized AS (
                    SELECT
                        REPLACE(REPLACE(REPLACE(sh.code, 'sh.', 'sh'), 'sz.', 'sz'), 'bj.', 'bj') as code,
                        sh.trade_date, sh.close, sh.volume, sh.amount, sh.change_pct
                    FROM stock_hist sh
                    WHERE sh.volume IS NOT NULL AND sh.volume > 0
                ),
                recent_vol AS (
                    SELECT n.code, AVG(n.volume) as avg_vol_short
                    FROM normalized n, max_dt m
                    WHERE n.trade_date >= m.dt - {days}
                    GROUP BY n.code
                    HAVING COUNT(*) >= {short_min}
                ),
                base_vol AS (
                    SELECT n.code, AVG(n.volume) as avg_vol_base
                    FROM normalized n, max_dt m
                    WHERE n.trade_date >= m.dt - {base_days}
                    GROUP BY n.code
                    HAVING COUNT(*) >= {base_min}
                ),
                latest AS (
                    SELECT DISTINCT ON (n.code) n.code, n.trade_date as latest_trade_date,
                        n.close as price, n.change_pct, n.volume as latest_volume, n.amount
                    FROM normalized n
                    ORDER BY n.code, n.trade_date DESC
                ),
                name_lookup AS (
                    SELECT REPLACE(REPLACE(REPLACE(g.code, 'sh', ''), 'sz', ''), 'bj', '') as code,
                           MAX(g.name) as name FROM gainers g
                    WHERE g.trade_date = %(d)s
                    GROUP BY 1
                )
                SELECT COUNT(*) as cnt
                FROM recent_vol r
                JOIN base_vol b ON r.code = b.code AND b.avg_vol_base > 0
                LEFT JOIN latest l ON r.code = l.code
                LEFT JOIN name_lookup nl ON
                    REPLACE(REPLACE(REPLACE(r.code, 'sh', ''), 'sz', ''), 'bj', '') = nl.code
                WHERE r.avg_vol_short / b.avg_vol_base >= %(min_ratio)s
                {zt_clause}
            """

            params = {"d": d, "min_ratio": min_ratio}
            cur.execute(count_sql, params)
            total = cur.fetchone()["cnt"]

            data_sql = f"""
                WITH max_dt AS (SELECT MAX(trade_date) as dt FROM stock_hist),
                normalized AS (
                    SELECT
                        REPLACE(REPLACE(REPLACE(sh.code, 'sh.', 'sh'), 'sz.', 'sz'), 'bj.', 'bj') as code,
                        sh.trade_date, sh.close, sh.volume, sh.amount, sh.change_pct
                    FROM stock_hist sh
                    WHERE sh.volume IS NOT NULL AND sh.volume > 0
                ),
                recent_vol AS (
                    SELECT n.code, AVG(n.volume) as avg_vol_short
                    FROM normalized n, max_dt m
                    WHERE n.trade_date >= m.dt - {days}
                    GROUP BY n.code
                    HAVING COUNT(*) >= {short_min}
                ),
                base_vol AS (
                    SELECT n.code, AVG(n.volume) as avg_vol_base
                    FROM normalized n, max_dt m
                    WHERE n.trade_date >= m.dt - {base_days}
                    GROUP BY n.code
                    HAVING COUNT(*) >= {base_min}
                ),
                latest AS (
                    SELECT DISTINCT ON (n.code) n.code, n.trade_date as latest_trade_date,
                        n.close as price, n.change_pct, n.volume as latest_volume, n.amount
                    FROM normalized n
                    ORDER BY n.code, n.trade_date DESC
                ),
                name_lookup AS (
                    SELECT REPLACE(REPLACE(REPLACE(g.code, 'sh', ''), 'sz', ''), 'bj', '') as code,
                           MAX(g.name) as name FROM gainers g
                    WHERE g.trade_date = %(d)s
                    GROUP BY 1
                )
                SELECT
                    r.code, COALESCE(nl.name, '') as name,
                    l.latest_trade_date,
                    l.price, l.change_pct, l.latest_volume, l.amount,
                    ROUND(r.avg_vol_short::numeric, 0) as avg_vol_short,
                    ROUND(b.avg_vol_base::numeric, 0) as avg_vol_base,
                    ROUND((r.avg_vol_short / NULLIF(b.avg_vol_base, 0))::numeric, 2) as volume_ratio
                FROM recent_vol r
                JOIN base_vol b ON r.code = b.code AND b.avg_vol_base > 0
                LEFT JOIN latest l ON r.code = l.code
                LEFT JOIN name_lookup nl ON
                    REPLACE(REPLACE(REPLACE(r.code, 'sh', ''), 'sz', ''), 'bj', '') = nl.code
                WHERE r.avg_vol_short / b.avg_vol_base >= %(min_ratio)s
                {zt_clause}
                ORDER BY volume_ratio DESC
                LIMIT %(limit)s OFFSET %(offset)s
            """

            params["limit"] = page_size
            params["offset"] = (page - 1) * page_size
            cur.execute(data_sql, params)
            items = [dict(r) for r in cur.fetchall()]

            for item in items:
                for k in ("price", "change_pct", "latest_volume", "amount",
                          "avg_vol_short", "avg_vol_base", "volume_ratio"):
                    if item.get(k) is not None:
                        item[k] = float(item[k])
                code = item.get("code", "")
                item["code"] = strip_prefix(code)

            return {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "data_date": str(d),
            }
    finally:
        put_conn(conn)
