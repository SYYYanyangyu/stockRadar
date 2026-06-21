"""板块概念轮动 Router — 读本地 PostgreSQL"""
from fastapi import APIRouter, Query
from services.storage import query_all, query_page, latest_trade_date, get_conn, put_conn
from psycopg2.extras import RealDictCursor

router = APIRouter()


def _date() -> str:
    return latest_trade_date("sector_rank") or ""


def _compute_up_down(rows: list[dict]) -> list[dict]:
    """从 sector_stocks 成分股数据计算真实涨跌家数和领涨股"""
    if not rows:
        return rows
    d = rows[0].get("trade_date") or _date()

    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 同时用 sector_code 和 name 列匹配，sector_rank.name 可能与 sector_stocks.sector_code 不完全一致
            sector_names = [r["name"] for r in rows]
            sector_codes = [r.get("code", "") for r in rows if r.get("code")]

            # 先用 name 匹配
            cur.execute("""
                SELECT
                    sector_code,
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE change_pct > 0) as up_n,
                    COUNT(*) FILTER (WHERE change_pct < 0) as down_n,
                    MAX(change_pct) as max_change
                FROM sector_stocks
                WHERE trade_date = %s AND sector_code = ANY(%s)
                GROUP BY sector_code
            """, (d, sector_names))
            stats = {r["sector_code"]: r for r in cur.fetchall()}

            cur.execute("""
                SELECT DISTINCT ON (sector_code) sector_code, name, change_pct
                FROM sector_stocks
                WHERE trade_date = %s AND sector_code = ANY(%s)
                ORDER BY sector_code, change_pct DESC NULLS LAST
            """, (d, sector_names))
            top_names = {r["sector_code"]: r["name"] for r in cur.fetchall()}

            for row in rows:
                name = row.get("name", "")
                code = row.get("code", "")
                st = stats.get(name)
                tn = top_names.get(name)
                # 如果按 name 没匹配到，尝试用 sector_rank.code 匹配 sector_stocks.sector_code
                if not st and code:
                    st = stats.get(code)
                    tn = top_names.get(code)
                if st:
                    row["up_count"] = st["up_n"] or 0
                    row["down_count"] = st["down_n"] or 0
                    if tn:
                        row["top_stock"] = tn
                        row["top_change_pct"] = round(float(st["max_change"] or 0), 2)
                else:
                    row["up_count"] = 0
                    row["down_count"] = 0
    finally:
        put_conn(conn)
    return rows


@router.get("/rank")
async def sector_rank(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    result = query_page("sector_rank", page=page, page_size=page_size, trade_date=_date(), order_by="change_pct DESC")
    result["items"] = _compute_up_down(result["items"])
    return result


@router.get("/{sector_code}/stocks")
async def sector_stocks(
    sector_code: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
):
    """sector_code 可以是 sector_rank.code（如'002297'）或 sector_rank.name（如'金属制品业'）"""
    result = query_page("sector_stocks", page=page, page_size=page_size, trade_date=_date(), sector_code=sector_code, order_by="change_pct DESC")
    if not result["items"]:
        from services.storage import get_conn, put_conn
        from psycopg2.extras import RealDictCursor
        conn = get_conn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT name FROM sector_rank WHERE code=%s AND trade_date=%s LIMIT 1", (sector_code, _date()))
                row = cur.fetchone()
                if row:
                    result = query_page("sector_stocks", page=page, page_size=page_size, trade_date=_date(), sector_code=row["name"], order_by="change_pct DESC")
        finally:
            put_conn(conn)
    return result
