"""AKShare 客户端封装 — 涨停池、龙虎榜、板块概念、资金流向"""
import akshare as ak
import pandas as pd
from datetime import date, datetime
from typing import Optional
import time
import threading

MIN_INTERVAL = 3.0  # 东方财富 API 请求最小间隔（秒），避免频率限流
_last_call: float = 0
_lock = threading.Lock()


def _rate_limit():
    """全局限流：确保两次 eastmoney 请求间隔 >= MIN_INTERVAL"""
    global _last_call
    with _lock:
        elapsed = time.time() - _last_call
        if elapsed < MIN_INTERVAL:
            time.sleep(MIN_INTERVAL - elapsed)
        _last_call = time.time()


def _today_str() -> str:
    return date.today().strftime("%Y%m%d")


def _retry(fn, retries: int = 3, delay: float = 2.0):
    """带重试的调用封装，处理 SSL/超时等临时错误"""
    last_err = None
    for i in range(retries + 1):
        try:
            _rate_limit()
            return fn()
        except Exception as e:
            last_err = e
            if i < retries:
                time.sleep(delay * (i + 1))
    print(f"[akshare] retry exhausted: {last_err}")
    return None


# ──────────────────────────────────────
# 涨停板 / 热门股
# ──────────────────────────────────────

def get_zt_pool(trade_date: Optional[str] = None) -> list[dict]:
    """今日涨停池 — 东方财富
    返回字段：代码、名称、涨跌幅、最新价、成交额、流通市值、封单资金、连板数、首次封板时间、最后封板时间、炸板次数、所属行业
    """
    d = trade_date or _today_str()
    try:
        df = _retry(lambda: ak.stock_zt_pool_em(date=d))
        if df is None or df.empty:
            return []
        df = df.rename(columns={
            "代码": "code", "名称": "name", "涨跌幅": "change_pct",
            "最新价": "price", "成交额": "amount", "流通市值": "circ_mv",
            "封单资金": "seal_amount", "连板数": "streak",
            "首次封板时间": "first_seal_time", "最后封板时间": "last_seal_time",
            "炸板次数": "break_count", "所属行业": "industry",
        })
        cols = ["code", "name", "change_pct", "price", "amount", "circ_mv",
                "seal_amount", "streak", "first_seal_time", "last_seal_time",
                "break_count", "industry"]
        return df[[c for c in cols if c in df.columns]].to_dict("records")
    except Exception as e:
        print(f"[akshare] get_zt_pool error: {e}")
        return []


def _normalize_columns(df: pd.DataFrame, rename_map: dict) -> pd.DataFrame:
    """先用 rename_map 映射，再对残留的中文列名做二次匹配"""
    df = df.rename(columns=rename_map)
    # 如果 rename_map 里有多个候选中文名对应同一个英文名，做兜底
    # 例如 "名称"/"股票名称" -> "name"
    reverse = {}  # 英文名 -> 所有候选中文名
    for cn, en in rename_map.items():
        reverse.setdefault(en, []).append(cn)
    for col in list(df.columns):
        if col in rename_map:
            continue  # 已经成功 rename
        for en_name, cn_candidates in reverse.items():
            if en_name in df.columns:
                continue  # 目标英文名列已存在
            if col in cn_candidates:
                df = df.rename(columns={col: en_name})
                break
    return df


def get_top_gainers(limit: int = 30) -> list[dict]:
    """涨幅排行榜 — A 股实时行情"""
    try:
        df = _retry(lambda: ak.stock_zh_a_spot_em())
        if df is None or df.empty:
            return []
        # akshare 列名可能变动，兼容多种列名
        rename_map = {
            "代码": "code", "名称": "name", "股票名称": "name",
            "最新价": "price", "涨跌幅": "change_pct", "涨跌额": "change_amt",
            "成交量": "volume", "成交额": "amount",
            "最高": "high", "最低": "low", "今开": "open",
            "昨收": "pre_close", "换手率": "turnover",
        }
        df = _normalize_columns(df, rename_map)
        df = df.sort_values("change_pct", ascending=False).head(limit)
        cols = ["code", "name", "price", "change_pct", "change_amt",
                "volume", "amount", "high", "low", "open", "pre_close", "turnover"]
        return df[[c for c in cols if c in df.columns]].to_dict("records")
    except Exception as e:
        print(f"[akshare] get_top_gainers error: {e}")
        return []


def get_hot_rank() -> list[dict]:
    """东方财富人气榜 — 热门股"""
    try:
        df = _retry(lambda: ak.stock_hot_rank_em())
        if df is None or df.empty:
            return []
        rename_map = {
            "当前排名": "rank", "代码": "code", "名称": "name", "股票名称": "name",
            "最新价": "price", "涨跌幅": "change_pct",
        }
        df = _normalize_columns(df, rename_map)
        return df.head(30).to_dict("records")
    except Exception as e:
        print(f"[akshare] get_hot_rank error: {e}")
        return []


# ──────────────────────────────────────
# 龙虎榜
# ──────────────────────────────────────

def get_dragon_tiger(trade_date: Optional[str] = None) -> list[dict]:
    """龙虎榜明细 — 东方财富"""
    d = trade_date or _today_str()
    try:
        df = _retry(lambda: ak.stock_lhb_detail_em(start_date=d, end_date=d))
        if df is None or df.empty:
            # 今天可能还没收盘，尝试取上一个交易日
            df = _retry(lambda: ak.stock_lhb_detail_em(start_date="", end_date=d))
        if df is None or df.empty:
            return []
        rename_map = {
            "代码": "code", "名称": "name", "上榜日期": "date",
            "解读": "reason", "收盘价": "price", "涨跌幅": "change_pct",
            "龙虎榜净买额": "net_buy", "龙虎榜买入额": "buy_amount",
            "龙虎榜卖出额": "sell_amount", "龙虎榜成交额": "total_amount",
            "市场总成交额": "market_amount", "净买额占总成交比": "net_pct",
            "成交额占总成交比": "amount_pct", "换手率": "turnover",
            "流通市值": "circ_mv",
        }
        df = _normalize_columns(df, rename_map)
        return df.to_dict("records")
    except Exception as e:
        print(f"[akshare] get_dragon_tiger error: {e}")
        return []


# ──────────────────────────────────────
# 资金流向
# ──────────────────────────────────────

def get_fund_flow_rank(limit: int = 30) -> list[dict]:
    """个股资金流排名 — 今日主力净流入"""
    try:
        df = _retry(lambda: ak.stock_individual_fund_flow_rank(indicator="今日"))
        if df is None or df.empty:
            return []
        rename_map = {
            "代码": "code", "名称": "name", "最新价": "price",
            "涨跌幅": "change_pct",
            "主力净流入-净额": "main_net",
            "主力净流入-净占比": "main_pct",
            "超大单净流入-净额": "super_large_net",
            "超大单净流入-净占比": "super_large_pct",
            "大单净流入-净额": "large_net",
            "大单净流入-净占比": "large_pct",
            "中单净流入-净额": "mid_net",
            "小单净流入-净额": "small_net",
        }
        df = _normalize_columns(df, rename_map)
        df = df.sort_values("main_net", ascending=False).head(limit)
        return df.to_dict("records")
    except Exception as e:
        print(f"[akshare] get_fund_flow_rank error: {e}")
        return []


def get_north_bound() -> dict:
    """北向资金（沪股通+深股通）当日净流入"""
    try:
        # 旧接口 stock_hsgt_north_net_flow_in_em 已移除，改用沪股通+深股通分别查询
        total_net_flow = 0
        total_balance = 0
        latest_date = None
        for channel in ("沪股通", "深股通"):
            df = _retry(lambda ch=channel: ak.stock_hsgt_hist_em(symbol=ch))
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
        if latest_date is None:
            return {}
        return {
            "date": latest_date,
            "net_flow": round(total_net_flow, 4),
            "balance": round(total_balance, 4),
        }
    except Exception as e:
        print(f"[akshare] get_north_bound error: {e}")
        return {}


# ──────────────────────────────────────
# 板块概念
# ──────────────────────────────────────

def get_sector_rank() -> list[dict]:
    """概念板块涨幅排行"""
    try:
        df = _retry(lambda: ak.stock_board_concept_name_em(), retries=3, delay=2.0)
        if df is None or df.empty:
            return []
        rename_map = {
            "排名": "rank", "板块名称": "name", "名称": "name", "板块代码": "code",
            "最新价": "price", "涨跌幅": "change_pct",
            "总市值": "total_mv", "换手率": "turnover",
            "上涨家数": "up_count", "下跌家数": "down_count",
            "领涨股票": "top_stock", "领涨涨跌幅": "top_change_pct",
        }
        df = _normalize_columns(df, rename_map)
        df = df.sort_values("change_pct", ascending=False)
        return df.to_dict("records")
    except Exception as e:
        print(f"[akshare] get_sector_rank error: {e}")
        return []


def get_sector_stocks(sector_code: str) -> list[dict]:
    """板块内个股列表"""
    try:
        df = _retry(lambda: ak.stock_board_concept_cons_em(symbol=sector_code))
        if df is None or df.empty:
            return []
        rename_map = {
            "代码": "code", "名称": "name", "股票名称": "name", "最新价": "price",
            "涨跌幅": "change_pct", "成交额": "amount",
            "换手率": "turnover",
        }
        df = _normalize_columns(df, rename_map)
        df = df.sort_values("change_pct", ascending=False).head(10)
        return df.to_dict("records")
    except Exception as e:
        print(f"[akshare] get_sector_stocks error: {e}")
        return []
