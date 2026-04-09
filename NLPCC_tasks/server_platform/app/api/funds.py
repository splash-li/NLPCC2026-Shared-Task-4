from fastapi import APIRouter
from server_platform.app.core.fund_info import FUND_INFO

router = APIRouter()


@router.get("/funds", tags=["funds"])
def get_fund_info():
    """
    Retrieve information about all available funds.
    """
    return FUND_INFO
