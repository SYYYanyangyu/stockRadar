from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import hot_stocks, trend_signals, dragon_tiger, sectors, kline, margin, volume_anomaly, quiet_bulls, us_correlation, backtest, prediction
from services.storage import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="CorrBoard API", version="2.0.0",
              description="美股联动 · 涨停分析 · 龙虎榜 · 板块轮动 · 两融（本地PG存储）",
              lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(hot_stocks.router, prefix="/api/hot-stocks", tags=["涨停/热门"])
app.include_router(trend_signals.router, prefix="/api/trend-signals", tags=["趋势战法"])
app.include_router(dragon_tiger.router, prefix="/api/dragon-tiger", tags=["龙虎榜/资金"])
app.include_router(sectors.router, prefix="/api/sectors", tags=["板块轮动"])
app.include_router(kline.router, prefix="/api/stock-kline", tags=["个股K线"])
app.include_router(margin.router, prefix="/api/margin", tags=["两融数据"])
app.include_router(volume_anomaly.router, prefix="/api/volume-anomaly", tags=["成交量异动"])
app.include_router(quiet_bulls.router, prefix="/api/quiet-bulls", tags=["低调牛股"])
app.include_router(us_correlation.router, prefix="/api", tags=["美股联动"])
app.include_router(backtest.router, prefix="/api", tags=["回测验证"])
app.include_router(prediction.router, prefix="/api", tags=["明日预测"])


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "AStockRadar", "storage": "postgresql"}


@app.post("/api/refresh")
async def refresh_data():
    """手动触发数据刷新 — 从多源拉取最新数据写入 PG"""
    from services.pull_data import refresh_daily
    import asyncio
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, refresh_daily)
    return {"status": "ok", "message": "data refreshed"}
