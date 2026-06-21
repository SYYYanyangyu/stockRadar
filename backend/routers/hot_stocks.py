"""涨停板 / 热门股 Router — 读本地 PostgreSQL"""
from fastapi import APIRouter, Query
from typing import Optional
from services.storage import query_all, query_page, latest_trade_date

router = APIRouter()


def _date() -> str:
    return latest_trade_date("zt_pool") or ""


@router.get("/zt-today")
async def zt_today(
    date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    d = date or _date()
    result = query_page("zt_pool", page=page, page_size=page_size, trade_date=d, order_by="streak DESC")
    streak_dist = {}
    for item in result["items"]:
        s = item.get("streak", 1) or 1
        streak_dist[s] = streak_dist.get(s, 0) + 1
    max_streak = max((item.get("streak", 1) or 1 for item in result["items"]), default=0)
    return {
        **result,
        "maxStreak": max_streak,
        "streakDist": streak_dist,
    }


@router.get("/zt-analysis")
async def zt_analysis(date: Optional[str] = Query(None)):
    """涨停复盘分析 — 封板质量 + 行业热力 + 时间分布"""
    d = date or _date()

    rows = query_all("zt_pool", trade_date=d, order_by="streak DESC")

    def seal_quality(row: dict) -> dict:
        """根据首次封板时间和炸板次数计算封板质量"""
        break_cnt = row.get("break_count") or 0
        first_time = row.get("first_seal_time") or ""
        time_order = row.get("last_seal_time") or ""

        # 时间评分
        if first_time and first_time <= "093500":
            time_label = "秒板"
            time_score = 5
        elif first_time and first_time <= "094500":
            time_label = "早封"
            time_score = 4
        elif first_time and first_time <= "100000":
            time_label = "早盘封"
            time_score = 3
        elif first_time and first_time <= "103000":
            time_label = "午前封"
            time_score = 2
        elif first_time:
            time_label = "午后封"
            time_score = 1
        else:
            time_label = "尾盘"
            time_score = 0

        # 炸板扣分
        if break_cnt == 0:
            break_label = "零炸板"
            break_score = 3
        elif break_cnt <= 2:
            break_label = f"炸{break_cnt}次"
            break_score = 2
        elif break_cnt <= 5:
            break_label = f"炸{break_cnt}次"
            break_score = 1
        else:
            break_label = f"炸{break_cnt}次"
            break_score = 0

        total = time_score + break_score
        if total >= 7:
            grade = "强势封板"
        elif total >= 5:
            grade = "一般封板"
        elif total >= 3:
            grade = "烂板"
        else:
            grade = "弱"

        return {
            "time_label": time_label,
            "time_score": time_score,
            "break_label": break_label,
            "break_score": break_score,
            "total_score": total,
            "grade": grade,
        }

    # 行业热力图
    industry_map: dict[str, dict] = {}
    for row in rows:
        ind = row.get("industry") or "其他"
        if ind not in industry_map:
            industry_map[ind] = {"name": ind, "count": 0, "stocks": [], "max_streak": 0}
        industry_map[ind]["count"] += 1
        industry_map[ind]["max_streak"] = max(industry_map[ind]["max_streak"], row.get("streak") or 0)
        if len(industry_map[ind]["stocks"]) < 6:
            industry_map[ind]["stocks"].append({"code": row["code"], "name": row["name"], "streak": row.get("streak") or 0})

    industries = sorted(industry_map.values(), key=lambda x: -x["count"])

    # 封板时间分布
    time_buckets = {"秒板(09:30-09:35)": 0, "早封(09:35-09:45)": 0, "早盘封(09:45-10:00)": 0, "午前封(10:00-10:30)": 0, "午后封(10:30后)": 0}
    for row in rows:
        ft = row.get("first_seal_time") or ""
        if ft <= "093500": time_buckets["秒板(09:30-09:35)"] += 1
        elif ft <= "094500": time_buckets["早封(09:35-09:45)"] += 1
        elif ft <= "100000": time_buckets["早盘封(09:45-10:00)"] += 1
        elif ft <= "103000": time_buckets["午前封(10:00-10:30)"] += 1
        else: time_buckets["午后封(10:30后)"] += 1

    time_dist = [{"label": k, "count": v} for k, v in time_buckets.items()]

    # 为每只票附加封板质量
    items_with_quality = []
    for row in rows:
        sq = seal_quality(row)
        # 计算封成比（封单金额/成交额），如果有 seal_amount 和 amount
        amount = float(row.get("amount") or 0)
        seal = float(row.get("seal_amount") or 0)
        seal_ratio = round(seal / amount, 2) if amount > 0 and seal > 0 else None
        items_with_quality.append({**row, "seal_quality": sq, "seal_ratio": seal_ratio})

    # 质量分布
    grade_dist = {}
    for item in items_with_quality:
        g = item["seal_quality"]["grade"]
        grade_dist[g] = grade_dist.get(g, 0) + 1

    # 烂板列表（炸板 3 次以上的票，按炸板次数降序）
    broken_boards = sorted(
        [{"code": r["code"], "name": r["name"], "break_count": r.get("break_count") or 0, "streak": r.get("streak") or 0}
         for r in rows if (r.get("break_count") or 0) >= 3],
        key=lambda x: -x["break_count"]
    )

    return {
        "trade_date": d,
        "total": len(rows),
        "items": items_with_quality,
        "industries": industries,
        "time_dist": time_dist,
        "grade_dist": grade_dist,
        "broken_boards": broken_boards,
        "max_streak": max((r.get("streak") or 0 for r in rows), default=0),
    }


@router.get("/rank")
async def gainers_rank(
    limit: int = Query(30, ge=1, le=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    d = _date()
    return query_page("gainers", page=page, page_size=page_size, trade_date=d, order_by="change_pct DESC")


@router.get("/hot")
async def hot_rank(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    d = _date()
    hot_result = query_page("hot_stocks", page=page, page_size=page_size, trade_date=d, order_by="rank ASC")
    if hot_result["items"]:
        return hot_result
    # fallback: 如果 hot_stocks 没拉到数据（东方财富限流），从 gainers 涨幅榜取
    rows = query_all("gainers", trade_date=d, order_by="change_pct DESC", limit=30)
    result = []
    for i, r in enumerate(rows):
        result.append({
            "rank": i + 1,
            "code": r["code"],
            "name": r["name"],
            "price": r["price"],
            "change_pct": r["change_pct"],
            "trade_date": d,
        })
    return {"items": result, "total": len(result), "page": 1, "page_size": 30}
