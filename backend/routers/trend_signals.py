"""趋势战法信号 Router — 读本地 PostgreSQL"""
from fastapi import APIRouter, Query
from typing import Optional
from services.storage import query_all, query_page, latest_trade_date

router = APIRouter()


def _date() -> str:
    return latest_trade_date("trend_signals") or ""


@router.get("/today")
async def today_signals(
    top: int = Query(30, ge=1, le=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    d = _date()
    result = query_page("trend_signals", page=page, page_size=page_size, trade_date=d, order_by="score DESC")
    for r in result["items"]:
        if isinstance(r.get("signals"), str):
            import json
            r["signals"] = json.loads(r["signals"])
    return result


@router.get("/{symbol}")
async def symbol_signals(symbol: str):
    d = _date()
    rows = query_all("trend_signals", trade_date=d, code=symbol)
    if rows:
        r = rows[0]
        if isinstance(r.get("signals"), str):
            import json
            r["signals"] = json.loads(r["signals"])
        return r
    return {"code": symbol, "score": 0, "signals": [], "error": "无数据"}
