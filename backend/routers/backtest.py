"""回测验证 API — 美股→A股联动预测能力"""
import json
import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services.backtest_engine import compute_backtest, BACKTEST_CACHE

router = APIRouter()


@router.get("/backtest")
async def backtest():
    """
    完整回测结果：
    - summary: 全局统计
    - by_concept: 概念×指数 全量回测
    - by_index: 按指数汇总
    - extreme_analysis: 极端行情梯度
    - time_stability: 分时期稳定性（锂电池×纳指）
    """
    if not os.path.exists(BACKTEST_CACHE):
        compute_backtest()

    try:
        with open(BACKTEST_CACHE) as f:
            data = json.load(f)
        return JSONResponse(content=data)
    except Exception:
        return JSONResponse(content={"error": "failed to load backtest data"}, status_code=500)


@router.post("/backtest/refresh")
async def backtest_refresh():
    """强制刷新回测数据（一次全量计算约耗时几秒）"""
    data = compute_backtest()
    return JSONResponse(content={"status": "ok", "summary": data["summary"]})
