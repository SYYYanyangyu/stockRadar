"""美股→A股联动 API — 读取预计算结果，支持概念/个股两种模式"""
import json
from fastapi import APIRouter, Query

from services.storage import get_conn, put_conn

router = APIRouter()

US_INDEX_NAMES = {".INX": "标普500", ".IXIC": "纳斯达克", ".DJI": "道琼斯"}


def _date() -> str:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT MAX(calc_date) FROM us_concept_correlation")
        row = cur.fetchone()
        return str(row[0]) if row and row[0] else ""
    finally:
        put_conn(conn)


def _index_snapshots(d: str):
    """美股指数快照（概念和个股模式共用）"""
    conn = get_conn()
    try:
        cur = conn.cursor()
        indices = []
        for symbol in [".INX", ".IXIC", ".DJI"]:
            cur.execute("""
                SELECT close, change_pct FROM us_indices
                WHERE symbol = %s AND trade_date <= %s
                ORDER BY trade_date DESC LIMIT 1
            """, (symbol, d))
            latest = cur.fetchone()

            cur.execute("""
                SELECT close FROM us_indices
                WHERE symbol = %s AND trade_date <= %s
                ORDER BY trade_date DESC LIMIT 5
            """, (symbol, d))
            recents = [float(r[0]) for r in cur.fetchall() if r[0] is not None]
            recent_norm = None
            if recents and len(recents) >= 2:
                base = recents[-1]
                recent_norm = [round(v / base, 4) for v in recents] if base > 0 else None

            indices.append({
                "symbol": symbol,
                "name": US_INDEX_NAMES.get(symbol, symbol),
                "close": round(float(latest[0]), 2) if latest and latest[0] else None,
                "change_pct": round(float(latest[1]), 2) if latest and latest[1] else None,
                "recent_5d": recent_norm or [],
            })
        return indices
    finally:
        put_conn(conn)


@router.get("/us-correlation")
async def us_correlation(
    us_index: str = Query("all", description="美股指数代码，all=全部"),
    top: int = Query(20, ge=1, le=50),
    mode: str = Query("concept", description="concept=概念卡片 | stock=个股列表"),
    period: str = Query("10d", description="相关系数周期：10d/15d/20d"),
):
    d = _date()
    if not d:
        return {"indices": [], "concepts": [], "stocks": [], "date": None, "mode": mode}

    corr_col = f"corr_{period}"
    score_col = f"composite_score_{period}"

    conn = get_conn()
    try:
        cur = conn.cursor()
        indices = _index_snapshots(d)

        if mode == "concept":
            cur.execute("SELECT MAX(calc_date) FROM us_concept_correlation")
            cd = cur.fetchone()
            if not cd or not cd[0]:
                return {"indices": indices, "concepts": [], "date": d, "mode": "concept"}

            if us_index == "all":
                cur.execute(f"""
                    SELECT concept_name, icon, us_index, stock_count, total_constituents,
                           {corr_col}_avg, {corr_col}_std, consistency_{period},
                           {score_col}, avg_beta, top_stocks
                    FROM us_concept_correlation
                    WHERE calc_date = %s
                    ORDER BY {score_col} DESC
                """, (d,))
            else:
                cur.execute(f"""
                    SELECT concept_name, icon, us_index, stock_count, total_constituents,
                           {corr_col}_avg, {corr_col}_std, consistency_{period},
                           {score_col}, avg_beta, top_stocks
                    FROM us_concept_correlation
                    WHERE calc_date = %s AND us_index = %s
                    ORDER BY {score_col} DESC
                """, (d, us_index))

            concepts = []
            for r in cur.fetchall():
                ts = r[10]
                if isinstance(ts, str):
                    ts = json.loads(ts)
                concepts.append({
                    "name": r[0],
                    "icon": r[1],
                    "us_index": r[2],
                    "stock_count": r[3],
                    "total_constituents": r[4],
                    "avg_corr": round(float(r[5]), 4) if r[5] else None,
                    "std_corr": round(float(r[6]), 4) if r[6] else None,
                    "consistency": round(float(r[7]), 4) if r[7] else None,
                    "composite_score": round(float(r[8]), 4) if r[8] else None,
                    "avg_beta": round(float(r[9]), 2) if r[9] else None,
                    "top_stocks": ts or [],
                })

            return {"indices": indices, "concepts": concepts, "stocks": [], "date": d, "mode": "concept"}

        else:
            # mode=stock (legacy)
            stocks = []
            symbols = [".IXIC", ".INX", ".DJI"] if us_index == "all" else [us_index]
            for symbol in symbols:
                cur.execute(f"""
                    SELECT stock_code, stock_name, us_index,
                           corr_10d, corr_15d, corr_20d,
                           beta, overnight_gap, a_stock_change, us_change
                    FROM us_correlation_result
                    WHERE calc_date = %s AND us_index = %s
                    ORDER BY {corr_col} DESC NULLS LAST
                    LIMIT %s
                """, (d, symbol, top))
                for r in cur.fetchall():
                    stocks.append({
                        "code": r[0],
                        "name": r[1],
                        "us_index": r[2],
                        "corr_10d": round(float(r[3]), 4) if r[3] is not None else None,
                        "corr_15d": round(float(r[4]), 4) if r[4] is not None else None,
                        "corr_20d": round(float(r[5]), 4) if r[5] is not None else None,
                        "beta": round(float(r[6]), 2) if r[6] is not None else None,
                        "overnight_gap": round(float(r[7]), 2) if r[7] is not None else None,
                        "a_stock_change": round(float(r[8]), 2) if r[8] is not None else None,
                        "us_change": round(float(r[9]), 2) if r[9] is not None else None,
                    })

            return {"indices": indices, "concepts": [], "stocks": stocks, "date": d, "mode": "stock"}

    finally:
        put_conn(conn)
