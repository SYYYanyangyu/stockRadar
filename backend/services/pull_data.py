"""一次性初始化数据 — baostock 拉全A股历史K线 + akshare 补充当日行情"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import baostock as bs
import akshare as ak
import pandas as pd
import threading
from datetime import date, timedelta

from services.storage import init_db, upsert_many, delete_date, get_conn, put_conn

MIN_INTERVAL = 2.0  # baostock 没有严格限制，akshare 部分谨慎
_last_call = 0
_lock = threading.Lock()


def _wait():
    global _last_call
    with _lock:
        elapsed = time.time() - _last_call
        if elapsed < MIN_INTERVAL:
            time.sleep(MIN_INTERVAL - elapsed)
        _last_call = time.time()


def _today():
    return date.today().strftime("%Y%m%d")


def _ak(fn, name: str):
    """akshare 调用（需要限流）"""
    _wait()
    try:
        return fn()
    except Exception as e:
        print(f"  [{name}] ❌ {type(e).__name__}: {str(e)[:60]}")
        return None


# ══════════════════════════════════════════
# 全A股历史日K线 — baostock（免费，无频率限制）
# ══════════════════════════════════════════
def pull_all_stock_hist(days_back: int = 500):
    """用 baostock 一次性拉全A股历史日K线到 stock_hist"""
    print("\n📊 全A股历史日K线 (baostock)")

    bs.login()

    # 1. 获取全A股列表
    rs = bs.query_stock_basic()
    stocks = []
    while (rs.error_code == '0') & rs.next():
        row = rs.get_row_data()
        code = row[0]  # sh.600519
        name = row[1]
        # 只要正常A股（交易中的）
        if row[4] == '1':  # type=1 股票
            # 排除指数
            if not code.endswith(('.000001', '.000002', '.000003', '.399001', '.399005', '.399006')):
                stocks.append((code, name))

    print(f"  共 {len(stocks)} 只A股, 拉取近 {days_back} 天日K...")

    end_date = date.today().strftime("%Y-%m-%d")
    start_date = (date.today() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    batch = []
    total_inserted = 0
    for i, (code, name) in enumerate(stocks):
        rs = bs.query_history_k_data_plus(
            code, "date,open,high,low,close,volume,amount,pctChg",
            start_date=start_date, end_date=end_date,
            frequency='d', adjustflag='2'
        )
        while (rs.error_code == '0') & rs.next():
            rd = rs.get_row_data()
            batch.append({
                "code": code,
                "trade_date": rd[0],
                "open": float(rd[1]) if rd[1] else None,
                "high": float(rd[2]) if rd[2] else None,
                "low": float(rd[3]) if rd[3] else None,
                "close": float(rd[4]) if rd[4] else None,
                "volume": float(rd[5]) if rd[5] else None,
                "amount": float(rd[6]) if rd[6] else None,
                "change_pct": float(rd[7]) if rd[7] else None,
            })

        # 每500只写一次，避免内存爆炸
        if len(batch) >= 50000:
            _write_hist_batch(batch)
            total_inserted += len(batch)
            print(f"    [{i+1}/{len(stocks)}] {code} {name} — 已写入 {total_inserted} 条")
            batch = []

        if (i + 1) % 200 == 0:
            print(f"    [{i+1}/{len(stocks)}] {code} {name}")

    if batch:
        _write_hist_batch(batch)
        total_inserted += len(batch)

    bs.logout()
    print(f"  ✅ 总计写入 {total_inserted} 条日K数据")


def _write_hist_batch(rows: list[dict]):
    """批量写入 stock_hist (每50000条)"""
    if not rows:
        return
    conn = get_conn()
    try:
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
                    r["code"], r["trade_date"], r.get("open"), r.get("close"),
                    r.get("high"), r.get("low"), r.get("volume"), r.get("amount"),
                    r.get("change_pct"),
                ))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"    ⚠️ 写库失败: {e}")
    finally:
        put_conn(conn)


# ══════════════════════════════════════════
# 当日行情 — akshare 多源补充
# ══════════════════════════════════════════
def pull_zt_pool(trade_date: str):
    d = trade_date or _today()
    print(f"\n📊 涨停池 ({d})")
    df = _ak(lambda: ak.stock_zt_pool_em(date=d), "zt_pool")
    if df is None or df.empty:
        return
    wanted = ["代码","名称","涨跌幅","最新价","成交额","流通市值","封单资金","连板数","首次封板时间","最后封板时间","炸板次数","所属行业"]
    en_names = ["code","name","change_pct","price","amount","circ_mv","seal_amount","streak","first_seal_time","last_seal_time","break_count","industry"]
    rename = {k: v for k, v in zip(wanted, en_names) if k in df.columns}
    df = df.rename(columns=rename)
    rows = df[[c for c in en_names if c in df.columns]].to_dict("records")
    for r in rows:
        r["trade_date"] = d
    delete_date("zt_pool", d)
    upsert_many("zt_pool", rows)
    print(f"  -> {len(rows)} rows")


def pull_gainers_sina(trade_date: str):
    d = trade_date or _today()
    print(f"\n📊 涨幅榜 ({d}) — 新浪")
    df = _ak(lambda: ak.stock_zh_a_spot(), "gainers_sina")
    if df is None or df.empty:
        return
    df = df.rename(columns={
        "代码": "code", "名称": "name", "最新价": "price",
        "涨跌幅": "change_pct", "涨跌额": "change_amt",
        "成交量": "volume", "成交额": "amount",
        "最高": "high", "最低": "low", "今开": "open", "昨收": "pre_close",
    })
    df = df.sort_values("change_pct", ascending=False)
    wanted = ["code","name","price","change_pct","change_amt","volume","amount","high","low","open","pre_close"]
    rows = df[[c for c in wanted if c in df.columns]].to_dict("records")
    for r in rows:
        r["trade_date"] = d
    delete_date("gainers", d)
    upsert_many("gainers", rows)
    print(f"  -> {len(rows)} rows")


def pull_sector_ths(trade_date: str):
    d = trade_date or _today()
    import re

    # 新浪板块分类 indicator 参数: "新浪行业","概念","地域","行业","启明星行业"
    for indicator in ("概念", "行业"):
        print(f"\n📈 [{indicator}]板块 ({d}) — 新浪")
        try:
            _wait()
            spot = ak.stock_sector_spot(indicator=indicator)
        except Exception as e:
            print(f"  [{indicator}] ❌ {type(e).__name__}: {str(e)[:60]}")
            continue
        if spot is None or spot.empty:
            continue

        rows = []
        for _, row in spot.iterrows():
            code = str(row.get("股票代码", "")).replace("sh","").replace("sz","").replace("SH","").replace("SZ","")
            name = row.get("板块", "")[:64]
            change_pct_val = row.get("涨跌幅", 0)
            if pd.isna(change_pct_val):
                change_pct_val = 0
            top_stock = str(row.get("股票名称", ""))[:32]
            top_change = row.get("个股-涨跌幅", 0)
            if pd.isna(top_change):
                top_change = 0
            rows.append({
                "trade_date": d,
                "code": code,
                "name": name,
                "change_pct": round(float(change_pct_val), 2),
                "up_count": 0,
                "down_count": 0,
                "top_stock": top_stock,
                "top_change_pct": round(float(top_change), 2),
            })
        if rows:
            delete_date("sector_rank", d)
            upsert_many("sector_rank", rows, conflict_cols=["trade_date", "code"])
        print(f"  -> {len(rows)} rows")


def pull_north_bound():
    print("\n🌏 北向资金")
    total_net_flow = 0
    total_balance = 0
    latest_date = None
    for channel in ("沪股通", "深股通"):
        df = _ak(lambda ch=channel: ak.stock_hsgt_hist_em(symbol=ch), f"north_{channel}")
        if df is None or df.empty:
            continue
        last_row = df.iloc[-1]
        if latest_date is None:
            latest_date = str(last_row.get("日期", ""))
        net = last_row.get("当日成交净买额")
        bal = last_row.get("当日余额")
        if pd.notna(net):
            total_net_flow += float(net)
        if pd.notna(bal):
            total_balance += float(bal)
    if latest_date:
        upsert_many("north_bound", [{
            "trade_date": latest_date, "net_flow": round(total_net_flow, 4),
            "balance": round(total_balance, 4),
        }], conflict_cols=["trade_date"])
        print(f"  -> date={latest_date}, net_flow={round(total_net_flow,4)}")


def pull_dragon_tiger(trade_date: str):
    d = trade_date or _today()
    print(f"\n🐉 龙虎榜 ({d}) — zzshare")

    from zzshare.client import DataApi
    api = DataApi()

    # 1. 龙虎榜列表 — zzshare 数据很全：换手率、振幅、游资、连板描述
    try:
        items = api.lhb_list(date1=d)
    except Exception as e:
        print(f"  [lhb_list] ❌ {type(e).__name__}: {str(e)[:60]}")
        return

    if not items:
        print(f"  ⚠️ {d} 无龙虎榜数据（可能非交易日），尝试前一天")
        # 自动往回找最近交易日
        from datetime import timedelta
        for offset in range(1, 8):
            prev = (date.today() - timedelta(days=offset)).strftime("%Y%m%d")
            try:
                items = api.lhb_list(date1=prev)
            except Exception:
                continue
            if items:
                d = prev
                print(f"  -> 使用最近交易日: {d}")
                break

    if not items:
        print("  ⚠️ 最近7天无龙虎榜数据")
        return

    # 2. 新浪行情（补充最新价/涨跌幅，zzshare 没提供实时行情）
    _wait()
    try:
        df_spot = ak.stock_zh_a_spot()
    except Exception as e:
        print(f"  [spot] ❌ {type(e).__name__}: {str(e)[:60]}")
        df_spot = None

    spot_map = {}
    if df_spot is not None and not df_spot.empty:
        for _, row in df_spot.iterrows():
            code_spot = row.get("代码", "")
            code_short = code_spot.replace("sz","").replace("sh","").replace("bj","")
            spot_map[code_short] = (row.get("最新价", 0), row.get("涨跌幅", 0))

    # 3. 合并
    rows = []
    seat_rows = []
    for item in items:
        code = item.get("stock_code", "")
        r = {
            "trade_date": d,
            "code": code,
            "name": (item.get("stock_name", "") or "")[:32],
            "reason": (item.get("up_reason", "") or "")[:256],
            "turnover_ratio": round(float(item.get("turnover_ratio", 0) or 0), 2),
            "amplitude": round(float(item.get("amplitude", 0) or 0), 2),
            "up_desc": str(item.get("up_desc", "") or "")[:32],
            "join_num": int(item.get("join_num", 0) or 0),
            # zzshare buy_in 是净买额（元），转万元
            "net_buy": round(float(item.get("buy_in", 0) or 0) / 10000, 2),
        }
        # buy_amount/sell_amount: zzshare 没直接提供，需从席位汇总
        buy_group = item.get("buy_group_icons") or []
        sell_group = item.get("sell_group_icons") or []
        buy_seats = len(buy_group)
        sell_seats = len(sell_group)
        r["buy_seats"] = buy_seats
        r["sell_seats"] = sell_seats

        # 价格/涨跌幅来自新浪行情
        if code in spot_map:
            r["price"] = float(spot_map[code][0]) if spot_map[code][0] else None
            r["change_pct"] = float(spot_map[code][1]) if spot_map[code][1] else None
        else:
            r["price"] = None
            r["change_pct"] = None

        # 从 lhb_detail 获取席位明细（limit 5只 sample to avoid rate limit）
        if len(seat_rows) < 50:
            try:
                detail = api.lhb_detail(date1=d, stock_code=code)
                if detail:
                    traders = detail.get("traders") or []
                    for t in traders:
                        seat_rows.append({
                            "trade_date": d,
                            "code": code,
                            "rank": t.get("rank"),
                            "trader_name": t.get("trader_name", "")[:128],
                            "trader_type": "buy" if t.get("type") == 1 else "sell",
                            "group_name": t.get("group_icon", "")[:64] if t.get("group_icon") else None,
                            "buy_amount": round(float(t.get("buy_amount", 0) or 0) / 10000, 2),
                            "sell_amount": round(float(t.get("sell_amount", 0) or 0) / 10000, 2),
                            "reason_type": t.get("reason_type", ""),
                        })
            except Exception:
                pass  # lhb_detail 偶尔超时，不影响主流程

        rows.append(r)

    delete_date("dragon_tiger", d)
    upsert_many("dragon_tiger", rows)
    print(f"  -> {len(rows)} rows")

    if seat_rows:
        from services.storage import get_conn, put_conn
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM dragon_tiger_seats WHERE trade_date = %s", (d,))
                for s in seat_rows:
                    cur.execute("""
                        INSERT INTO dragon_tiger_seats
                            (trade_date, code, rank, trader_name, trader_type, group_name, buy_amount, sell_amount, reason_type)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (trade_date, code, rank, trader_type) DO UPDATE SET
                            trader_name=EXCLUDED.trader_name,
                            group_name=EXCLUDED.group_name,
                            buy_amount=EXCLUDED.buy_amount,
                            sell_amount=EXCLUDED.sell_amount
                    """, (s["trade_date"], s["code"], s["rank"], s["trader_name"],
                          s["trader_type"], s["group_name"], s["buy_amount"], s["sell_amount"],
                          s["reason_type"]))
            conn.commit()
        finally:
            put_conn(conn)
        print(f"  -> {len(seat_rows)} 条席位明细")


def pull_hot_rank(trade_date: str):
    d = trade_date or _today()
    print(f"\n🔥 人气榜 ({d})")
    df = _ak(lambda: ak.stock_hot_rank_em(), "hot_rank")
    if df is None or df.empty:
        return
    # columns: 当前排名, 代码, 股票名称, 最新价, 涨跌额, 涨跌幅
    en_names = {"当前排名": "rank", "代码": "code", "股票名称": "name", "最新价": "price", "涨跌幅": "change_pct"}
    df = df.rename(columns=en_names)
    df = df.sort_values("rank").head(100)
    wanted = ["code","name","price","change_pct","rank"]
    rows = df[[c for c in wanted if c in df.columns]].to_dict("records")
    for r in rows:
        r["trade_date"] = d
        # code starts with SH/SZ, strip prefix
        r["code"] = (r["code"] or "").replace("SZ","").replace("SH","")
        r["rank"] = int(r["rank"])
    delete_date("hot_stocks", d)
    upsert_many("hot_stocks", rows)
    print(f"  -> {len(rows)} rows")


# ══════════════════════════════════════════
# 趋势信号 — 本地计算
# ══════════════════════════════════════════
def compute_trend_signals(trade_date: str):
    """从本地 stock_hist 计算所有股票的趋势信号"""
    from services.trend_engine import scan_all_from_db, save_trend_signals
    print(f"\n📐 计算趋势信号 (>=20分)")

    # 先确保 stock_hist 里有当日数据 — 从涨跌幅榜同步 close/change_pct
    sync_daily_close(trade_date)

    signals = scan_all_from_db(trade_date, top_n=30, min_score=20)
    save_trend_signals(trade_date, signals)
    print(f"  -> {len(signals)} 只有信号")
    for s in signals:
        print(f"    {s['code']} {s.get('name','')} score={s['score']}")
    return signals


def sync_daily_close(trade_date: str):
    """把 gainers 表的当日行情同步到 stock_hist（确保趋势引擎有最新数据 + 成交量完整）"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO stock_hist (code, trade_date, open, high, low, close, volume, amount, change_pct)
                SELECT
                    code, trade_date,
                    open, high, low, price as close,
                    volume, amount, change_pct
                FROM gainers
                WHERE trade_date = %s
                ON CONFLICT (code, trade_date) DO UPDATE SET
                    close = EXCLUDED.close,
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    change_pct = EXCLUDED.change_pct,
                    volume = EXCLUDED.volume,
                    amount = EXCLUDED.amount
            """, (trade_date,))
            conn.commit()
            cur.execute("SELECT count(*) FROM stock_hist WHERE trade_date = %s", (trade_date,))
            count = cur.fetchone()[0]
            print(f"  stock_hist 当日覆盖: {count} 只")
    finally:
        put_conn(conn)


# ══════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════
def init_all():
    """首次运行：拉历史K线 + 当日行情 + 计算趋势信号"""
    d = _today()
    init_db()

    # Step 1: 拉全A股历史K线 (baostock, 一次性)
    pull_all_stock_hist(days_back=500)

    # Step 2: 当日行情 (akshare 多源)
    pull_zt_pool(d)
    pull_gainers_sina(d)
    pull_sector_ths(d)
    pull_north_bound()
    pull_hot_rank(d)
    pull_dragon_tiger(d)
    compute_trend_signals(d)

    print("\n✅ 全部初始化完成")


def pull_margin(trade_date: str = None):
    """拉取融资融券数据 — akshare"""
    d = trade_date or _today()

    print(f"\n💰 两融数据 ({d}) — akshare")

    rows = []

    # 上交所融资融券
    for market_name, pull_fn in [
        ("上交所", lambda: ak.stock_margin_detail_sse(date=d)),
        ("深交所", lambda: ak.stock_margin_detail_szse(date=d)),
    ]:
        try:
            _wait()
            df = pull_fn()
        except Exception as e:
            print(f"  [{market_name}] ❌ {type(e).__name__}: {str(e)[:120]}")
            continue

        if df is None or df.empty:
            print(f"  [{market_name}] ⚠️ 无数据")
            continue

        for _, row in df.iterrows():
            code = str(row.get("标的证券代码", "") or row.get("证券代码", ""))
            name = str(row.get("标的证券简称", "") or row.get("证券简称", ""))[:32]
            rows.append({
                "trade_date": d,
                "code": code,
                "name": name,
                "margin_buy": float(row.get("融资买入额", 0) or 0),
                "margin_sell": float(row.get("融资偿还额", 0) or 0),
                "margin_balance": float(row.get("融资余额", 0) or 0),
                "short_sell": float(row.get("融券卖出量", 0) or 0),
                "short_balance": float(row.get("融券余量", 0) or 0),
                "total_balance": float(row.get("融资融券余额", 0) or 0),
            })

    if rows:
        delete_date("margin_trading", d)
        upsert_many("margin_trading", rows)
        print(f"  -> {len(rows)} rows")
    else:
        print("  ⚠️ 无两融数据")


def pull_sector_stocks(trade_date: str = None):
    """拉取所有板块的成分股 — akshare stock_sector_detail"""
    d = trade_date or _today()

    print(f"\n📋 板块成分股 ({d}) — akshare")

    # 先获取板块列表（含 label）
    sectors_by_name: dict[str, str] = {}  # name → label
    for indicator in ("概念", "行业"):
        _wait()
        try:
            spot = ak.stock_sector_spot(indicator=indicator)
        except Exception as e:
            print(f"  [{indicator}] ❌ {type(e).__name__}: {str(e)[:120]}")
            continue
        if spot is None or spot.empty:
            continue
        for _, row in spot.iterrows():
            name = str(row.get("板块", ""))[:64]
            label = str(row.get("label", ""))
            if name and label:
                sectors_by_name[name] = label

    print(f"  共 {len(sectors_by_name)} 个板块")

    all_rows = []
    for i, (name, label) in enumerate(sectors_by_name.items()):
        _wait()
        try:
            detail = ak.stock_sector_detail(sector=label)
        except Exception as e:
            print(f"  [{name}] ❌ {type(e).__name__}: {str(e)[:80]}")
            continue
        if detail is None or detail.empty:
            continue
        for _, row in detail.iterrows():
            code = str(row.get("code", ""))
            stk_name = str(row.get("name", ""))[:32]
            all_rows.append({
                "trade_date": d,
                "sector_code": name,
                "code": code,
                "name": stk_name,
                "change_pct": float(row.get("changepercent", 0) or 0),
            })
        if (i + 1) % 50 == 0:
            print(f"    [{i+1}/{len(sectors_by_name)}] {name} — {len(all_rows)} rows so far")

    if all_rows:
        delete_date("sector_stocks", d)
        upsert_many("sector_stocks", all_rows, conflict_cols=["trade_date", "sector_code", "code"])
        print(f"  -> {len(all_rows)} rows (unique sector+code)")
    else:
        print("  ⚠️ 无成分股数据")


# ══════════════════════════════════════════
# 美股三大指数 — akshare index_us_stock_sina
# ══════════════════════════════════════════
US_INDEX_MAP = {
    ".INX": "标普500",
    ".IXIC": "纳斯达克",
    ".DJI": "道琼斯",
}


def pull_us_indices():
    """拉取美股三大指数历史日线数据（全量写入 us_indices）"""
    print("\n🇺🇸 美股三大指数历史数据")

    total = 0
    for symbol, name in US_INDEX_MAP.items():
        print(f"  拉取 {symbol} ({name})...")
        df = _ak(lambda sym=symbol: ak.index_us_stock_sina(symbol=sym), f"us_index_{symbol}")
        if df is None or df.empty:
            print(f"    [{symbol}] ⚠️ 无数据")
            continue

        # columns: date, open, high, low, close, volume
        rows = []
        for _, rd in df.iterrows():
            trade_date = str(rd.get("date", ""))
            close_val = float(rd["close"]) if rd.get("close") is not None else None
            open_val = float(rd["open"]) if rd.get("open") is not None else None
            prev_close = None
            change_pct = None
            # Compute change_pct if prev_close available
            if len(rows) > 0 and rows[-1]["close"] is not None and close_val is not None:
                prev_close = rows[-1]["close"]
                change_pct = round((close_val / prev_close - 1) * 100, 2)

            rows.append({
                "symbol": symbol,
                "name": name,
                "trade_date": trade_date,
                "open": open_val,
                "close": close_val,
                "high": float(rd["high"]) if rd.get("high") is not None else None,
                "low": float(rd["low"]) if rd.get("low") is not None else None,
                "volume": float(rd["volume"]) if rd.get("volume") is not None else None,
                "change_pct": change_pct,
            })

        if rows:
            upsert_many("us_indices", rows, conflict_cols=["symbol", "trade_date"])
            total += len(rows)
            print(f"    [{symbol}] {len(rows)} rows")

    print(f"  ✅ 总计 {total} 条美股指数数据")


def pull_us_indices_daily():
    """每日增量拉取美股指数最新数据"""
    print("\n🇺🇸 美股指数增量更新")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for symbol, name in US_INDEX_MAP.items():
                df = _ak(lambda sym=symbol: ak.index_us_stock_sina(symbol=sym), f"us_index_{symbol}")
                if df is None or df.empty:
                    continue

                last = df.iloc[-1]
                trade_date = str(last.get("date", ""))
                # 检查是否已有
                cur.execute(
                    "SELECT 1 FROM us_indices WHERE symbol=%s AND trade_date=%s",
                    (symbol, trade_date),
                )
                if cur.fetchone():
                    continue

                # 取前一天 close 算涨跌幅
                cur.execute(
                    "SELECT close FROM us_indices WHERE symbol=%s ORDER BY trade_date DESC LIMIT 1",
                    (symbol,),
                )
                prev = cur.fetchone()
                prev_close = float(prev[0]) if prev else None
                close_val = float(last["close"])
                change_pct = (
                    round((close_val / prev_close - 1) * 100, 2)
                    if prev_close and prev_close > 0
                    else None
                )

                cur.execute(
                    """INSERT INTO us_indices (symbol, name, trade_date, open, close, high, low, volume, change_pct)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (symbol, trade_date) DO NOTHING""",
                    (
                        symbol, name, trade_date,
                        float(last["open"]), close_val,
                        float(last["high"]), float(last["low"]),
                        float(last["volume"]), change_pct,
                    ),
                )
                print(f"  [{symbol}] {trade_date} 已写入")
        conn.commit()
    finally:
        put_conn(conn)


def refresh_daily():
    """每日刷新：只拉当日行情 + 重新算趋势"""
    d = _today()
    init_db()

    pull_zt_pool(d)
    pull_gainers_sina(d)
    pull_sector_ths(d)
    pull_sector_stocks(d)
    pull_north_bound()
    pull_hot_rank(d)
    pull_dragon_tiger(d)
    pull_margin(d)
    compute_trend_signals(d)

    # 美股联动
    pull_us_indices_daily()
    try:
        from services.correlation_engine import compute_us_correlation, compute_concept_correlation
        compute_us_correlation()
        compute_concept_correlation()
    except Exception as e:
        print(f"  [美股联动计算] ⚠️ {e}")

    print("\n✅ 每日刷新完成")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "init"
    if cmd == "init":
        init_all()
    elif cmd == "daily":
        refresh_daily()
    else:
        print(f"Usage: python pull_data.py [init|daily]")
