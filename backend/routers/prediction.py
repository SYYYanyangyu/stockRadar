"""明日预测 API"""
import json
import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services.prediction_engine import compute_prediction, PREDICTION_CACHE

router = APIRouter()


@router.get("/prediction")
async def prediction():
    """返回明日A股概念预测（基于当晚美股收盘数据）"""
    if not os.path.exists(PREDICTION_CACHE):
        compute_prediction()

    try:
        with open(PREDICTION_CACHE) as f:
            data = json.load(f)
        return JSONResponse(content=data)
    except Exception:
        return JSONResponse(content={"error": "failed to load prediction"}, status_code=500)


@router.post("/prediction/refresh")
async def prediction_refresh():
    """强制刷新预测"""
    data = compute_prediction()
    return JSONResponse(content={"status": "ok", "predictions_count": len(data.get("predictions", []))})
