"""PostgreSQL 存储层 — 所有行情数据落地到本地 PG"""
import psycopg2
import psycopg2.pool
from psycopg2.extras import RealDictCursor
from datetime import date
from typing import Optional

DSN = "host=localhost port=5432 dbname=astockradar user=aiuser password=123456"

_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None


def get_pool():
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(2, 10, DSN)
    return _pool


def get_conn():
    return get_pool().getconn()


def put_conn(conn):
    get_pool().putconn(conn)


# ─────────── DDL ───────────

TABLES = {
    "zt_pool": """
        CREATE TABLE IF NOT EXISTS zt_pool (
            id SERIAL PRIMARY KEY,
            trade_date DATE NOT NULL DEFAULT CURRENT_DATE,
            code VARCHAR(10) NOT NULL,
            name VARCHAR(32),
            change_pct DOUBLE PRECISION,
            price DOUBLE PRECISION,
            amount DOUBLE PRECISION,
            circ_mv DOUBLE PRECISION,
            seal_amount DOUBLE PRECISION,
            streak INTEGER,
            first_seal_time VARCHAR(16),
            last_seal_time VARCHAR(16),
            break_count INTEGER,
            industry VARCHAR(64),
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(trade_date, code)
        );
    """,
    "gainers": """
        CREATE TABLE IF NOT EXISTS gainers (
            id SERIAL PRIMARY KEY,
            trade_date DATE NOT NULL DEFAULT CURRENT_DATE,
            code VARCHAR(10) NOT NULL,
            name VARCHAR(32),
            price DOUBLE PRECISION,
            change_pct DOUBLE PRECISION,
            change_amt DOUBLE PRECISION,
            volume DOUBLE PRECISION,
            amount DOUBLE PRECISION,
            high DOUBLE PRECISION,
            low DOUBLE PRECISION,
            open DOUBLE PRECISION,
            pre_close DOUBLE PRECISION,
            turnover DOUBLE PRECISION,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(trade_date, code)
        );
    """,
    "hot_stocks": """
        CREATE TABLE IF NOT EXISTS hot_stocks (
            id SERIAL PRIMARY KEY,
            trade_date DATE NOT NULL DEFAULT CURRENT_DATE,
            rank INTEGER,
            code VARCHAR(10) NOT NULL,
            name VARCHAR(32),
            price DOUBLE PRECISION,
            change_pct DOUBLE PRECISION,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(trade_date, code)
        );
    """,
    "dragon_tiger": """
        CREATE TABLE IF NOT EXISTS dragon_tiger (
            id SERIAL PRIMARY KEY,
            trade_date DATE NOT NULL,
            code VARCHAR(10) NOT NULL,
            name VARCHAR(32),
            reason TEXT,
            price DOUBLE PRECISION,
            change_pct DOUBLE PRECISION,
            net_buy DOUBLE PRECISION,
            buy_amount DOUBLE PRECISION,
            sell_amount DOUBLE PRECISION,
            total_amount DOUBLE PRECISION,
            market_amount DOUBLE PRECISION,
            net_pct DOUBLE PRECISION,
            amount_pct DOUBLE PRECISION,
            turnover DOUBLE PRECISION,
            circ_mv DOUBLE PRECISION,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(trade_date, code)
        );
    """,
    "fund_flow": """
        CREATE TABLE IF NOT EXISTS fund_flow (
            id SERIAL PRIMARY KEY,
            trade_date DATE NOT NULL DEFAULT CURRENT_DATE,
            code VARCHAR(10) NOT NULL,
            name VARCHAR(32),
            price DOUBLE PRECISION,
            change_pct DOUBLE PRECISION,
            main_net DOUBLE PRECISION,
            main_pct DOUBLE PRECISION,
            super_large_net DOUBLE PRECISION,
            super_large_pct DOUBLE PRECISION,
            large_net DOUBLE PRECISION,
            large_pct DOUBLE PRECISION,
            mid_net DOUBLE PRECISION,
            small_net DOUBLE PRECISION,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(trade_date, code)
        );
    """,
    "north_bound": """
        CREATE TABLE IF NOT EXISTS north_bound (
            id SERIAL PRIMARY KEY,
            trade_date DATE NOT NULL UNIQUE,
            net_flow DOUBLE PRECISION DEFAULT 0,
            balance DOUBLE PRECISION DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """,
    "sector_rank": """
        CREATE TABLE IF NOT EXISTS sector_rank (
            id SERIAL PRIMARY KEY,
            trade_date DATE NOT NULL DEFAULT CURRENT_DATE,
            rank INTEGER,
            name VARCHAR(64),
            code VARCHAR(16) NOT NULL,
            price DOUBLE PRECISION,
            change_pct DOUBLE PRECISION,
            total_mv DOUBLE PRECISION,
            turnover DOUBLE PRECISION,
            up_count INTEGER,
            down_count INTEGER,
            top_stock VARCHAR(32),
            top_change_pct DOUBLE PRECISION,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(trade_date, code)
        );
    """,
    "sector_stocks": """
        CREATE TABLE IF NOT EXISTS sector_stocks (
            id SERIAL PRIMARY KEY,
            trade_date DATE NOT NULL DEFAULT CURRENT_DATE,
            sector_code VARCHAR(64) NOT NULL,
            code VARCHAR(10) NOT NULL,
            name VARCHAR(32),
            price DOUBLE PRECISION,
            change_pct DOUBLE PRECISION,
            amount DOUBLE PRECISION,
            turnover DOUBLE PRECISION,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(trade_date, sector_code, code)
        );
    """,
    "stock_hist": """
        CREATE TABLE IF NOT EXISTS stock_hist (
            id SERIAL PRIMARY KEY,
            code VARCHAR(10) NOT NULL,
            trade_date DATE NOT NULL,
            open DOUBLE PRECISION,
            close DOUBLE PRECISION,
            high DOUBLE PRECISION,
            low DOUBLE PRECISION,
            volume DOUBLE PRECISION,
            amount DOUBLE PRECISION,
            change_pct DOUBLE PRECISION,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(code, trade_date)
        );
        CREATE INDEX IF NOT EXISTS idx_stock_hist_code ON stock_hist(code);
        CREATE INDEX IF NOT EXISTS idx_stock_hist_date ON stock_hist(trade_date);
        CREATE INDEX IF NOT EXISTS idx_stock_hist_code_date_vol ON stock_hist(code, trade_date DESC, volume);
    """,
    "trend_signals": """
        CREATE TABLE IF NOT EXISTS trend_signals (
            id SERIAL PRIMARY KEY,
            trade_date DATE NOT NULL DEFAULT CURRENT_DATE,
            code VARCHAR(10) NOT NULL,
            name VARCHAR(32),
            price DOUBLE PRECISION,
            change_pct DOUBLE PRECISION,
            score INTEGER DEFAULT 0,
            signals JSONB DEFAULT '[]',
            ma5 DOUBLE PRECISION,
            ma10 DOUBLE PRECISION,
            ma20 DOUBLE PRECISION,
            ma60 DOUBLE PRECISION,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(trade_date, code)
        );
    """,
    "margin_trading": """
        CREATE TABLE IF NOT EXISTS margin_trading (
            id SERIAL PRIMARY KEY,
            trade_date DATE NOT NULL DEFAULT CURRENT_DATE,
            code VARCHAR(10) NOT NULL,
            name VARCHAR(32),
            margin_buy DOUBLE PRECISION,
            margin_sell DOUBLE PRECISION,
            margin_balance DOUBLE PRECISION,
            short_sell DOUBLE PRECISION,
            short_balance DOUBLE PRECISION,
            total_balance DOUBLE PRECISION,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(trade_date, code)
        );
    """,
    "margin_daily": """
        CREATE TABLE IF NOT EXISTS margin_daily (
            id SERIAL PRIMARY KEY,
            trade_date DATE NOT NULL UNIQUE,
            total_margin_balance DOUBLE PRECISION,
            total_margin_buy DOUBLE PRECISION,
            total_balance DOUBLE PRECISION,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """,
    "dragon_tiger_seats": """
        CREATE TABLE IF NOT EXISTS dragon_tiger_seats (
            id SERIAL PRIMARY KEY,
            trade_date DATE NOT NULL,
            code VARCHAR(10) NOT NULL,
            rank INTEGER,
            trader_name VARCHAR(128),
            trader_type VARCHAR(10),
            group_name VARCHAR(64),
            buy_amount DOUBLE PRECISION,
            sell_amount DOUBLE PRECISION,
            reason_type VARCHAR(32),
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_seats_unique ON dragon_tiger_seats(trade_date, code, rank, trader_type);
        CREATE INDEX IF NOT EXISTS idx_seats_trader ON dragon_tiger_seats(trader_name);
        CREATE INDEX IF NOT EXISTS idx_seats_group ON dragon_tiger_seats(group_name);
        CREATE INDEX IF NOT EXISTS idx_seats_date_code ON dragon_tiger_seats(trade_date, code);
    """,
    "stock_name": """
        CREATE TABLE IF NOT EXISTS stock_name (
            code VARCHAR(10) PRIMARY KEY,
            name VARCHAR(32) NOT NULL
        );
    """,
    "us_indices": """
        CREATE TABLE IF NOT EXISTS us_indices (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(16) NOT NULL,
            name VARCHAR(64),
            trade_date DATE NOT NULL,
            open DOUBLE PRECISION,
            close DOUBLE PRECISION,
            high DOUBLE PRECISION,
            low DOUBLE PRECISION,
            volume DOUBLE PRECISION,
            change_pct DOUBLE PRECISION,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(symbol, trade_date)
        );
    """,
    "us_correlation_result": """
        CREATE TABLE IF NOT EXISTS us_correlation_result (
            id SERIAL PRIMARY KEY,
            calc_date DATE NOT NULL,
            us_index VARCHAR(16) NOT NULL,
            stock_code VARCHAR(10) NOT NULL,
            stock_name VARCHAR(32),
            corr_10d DOUBLE PRECISION,
            corr_15d DOUBLE PRECISION,
            corr_20d DOUBLE PRECISION,
            beta DOUBLE PRECISION,
            overnight_gap DOUBLE PRECISION,
            a_stock_change DOUBLE PRECISION,
            us_change DOUBLE PRECISION,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(calc_date, us_index, stock_code)
        );
        CREATE INDEX IF NOT EXISTS idx_corr_calc_idx
            ON us_correlation_result(calc_date, us_index, corr_10d DESC);
        CREATE INDEX IF NOT EXISTS idx_corr_stock
            ON us_correlation_result(stock_code, us_index);
    """,
        "us_concept_correlation": """
            CREATE TABLE IF NOT EXISTS us_concept_correlation (
                id SERIAL PRIMARY KEY,
                calc_date DATE NOT NULL,
                us_index VARCHAR(16) NOT NULL,
                concept_name VARCHAR(64) NOT NULL,
                icon VARCHAR(8),
                stock_count INTEGER,
                total_constituents INTEGER,
                corr_10d_avg DOUBLE PRECISION,
                corr_15d_avg DOUBLE PRECISION,
                corr_20d_avg DOUBLE PRECISION,
                corr_10d_std DOUBLE PRECISION,
                corr_15d_std DOUBLE PRECISION,
                corr_20d_std DOUBLE PRECISION,
                consistency_10d DOUBLE PRECISION,
                consistency_15d DOUBLE PRECISION,
                consistency_20d DOUBLE PRECISION,
                composite_score_10d DOUBLE PRECISION,
                composite_score_15d DOUBLE PRECISION,
                composite_score_20d DOUBLE PRECISION,
                avg_beta DOUBLE PRECISION,
                top_stocks JSONB,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(calc_date, us_index, concept_name)
            );
            CREATE INDEX IF NOT EXISTS idx_ucc_calc_score
                ON us_concept_correlation(calc_date, us_index, composite_score_10d DESC);
        """,
}


def init_db():
    """建表"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for name, sql in TABLES.items():
                cur.execute(sql)
        conn.commit()
        print("[storage] tables initialized")
    finally:
        put_conn(conn)


# ─────────── 通用读写 ───────────

def upsert_many(table: str, rows: list[dict], conflict_cols: list[str] = None):
    """批量 upsert — 逐行执行，简单可靠"""
    if not rows:
        return
    conflict_cols = conflict_cols or ["trade_date", "code"]
    keys = list(rows[0].keys())
    cols = ", ".join(keys)
    placeholders = ", ".join(["%s"] * len(keys))
    conflict = ", ".join(conflict_cols)
    updates = ", ".join(f"{k}=EXCLUDED.{k}" for k in keys if k not in conflict_cols)
    sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) ON CONFLICT ({conflict}) DO UPDATE SET {updates}"

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for r in rows:
                cur.execute(sql, tuple(r.get(k) for k in keys))
        conn.commit()
    finally:
        put_conn(conn)


def query_all(table: str, trade_date: str = None, order_by: str = None,
              limit: int = None, **filters) -> list[dict]:
    """查询表数据"""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            sql = f"SELECT * FROM {table} WHERE 1=1"
            params = {}
            if trade_date:
                sql += " AND trade_date = %(trade_date)s"
                params["trade_date"] = trade_date
            for k, v in filters.items():
                sql += f" AND {k} = %({k})s"
                params[k] = v
            if order_by:
                sql += f" ORDER BY {order_by}"
            if limit:
                sql += f" LIMIT {limit}"
            cur.execute(sql, params)
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    finally:
        put_conn(conn)


def latest_trade_date(table: str) -> Optional[str]:
    """获取某表最新交易日期"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT MAX(trade_date) FROM {table}")
            row = cur.fetchone()
            return str(row[0]) if row and row[0] else None
    finally:
        put_conn(conn)


def query_page(table: str, page: int = 1, page_size: int = 20,
               trade_date: str = None, order_by: str = None, **filters) -> dict:
    """分页查询表数据 → {items, total, page, page_size}"""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            where = ["1=1"]
            params = {}
            if trade_date:
                where.append("trade_date = %(trade_date)s")
                params["trade_date"] = trade_date
            for k, v in filters.items():
                where.append(f"{k} = %({k})s")
                params[k] = v
            where_clause = " AND ".join(where)

            cur.execute(f"SELECT count(*) as cnt FROM {table} WHERE {where_clause}", params)
            total = cur.fetchone()["cnt"]

            sql = f"SELECT * FROM {table} WHERE {where_clause}"
            if order_by:
                sql += f" ORDER BY {order_by}"
            sql += f" LIMIT %(limit)s OFFSET %(offset)s"
            params["limit"] = page_size
            params["offset"] = (page - 1) * page_size
            cur.execute(sql, params)
            rows = cur.fetchall()
            return {
                "items": [dict(r) for r in rows],
                "total": total,
                "page": page,
                "page_size": page_size,
            }
    finally:
        put_conn(conn)


def delete_date(table: str, trade_date: str):
    """删除某天数据（刷新前清理）"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM {table} WHERE trade_date = %s", (trade_date,))
        conn.commit()
    finally:
        put_conn(conn)
