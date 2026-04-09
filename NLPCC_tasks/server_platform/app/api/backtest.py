import time
from typing import Any, Dict, List

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from config import BACKTEST_DEFAULTS
from logs import server_logger as logger
from server_platform.app.api.agents import get_current_user
from server_platform.app.core.backtest import (
    create_backtest_session,
    create_backtest_session_with_restore,
    get_all_backtest_sessions,
    get_backtest_session,
    load_session_by_id,
)
from server_platform.app.core.fund_info import FUND_INFO
from server_platform.app.models.backtest import AgentDecision, BacktestConfig, NewsRequest, Trade

router = APIRouter()

VISUALIZATION_CACHE = {}
CACHE_TTL = 3600


def calculate_sharpe_ratio(portfolio_history):
    """Calculate annualized Sharpe ratio from daily portfolio history."""
    if not portfolio_history or len(portfolio_history) < 2:
        return 0.0

    values = np.array([day["value"] for day in portfolio_history])
    with np.errstate(divide="ignore", invalid="ignore"):
        daily_returns = np.diff(values) / values[:-1]

    daily_returns = daily_returns[np.isfinite(daily_returns)]
    if len(daily_returns) == 0:
        return 0.0

    std_daily_return = np.std(daily_returns)
    if std_daily_return == 0:
        return 0.0

    mean_daily_return = np.mean(daily_returns)
    daily_rf = BACKTEST_DEFAULTS.get("risk_free_rate", 0.0) / 252
    excess_return = mean_daily_return - daily_rf
    return (excess_return / std_daily_return) * np.sqrt(252)


def get_aligned_portfolio_history(
    results: Dict[str, Any], initial_capital: float, normalize: bool = False
) -> List[Dict[str, Any]]:
    """
    Reconstruct a daily close-aligned portfolio history.

    Raw portfolio_value_history is recorded before the current trading day is
    settled, so a row stamped with day D usually represents the portfolio at
    D-1 close. The final finish() call writes the actual last-day close again.
    """
    raw_history = results.get("portfolio_value_history", [])
    aligned_history: List[Dict[str, Any]] = []

    if raw_history:
        frame = pd.DataFrame(raw_history)
        frame["date"] = pd.to_datetime(frame["date"])
        frame = frame.sort_values("date").reset_index(drop=True)

        if len(frame) == 1:
            aligned_history = [
                {
                    "date": frame.iloc[0]["date"].strftime("%Y-%m-%d"),
                    "value": float(frame.iloc[0].get("value", 0) or 0),
                    "cash": float(frame.iloc[0].get("cash", 0) or 0),
                }
            ]
        else:
            for index in range(len(frame) - 2):
                aligned_history.append(
                    {
                        "date": frame.iloc[index]["date"].strftime("%Y-%m-%d"),
                        "value": float(frame.iloc[index + 1].get("value", 0) or 0),
                        "cash": float(frame.iloc[index + 1].get("cash", 0) or 0),
                    }
                )

            aligned_history.append(
                {
                    "date": frame.iloc[-1]["date"].strftime("%Y-%m-%d"),
                    "value": float(frame.iloc[-1].get("value", 0) or 0),
                    "cash": float(frame.iloc[-1].get("cash", 0) or 0),
                }
            )

    if not aligned_history:
        snapshots = results.get("daily_portfolio_snapshots", [])
        after_trade_snapshots = [s for s in snapshots if s.get("snapshot_type") == "after_trade"]
        aligned_history = [
            {
                "date": snapshot.get("date", ""),
                "value": float(snapshot.get("total_value", 0) or 0),
                "cash": float(snapshot.get("capital", 0) or 0),
            }
            for snapshot in after_trade_snapshots
        ]

    if normalize and initial_capital > 0:
        return [
            {
                "date": item["date"],
                "value": item["value"] / initial_capital,
                "cash": item["cash"] / initial_capital,
            }
            for item in aligned_history
        ]

    return aligned_history


def get_cached_response(cache_key: str):
    cached_item = VISUALIZATION_CACHE.get(cache_key)
    if not cached_item:
        return None

    timestamp, cached_response = cached_item
    if time.time() - timestamp < CACHE_TTL:
        return cached_response

    VISUALIZATION_CACHE.pop(cache_key, None)
    return None


def set_cached_response(cache_key: str, response: JSONResponse):
    VISUALIZATION_CACHE[cache_key] = (time.time(), response)
    return response


def warm_up_visualization_cache():
    """Competition starter kit does not pre-warm heavy historical views."""
    return None


def _clean_data_for_json(data: Any) -> Any:
    """Recursively clean data for safe JSON serialization."""
    if data is None:
        return None
    if isinstance(data, (int, str, bool)):
        return data
    if isinstance(data, float):
        return None if pd.isna(data) or np.isinf(data) else data
    if isinstance(data, dict):
        return {k: _clean_data_for_json(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_clean_data_for_json(item) for item in data]
    try:
        return str(data)
    except Exception:
        return None


@router.post("/start")
def start_backtest(config: BacktestConfig, current_user: dict = Depends(get_current_user)):
    logger.info(f"User '{current_user.get('username')}' starting new backtest session.")
    logger.debug(f"Backtest config: {config.model_dump_json(indent=2)}")

    try:
        config_dict = config.dict()
        if not config_dict.get("fund_pool"):
            logger.info("Fund pool is empty, using all available funds as default.")
            config_dict["fund_pool"] = list(FUND_INFO.keys())

        session_id = create_backtest_session(config_dict)
        session = get_backtest_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Backtest session not found")

        initial_data = session.start()
        logger.info(f"Backtest session '{session_id}' created successfully")
        return {"session_id": session_id, "data": _clean_data_for_json(initial_data)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start backtest session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to start backtest session.")


@router.post("/resume")
def resume_backtest(resume_data: dict, current_user: dict = Depends(get_current_user)):
    """Resume a backtest session from previously saved results."""
    logger.info(f"User '{current_user.get('username')}' resuming backtest session.")

    try:
        config = resume_data.get("config")
        saved_data = resume_data.get("saved_data", {})

        if not config:
            raise HTTPException(status_code=400, detail="Missing config in request")

        if not config.get("fund_pool"):
            logger.info("Fund pool is empty, using all available funds as default.")
            config["fund_pool"] = list(FUND_INFO.keys())

        session_id = create_backtest_session_with_restore(session_id=None, config=config, saved_data=saved_data)
        session = get_backtest_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Backtest session not found")

        current_data = session.get_day_data()
        logger.info(
            f"Backtest session '{session_id}' resumed successfully, current date: {current_data.get('date')}"
        )
        return {"session_id": session_id, "data": _clean_data_for_json(current_data)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resume backtest session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to resume backtest session.")


@router.post("/{session_id}/trade")
def submit_trade(
    session_id: str,
    trades: List[Trade],
    agent_decision: AgentDecision = None,
    current_user: dict = Depends(get_current_user),
):
    logger.info(f"Received trade submission for session '{session_id}'.")
    session = get_backtest_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Backtest session not found")

    try:
        trade_results = session.submit_trades(
            [trade.dict() for trade in trades], agent_decision.dict() if agent_decision else None
        )
        return _clean_data_for_json(trade_results)
    except Exception as e:
        logger.error(f"Error processing trades for session '{session_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error processing trades.")


@router.get("/{session_id}/status")
def get_backtest_status(session_id: str, current_user: dict = Depends(get_current_user)):
    session = get_backtest_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Backtest session not found")
    return _clean_data_for_json(session.get_portfolio_status())


@router.get("/{session_id}/next_day")
def get_next_day_data(session_id: str, current_user: dict = Depends(get_current_user)):
    session = get_backtest_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Backtest session not found")
    next_day_data = session.next_day()
    if session.is_finished:
        return {"message": "Backtest finished", "session_id": session_id}
    return _clean_data_for_json(next_day_data)


@router.get("/{session_id}/day_data")
def get_day_data(session_id: str, current_user: dict = Depends(get_current_user)):
    session = get_backtest_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Backtest session not found")
    return _clean_data_for_json(session.get_day_data())


@router.post("/{session_id}/news")
def get_news_data(session_id: str, news_request: NewsRequest, current_user: dict = Depends(get_current_user)):
    session = get_backtest_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Backtest session not found")

    try:
        news_data = session.data_loader.get_news(
            sources=news_request.sources,
            current_date=session.current_date,
            top_rank=news_request.top_rank,
            pre_k_days=news_request.pre_k_days,
        )
        return {"news": _clean_data_for_json(news_data)}
    except Exception as e:
        logger.error(f"Failed to get news for session '{session_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve news data.")


@router.get("/{session_id}/market_data")
def get_market_data(session_id: str, current_user: dict = Depends(get_current_user)):
    session = get_backtest_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Backtest session not found")
    return {"market_data": _clean_data_for_json(session.get_market_data())}


@router.get("/{session_id}/historical_prices")
def get_historical_prices(
    session_id: str, lookback_days: int = 1, current_user: dict = Depends(get_current_user)
):
    session = get_backtest_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Backtest session not found")

    historical_data = session.data_loader.get_historical_prices(
        fund_ids=session.backtest_config["fund_pool"],
        current_date=session.current_date,
        lookback_days=lookback_days,
    )
    return {"historical_prices": _clean_data_for_json(historical_data)}


@router.get("/{session_id}/decisions")
def get_agent_decisions(session_id: str, current_user: dict = Depends(get_current_user)):
    session = get_backtest_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Backtest session not found")
    return {"decisions": _clean_data_for_json(session.agent_decisions)}


@router.get("/results/{session_id}")
def get_backtest_results(session_id: str, current_user: dict = Depends(get_current_user)):
    session = get_backtest_session(session_id)
    if not session:
        session = load_session_by_id(session_id)
    if not session or not session.is_finished:
        raise HTTPException(status_code=404, detail="Backtest results not found or not finished")
    return _clean_data_for_json(session.get_results())


@router.get("/results/{session_id}/visualize")
def get_visualization_data(session_id: str):
    cache_key = f"session_visualize_{session_id}"
    cached_response = get_cached_response(cache_key)
    if cached_response:
        return cached_response

    session = load_session_by_id(session_id)
    if not session or not session.is_finished:
        raise HTTPException(status_code=404, detail="Backtest results not found or not finished")

    results = session.get_results()
    if not results:
        raise HTTPException(status_code=404, detail="Backtest results are empty")

    fund_pool = session.backtest_config.get("fund_pool", [])
    fund_performance_data = {}
    if fund_pool:
        all_fund_data = session.data_loader.get_historical_prices_for_funds(
            fund_ids=fund_pool, start_date=session.start_date, end_date=session.end_date
        )
        for fund_id, price_data in all_fund_data.items():
            if not price_data:
                continue
            price_data.sort(key=lambda x: x["date"])
            initial_price = next(
                (point.get("close") for point in price_data if point.get("close") is not None and point.get("close") > 0),
                None,
            )
            if not initial_price:
                continue
            fund_performance_data[fund_id] = [
                {"date": point["date"], "value": point["close"] / initial_price}
                for point in price_data
                if point.get("close") is not None
            ]

    benchmark_performance = []
    if fund_performance_data:
        all_dates = sorted({d["date"] for perfs in fund_performance_data.values() for d in perfs})
        fund_perf_map = {fid: {d["date"]: d["value"] for d in perfs} for fid, perfs in fund_performance_data.items()}
        for date in all_dates:
            daily_values = [fund_perf_map[fid].get(date) for fid in fund_performance_data if fund_perf_map[fid].get(date) is not None]
            if daily_values:
                benchmark_performance.append({"date": date, "value": sum(daily_values) / len(daily_values)})

    csi300_benchmark_data = []
    try:
        csi300_raw_data = session.data_loader.get_benchmark_data(session.start_date, session.end_date)
        if csi300_raw_data:
            initial_benchmark_close = csi300_raw_data[0]["close"]
            if initial_benchmark_close > 0:
                csi300_benchmark_data = [
                    {"date": item["date"], "value": item["close"] / initial_benchmark_close}
                    for item in csi300_raw_data
                ]
    except Exception as e:
        logger.warning(f"Failed to fetch CSI 300 benchmark data for session {session_id}: {e}")

    visualization_data = {
        "agent_performance": get_aligned_portfolio_history(results, session.initial_capital, normalize=True),
        "fund_performance": {
            f"{fund_id} ({FUND_INFO.get(fund_id, {}).get('name', 'Unknown')})": perf
            for fund_id, perf in fund_performance_data.items()
        },
        "benchmark_performance": benchmark_performance,
        "csi300_benchmark": csi300_benchmark_data,
        "transaction_history": results.get("transaction_history", []),
    }

    response = JSONResponse(
        content=_clean_data_for_json(visualization_data),
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"},
    )
    return set_cached_response(cache_key, response)


@router.get("/sessions")
def list_backtest_sessions(current_user: dict = Depends(get_current_user)):
    sessions = get_all_backtest_sessions()
    return [
        {
            "session_id": s.session_id,
            "agent_name": s.agent_name,
            "start_date": s.backtest_config["start_date"],
            "end_date": s.backtest_config["end_date"],
            "initial_capital": s.backtest_config["initial_capital"],
            "is_finished": s.is_finished,
        }
        for s in sessions
    ]


@router.get("/visualize/{session_id}")
def get_visualization(session_id: str):
    return FileResponse("frontend/public/backtest_visualization.html")


@router.get("/results/{session_id}/trading_signals")
def get_trading_signals(session_id: str):
    cache_key = f"trading_signals_{session_id}"
    cached_response = get_cached_response(cache_key)
    if cached_response:
        return cached_response

    session = load_session_by_id(session_id)
    if not session or not session.is_finished:
        raise HTTPException(status_code=404, detail="Backtest results not found or not finished")

    results = session.get_results()
    if not results:
        raise HTTPException(status_code=404, detail="Backtest results are empty")

    trading_signals = []
    for transaction in results.get("transaction_history", []):
        fund_id = transaction.get("fund_id")
        trading_signals.append(
            {
                "date": transaction.get("date"),
                "fund_name": FUND_INFO.get(fund_id, {}).get("name", fund_id),
                "signal": transaction.get("action"),
                "amount": transaction.get("amount") or transaction.get("amount_sold"),
                "commission": transaction.get("commission", 0),
            }
        )

    trading_signals.sort(key=lambda x: x["date"])
    response = JSONResponse(
        content=_clean_data_for_json(trading_signals),
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"},
    )
    return set_cached_response(cache_key, response)


@router.get("/results/{session_id}/portfolio_history")
def get_portfolio_history(session_id: str):
    cache_key = f"portfolio_history_{session_id}"
    cached_response = get_cached_response(cache_key)
    if cached_response:
        return cached_response

    session = load_session_by_id(session_id)
    if not session or not session.is_finished:
        raise HTTPException(status_code=404, detail="Backtest results not found or not finished")

    results = session.get_results()
    if not results:
        raise HTTPException(status_code=404, detail="Backtest results are empty")

    portfolio_history = get_aligned_portfolio_history(results, session.initial_capital, normalize=False)
    portfolio_with_details = [
        {
            "date": item.get("date"),
            "cash": item.get("cash", 0) or 0,
            "total_value": item.get("value", 0) or 0,
            "holdings_value": (item.get("value", 0) or 0) - (item.get("cash", 0) or 0),
        }
        for item in portfolio_history
    ]

    response = JSONResponse(
        content=_clean_data_for_json(portfolio_with_details),
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"},
    )
    return set_cached_response(cache_key, response)


@router.get("/results/{session_id}/holdings_details")
def get_holdings_details(session_id: str):
    """Return holding details reconstructed from daily portfolio snapshots."""
    cache_key = f"holdings_details_{session_id}"
    cached_response = get_cached_response(cache_key)
    if cached_response:
        return cached_response

    session = load_session_by_id(session_id)
    if not session or not session.is_finished:
        raise HTTPException(status_code=404, detail="Backtest results not found or not finished")

    results = session.get_results()
    if not results:
        raise HTTPException(status_code=404, detail="Backtest results are empty")

    snapshots = results.get("daily_portfolio_snapshots", [])
    holdings_details = {}

    def get_fund_display_name(fund_id: str) -> str:
        return FUND_INFO.get(fund_id, {}).get("name", fund_id)

    for snapshot in snapshots:
        date = snapshot.get("date")
        snapshot_type = snapshot.get("snapshot_type")
        holdings = snapshot.get("holdings", {})
        if not date:
            continue

        holdings_list = [
            {
                "fund_id": fund_id,
                "fund_name": get_fund_display_name(fund_id),
                "value": holding_info.get("value", 0),
                "close_price": holding_info.get("close_price"),
            }
            for fund_id, holding_info in holdings.items()
        ]
        holdings_list.sort(key=lambda x: x.get("value", 0), reverse=True)

        processed_trades = []
        for trade in snapshot.get("trades_executed", []):
            trade_fund_id = trade.get("fund_id", "")
            processed_trades.append({**trade, "fund_name": get_fund_display_name(trade_fund_id)})

        key = f"{date}_{snapshot_type}" if snapshot_type != "before_trade" else date
        holdings_details[key] = {
            "date": date,
            "snapshot_type": snapshot_type,
            "capital": snapshot.get("capital", 0),
            "total_value": snapshot.get("total_value", 0),
            "holdings": holdings_list,
            "trades_executed": processed_trades,
        }

    response = JSONResponse(
        content=_clean_data_for_json(holdings_details),
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"},
    )
    return set_cached_response(cache_key, response)
