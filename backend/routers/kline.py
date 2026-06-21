"""个股K线图 Router — 读 stock_hist 表，带 baostock 实时回退"""
from fastapi import APIRouter, Query
from services.storage import get_conn, put_conn
from psycopg2.extras import RealDictCursor
import baostock as bs
import threading
import time

router = APIRouter()
_bs_lock = threading.Lock()

# baostock 登录/登出管理
_bs_logged_in = False

def _bs_login():
    global _bs_logged_in
    if not _bs_logged_in:
        bs.login()
        _bs_logged_in = True

def _bs_logout():
    global _bs_logged_in
    if _bs_logged_in:
        bs.logout()
        _bs_logged_in = False


@router.get("/{code}")
async def stock_kline(
    code: str,
    days: int = Query(60, ge=5, le=500),
):
    """获取个股K线 — 先查本地 stock_hist，没有则实时从 baostock 拉取"""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 尝试多种格式匹配
            targets = [code]
            if not code.startswith(("sh.", "sz.", "bj")):
                targets.append(f"sh.{code}")
                targets.append(f"sz.{code}")
                targets.append(f"bj{code}")

            for target in targets:
                cur.execute("""
                    SELECT trade_date, open, close, high, low, volume, amount, change_pct
                    FROM stock_hist
                    WHERE code = %s
                    ORDER BY trade_date ASC
                    LIMIT %s
                """, (target, days))
                rows = cur.fetchall()
                if rows:
                    return [dict(r) for r in rows]
    finally:
        put_conn(conn)

    # 本地没有 → 实时从 baostock 拉取
    from datetime import date, timedelta
    end_date = date.today().strftime("%Y-%m-%d")
    start_date = (date.today() - timedelta(days=max(days, 500))).strftime("%Y-%m-%d")

    results = []
    with _bs_lock:
        _bs_login()
        try:
            for target in targets:
                rs = bs.query_history_k_data_plus(
                    target, "date,open,high,low,close,volume,amount,pctChg",
                    start_date=start_date, end_date=end_date,
                    frequency='d', adjustflag='2'
                )
                if rs.error_code != '0':
                    continue
                while rs.next():
                    rd = rs.get_row_data()
                    results.append({
                        "trade_date": rd[0],
                        "open": float(rd[1]) if rd[1] else None,
                        "close": float(rd[4]) if rd[4] else None,
                        "high": float(rd[2]) if rd[2] else None,
                        "low": float(rd[3]) if rd[3] else None,
                        "volume": float(rd[5]) if rd[5] else None,
                        "amount": float(rd[6]) if rd[6] else None,
                        "change_pct": float(rd[7]) if rd[7] else None,
                    })
                if results:
                    # 后台写入 store_hist 以便后续使用
                    _save_kline_async(target, results[-days:])
                    return results[-days:]
        finally:
            _bs_logout()

    return []


def _save_kline_async(code: str, rows: list[dict]):
    """异步写入 stock_hist 表"""
    if not rows:
        return
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            for r in rows:
                cur.execute("""
                    INSERT INTO stock_hist (code, trade_date, open, close, high, low, volume, amount, change_pct)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (code, trade_date) DO UPDATE SET
                        open=EXCLUDED.open, close=EXCLUDED.close,
                        high=EXCLUDED.high, low=EXCLUDED.low,
                        volume=EXCLUDED.volume, amount=EXCLUDED.amount,
                        change_pct=EXCLUDED.change_pct
                """, (
                    code, r["trade_date"], r.get("open"), r.get("close"),
                    r.get("high"), r.get("low"), r.get("volume"), r.get("amount"),
                    r.get("change_pct"),
                ))
        conn.commit()
    except Exception:
        pass
    finally:
        put_conn(conn)
