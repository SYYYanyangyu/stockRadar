"""龙虎榜 / 资金异动 Router — 读本地 PostgreSQL"""
from fastapi import APIRouter, Query
from typing import Optional
from services.storage import query_all, query_page, latest_trade_date

router = APIRouter()


def _date() -> str:
    return latest_trade_date("dragon_tiger") or ""


@router.get("/today")
async def dragon_tiger_today(
    date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    d = date or _date()
    return query_page("dragon_tiger", page=page, page_size=page_size, trade_date=d, order_by="net_buy DESC")


@router.get("/seats/{code}")
async def dragon_tiger_seats(code: str):
    d = _date()
    return query_all("dragon_tiger_seats", trade_date=d, code=code)


@router.get("/grouped-by-trader")
async def dragon_tiger_grouped_by_trader(
    days: int = Query(5, ge=1, le=30),
):
    """按游资席位聚合 — 近N天数据，排名靠前的活跃游资"""
    from services.storage import get_conn, put_conn
    from psycopg2.extras import RealDictCursor
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    trader_name,
                    COUNT(*) as total_trades,
                    COUNT(DISTINCT code) as stock_count,
                    COUNT(DISTINCT trade_date) as active_days,
                    SUM(buy_amount) as total_buy,
                    SUM(sell_amount) as total_sell,
                    SUM(buy_amount) - SUM(sell_amount) as net,
                    SUM(CASE WHEN trader_type = 'buy' THEN 1 ELSE 0 END) as buy_times,
                    SUM(CASE WHEN trader_type = 'sell' THEN 1 ELSE 0 END) as sell_times,
                    ARRAY_AGG(DISTINCT code ORDER BY code) as codes
                FROM dragon_tiger_seats
                WHERE trade_date >= CURRENT_DATE - %s
                  AND trader_name IS NOT NULL AND trader_name != ''
                GROUP BY trader_name
                HAVING COUNT(DISTINCT trade_date) >= 1
                ORDER BY COUNT(*) DESC
                LIMIT 30
            """, (days,))
            rows = cur.fetchall()

            if not rows:
                return []

            # 收集所有code批量查名称
            all_codes = []
            for r in rows:
                all_codes.extend(r["codes"] or [])
            code_name_map = {}
            if all_codes:
                # 查最近日期每个code的名称
                cur.execute("""
                    SELECT DISTINCT ON (code) code, name
                    FROM dragon_tiger
                    WHERE code = ANY(%s)
                    ORDER BY code, trade_date DESC
                """, (all_codes,))
                for row in cur.fetchall():
                    code_name_map[row["code"]] = row["name"]

            # 对每个游资，统计各操作股票的次日涨跌幅(预估跟庄胜率)
            trader_stock_stats = {}
            for r in rows:
                name = r["trader_name"]
                # 取该游资的买入操作，查次日涨跌幅
                cur.execute("""
                    SELECT ds.code, ds.trade_date, ds.buy_amount, ds.sell_amount,
                           LEAD(sh.change_pct) OVER (PARTITION BY ds.code ORDER BY sh.trade_date) as next_day_chg
                    FROM dragon_tiger_seats ds
                    LEFT JOIN stock_hist sh
                      ON ds.code = sh.code AND sh.trade_date > ds.trade_date
                    WHERE ds.trader_name = %s AND ds.trade_date >= CURRENT_DATE - %s
                    ORDER BY ds.code, ds.trade_date
                """, (name, days))
                buy_results = cur.fetchall()
                wins = 0
                total_with_next = 0
                for br in buy_results:
                    if br["buy_amount"] and float(br["buy_amount"] or 0) > 0 and br["next_day_chg"] is not None:
                        total_with_next += 1
                        if float(br["next_day_chg"] or 0) > 0:
                            wins += 1
                trader_stock_stats[name] = {
                    "win_rate": round(wins / total_with_next, 2) if total_with_next > 0 else 0,
                    "followed_count": total_with_next,
                }

            return [{
                "group_name": r["trader_name"],
                "stock_count": r["stock_count"],
                "total_trades": r["total_trades"],
                "active_days": r["active_days"],
                "total_buy": float(r["total_buy"] or 0),
                "total_sell": float(r["total_sell"] or 0),
                "net": float(r["net"] or 0),
                "buy_times": r["buy_times"],
                "sell_times": r["sell_times"],
                "buy_ratio": round(r["buy_times"] / max(r["total_trades"], 1), 2),
                "win_rate": trader_stock_stats.get(r["trader_name"], {}).get("win_rate", 0),
                "codes": r["codes"] or [],
                "stocks": [{"code": c, "name": code_name_map.get(c, c)} for c in (r["codes"] or [])],
            } for r in rows]
    finally:
        put_conn(conn)


@router.get("/grouped-by-concept")
async def dragon_tiger_grouped_by_concept():
    """按行业聚合龙虎榜 — 涨停板+龙虎榜共振票，带涨跌幅+游资买入统计"""
    from services.storage import get_conn, put_conn
    from psycopg2.extras import RealDictCursor
    d = _date()
    zt_date = latest_trade_date("zt_pool") or d
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 取所有涨停+龙虎榜共振的股票，带行业和涨跌幅
            cur.execute("""
                SELECT d.code, d.name, d.change_pct, d.reason,
                       d.net_buy as dt_net,
                       z.industry, z.streak
                FROM dragon_tiger d
                JOIN zt_pool z ON d.code = z.code AND z.trade_date = %s
                WHERE d.trade_date = %s
                  AND z.industry IS NOT NULL AND z.industry != ''
                ORDER BY z.industry, d.code
            """, (zt_date, d))
            rows = cur.fetchall()

            if not rows:
                return []

            # 查各行业的游资席位净买入总额
            code_list = [r["code"] for r in rows]
            cur.execute("""
                SELECT ds.code, SUM(COALESCE(ds.buy_amount, 0)) as seat_buy,
                       SUM(COALESCE(ds.sell_amount, 0)) as seat_sell,
                       STRING_AGG(DISTINCT ds.trader_name, ', ') FILTER (WHERE ds.trader_name IS NOT NULL AND ds.trader_name != '') as traders
                FROM dragon_tiger_seats ds
                WHERE ds.code = ANY(%s) AND ds.trade_date = %s
                GROUP BY ds.code
            """, (code_list, d))
            seat_map = {}
            for sr in cur.fetchall():
                seat_map[sr["code"]] = {
                    "seat_net": float(sr["seat_buy"] or 0) - float(sr["seat_sell"] or 0),
                    "seat_buy": float(sr["seat_buy"] or 0),
                    "traders": sr["traders"] or "",
                }

            # 按行业分组
            industries = {}
            for r in rows:
                ind = r["industry"]
                if ind not in industries:
                    industries[ind] = {"codes": [], "stocks": []}
                seat_info = seat_map.get(r["code"], {"seat_net": 0, "seat_buy": 0, "traders": ""})
                industries[ind]["codes"].append(r["code"])
                industries[ind]["stocks"].append({
                    "code": r["code"],
                    "name": r["name"] or "",
                    "change_pct": float(r["change_pct"] or 0),
                    "streak": r["streak"] or 0,
                    "reason": r["reason"] or "",
                    "dt_net": float(r["dt_net"] or 0),
                    "seat_net": seat_info["seat_net"],
                    "traders": seat_info["traders"],
                })

            result = []
            for ind, data in industries.items():
                stocks = data["stocks"]
                avg_chg = sum(s["change_pct"] for s in stocks) / len(stocks)
                total_seat_net = sum(s["seat_net"] for s in stocks)
                max_streak = max(s["streak"] for s in stocks)

                # 龙头股：涨停板数最多
                sorted_by_streak = sorted(stocks, key=lambda s: (-s["streak"], -abs(s["change_pct"])))
                leader = sorted_by_streak[0] if sorted_by_streak else None

                result.append({
                    "concept": ind,
                    "stock_count": len(stocks),
                    "codes": data["codes"],
                    "stocks": stocks,
                    "avg_change_pct": round(avg_chg, 1),
                    "total_seat_net": round(total_seat_net, 2),
                    "max_streak": max_streak,
                    "leader": leader,
                })

            result.sort(key=lambda x: (-x["stock_count"], -abs(x["avg_change_pct"])))
            return result
    finally:
        put_conn(conn)


@router.get("/fund-flow")
async def fund_flow(
    limit: int = Query(30, ge=1, le=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    d = latest_trade_date("fund_flow") or ""
    return query_page("fund_flow", page=page, page_size=page_size, trade_date=d, order_by="main_net DESC")


@router.get("/north-bound")
async def north_bound():
    rows = query_all("north_bound", order_by="trade_date DESC", limit=1)
    if rows:
        return rows[0]
    return {}


# ─── 游资网络 ───

@router.get("/trader/{name}")
async def trader_detail(name: str):
    """席位游资详情：历史交易 + 统计 + 协同游资"""
    from services.storage import get_conn, put_conn
    from psycopg2.extras import RealDictCursor
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1. Trader history — all trades
            cur.execute("""
                SELECT ds.trade_date, ds.code, dt.name,
                       ds.buy_amount, ds.sell_amount,
                       (COALESCE(ds.buy_amount, 0) - COALESCE(ds.sell_amount, 0)) as net,
                       dt.change_pct as stock_change_pct
                FROM dragon_tiger_seats ds
                LEFT JOIN dragon_tiger dt ON ds.code = dt.code AND ds.trade_date = dt.trade_date
                WHERE ds.trader_name = %s
                ORDER BY ds.trade_date DESC
                LIMIT 50
            """, (name,))
            history_rows = cur.fetchall()

            if not history_rows:
                return {"trader_name": name, "total_appearances": 0, "total_buy": 0,
                        "total_sell": 0, "net": 0, "avg_net_per_trade": 0,
                        "win_rate_est": 0, "favorite_sectors": [], "co_traders": [], "history": []}

            total_buy = sum(float((r["buy_amount"] or 0)) for r in history_rows)
            total_sell = sum(float((r["sell_amount"] or 0)) for r in history_rows)
            total_appearances = len(history_rows)
            net = total_buy - total_sell
            avg_net = net / total_appearances if total_appearances > 0 else 0

            win_count = sum(1 for r in history_rows if (r["stock_change_pct"] or 0) > 0)
            win_rate = win_count / total_appearances if total_appearances > 0 else 0

            # 2. Favorite sectors — via zt_pool industry
            codes = list(set(r["code"] for r in history_rows))
            cur.execute("""
                SELECT z.industry, COUNT(*) as cnt
                FROM zt_pool z
                WHERE z.code = ANY(%s) AND z.industry IS NOT NULL AND z.industry != ''
                GROUP BY z.industry
                ORDER BY cnt DESC
                LIMIT 5
            """, (codes,))
            sectors = [r["industry"] for r in cur.fetchall()]

            # 3. Co-traders — other traders who appeared with this one on same stock+date
            cur.execute("""
                SELECT ds2.trader_name as name, COUNT(*) as co_count
                FROM dragon_tiger_seats ds1
                JOIN dragon_tiger_seats ds2
                  ON ds1.code = ds2.code AND ds1.trade_date = ds2.trade_date
                WHERE ds1.trader_name = %s
                  AND ds2.trader_name != %s
                  AND ds2.trader_name IS NOT NULL AND ds2.trader_name != ''
                GROUP BY ds2.trader_name
                ORDER BY co_count DESC
                LIMIT 10
            """, (name, name))
            co_traders = [{"name": r["name"], "co_count": r["co_count"]} for r in cur.fetchall()]

            return {
                "trader_name": name,
                "total_appearances": total_appearances,
                "total_buy": round(total_buy, 2),
                "total_sell": round(total_sell, 2),
                "net": round(net, 2),
                "avg_net_per_trade": round(avg_net, 2),
                "win_rate_est": round(win_rate, 2),
                "favorite_sectors": sectors,
                "co_traders": co_traders,
                "history": [{
                    "trade_date": r["trade_date"].isoformat() if hasattr(r["trade_date"], "isoformat") else str(r["trade_date"]),
                    "code": r["code"],
                    "name": r["name"] or "",
                    "buy_amount": float(r["buy_amount"] or 0),
                    "sell_amount": float(r["sell_amount"] or 0),
                    "net": float(r["net"] or 0),
                    "stock_change_pct": float(r["stock_change_pct"] or 0),
                    "post_3d_change": None,
                } for r in history_rows],
            }
    finally:
        put_conn(conn)


@router.get("/co-occurrence")
async def trader_co_occurrence(days: int = Query(30, ge=7, le=365)):
    """游资协同出现分析：过去N天内共同上榜的游资对"""
    from services.storage import get_conn, put_conn
    from psycopg2.extras import RealDictCursor
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    LEAST(ds1.trader_name, ds2.trader_name) as trader_a,
                    GREATEST(ds1.trader_name, ds2.trader_name) as trader_b,
                    COUNT(*) as co_count,
                    SUM(COALESCE(ds1.buy_amount, 0)) as total_buy_a,
                    SUM(COALESCE(ds2.buy_amount, 0)) as total_buy_b
                FROM dragon_tiger_seats ds1
                JOIN dragon_tiger_seats ds2
                  ON ds1.code = ds2.code AND ds1.trade_date = ds2.trade_date
                WHERE ds1.trader_name < ds2.trader_name
                  AND ds1.trader_name IS NOT NULL AND ds1.trader_name != ''
                  AND ds2.trader_name IS NOT NULL AND ds2.trader_name != ''
                  AND ds1.trade_date >= CURRENT_DATE - %s
                GROUP BY LEAST(ds1.trader_name, ds2.trader_name),
                         GREATEST(ds1.trader_name, ds2.trader_name)
                HAVING COUNT(*) >= 2
                ORDER BY co_count DESC
                LIMIT 30
            """, (days,))
            rows = cur.fetchall()
            return [{
                "trader_a": r["trader_a"],
                "trader_b": r["trader_b"],
                "co_count": r["co_count"],
                "total_buy_a": float(r["total_buy_a"] or 0),
                "total_buy_b": float(r["total_buy_b"] or 0),
            } for r in rows]
    finally:
        put_conn(conn)
