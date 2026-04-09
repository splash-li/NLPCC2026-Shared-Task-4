from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from reporting.fund_arena import build_scenario_report, get_available_scenarios

router = APIRouter()


@router.get("/fund-manager/scenarios")
def list_report_scenarios(top_k: int | None = Query(None, description="Optional Top-K news configuration to inspect")):
    return JSONResponse(content={"scenarios": get_available_scenarios(top_k=top_k)})


@router.get("/fund-manager/scenario")
def get_fund_manager_report(
    year: str = Query(..., description="Scenario year, such as 2024 or 2025"),
    category: str = Query(..., description="Scenario category: Major or Industry"),
    top_k: int = Query(10, description="Top-K news configuration to inspect"),
):
    normalized_category = category.title()
    if normalized_category not in {"Major", "Industry"}:
        raise HTTPException(status_code=400, detail="category must be Major or Industry")

    report = build_scenario_report(year=year, category=normalized_category, top_k=top_k)
    return JSONResponse(content=report)
