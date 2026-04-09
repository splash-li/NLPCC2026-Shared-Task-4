#!/usr/bin/env python3
"""
Single-entry demo backtest runner for the competition starter kit.
"""

import argparse
import asyncio
import json
import os
import sys
import time
import traceback
from pathlib import Path

from loguru import logger

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from agent_platform.agents.advanced_agents import get_advanced_agent
from agent_platform.agents.trading_strategy_prompt import BASELINE_TRADING_PROMPT
from agent_platform.client.platform_client import PlatformClient
from config import AGENT_PLATFORM
from server_platform.app.models.backtest import AgentDecision

MAJOR_FUND_POOL = [
    "000300.SH",
    "000905.SH",
    "399006.SZ",
    "000688.SH",
    "000932.SH",
    "000941.SH",
    "399971.SZ",
    "000819.SH",
    "000928.SH",
    "000012.SH",
    "518880.SH",
]

INDUSTRY_FUND_POOL = [
    "512880.SH",
    "512800.SH",
    "512070.SH",
    "159995.SZ",
    "159819.SZ",
    "515880.SH",
    "159852.SZ",
    "512010.SH",
    "512170.SH",
    "159992.SZ",
    "515170.SH",
    "512690.SH",
    "512400.SH",
    "515220.SH",
    "159870.SZ",
    "512200.SH",
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run one demo backtest for the competition starter kit."
    )
    parser.add_argument("--track", choices=["macro", "sector"], default="sector")
    parser.add_argument("--model", default="gpt-5")
    parser.add_argument("--start-date", default="2025-01-02")
    parser.add_argument("--end-date", default="2025-01-31")
    parser.add_argument("--initial-capital", type=float, default=100000)
    parser.add_argument("--lookback-days", type=int, default=5)
    parser.add_argument("--top-rank", type=int, default=20)
    parser.add_argument("--pre-k-days", type=int, default=1)
    parser.add_argument("--history-days", type=int, default=5)
    parser.add_argument("--username", default=AGENT_PLATFORM["AGENT_USERNAME"])
    parser.add_argument("--password", default=AGENT_PLATFORM["AGENT_PASSWORD"])
    parser.add_argument("--base-url", default=AGENT_PLATFORM["BASE_URL"])
    parser.add_argument("--results-dir", default=None)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def build_config(args):
    fund_pool = MAJOR_FUND_POOL if args.track == "macro" else INDUSTRY_FUND_POOL
    default_results_dir = (
        "backtest_results_macro_demo"
        if args.track == "macro"
        else "backtest_results_sector_demo"
    )
    return {
        "start_date": args.start_date,
        "end_date": args.end_date,
        "initial_capital": args.initial_capital,
        "fund_pool": fund_pool,
        "agents": [{"name": args.username, "prompt": "..."}],
        "news_sources": ["caixin", "tiantian", "sinafinance", "tencent"],
        "lookback_days": args.lookback_days,
        "top_rank": args.top_rank,
        "pre_k_days": args.pre_k_days,
        "view_platform_trading_history_days": args.history_days,
        "decision_model_name": args.model,
        "results_dir": args.results_dir or default_results_dir,
    }


def build_output_path(args, session_id):
    if args.output:
        return Path(args.output)
    out_dir = Path(project_root) / "agent_platform" / "demo_outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{args.track}_{args.model}_{session_id}.json"


async def run_demo_backtest(args):
    client = PlatformClient(base_url=args.base_url)
    client.register(args.username, args.password)
    client.login(args.username, args.password)

    config = build_config(args)
    agent = get_advanced_agent(
        agent_id=f"{args.track}_demo_agent",
        trading_prompt_template=BASELINE_TRADING_PROMPT,
        decision_model_name=args.model,
    )

    start_response = client.start_backtest(config)
    session_id = start_response["session_id"]
    data = start_response.get("data")

    if not data:
        raise RuntimeError("Failed to get initial backtest data.")

    logger.info(
        f"Started session {session_id} for track={args.track}, model={args.model}"
    )

    trading_days = 0
    while True:
        trading_days += 1
        portfolio = client.get_backtest_status(session_id)
        historical_prices = client.get_historical_prices(
            session_id, lookback_days=config["lookback_days"]
        )

        try:
            decision_result = await agent.make_decision(
                date_to_decision=data["date"],
                news_data=data["news"],
                historical_prices=historical_prices.get("historical_prices", {}),
                current_portfolio=portfolio,
                market_data=data["market_data"],
                fund_pool=config["fund_pool"],
                view_platform_trading_history_days=config[
                    "view_platform_trading_history_days"
                ],
            )

            final_decision = decision_result["final_decision"]
            trades = [
                trade
                for trade in final_decision.get("trades", [])
                if trade.get("action") != "hold"
            ]

            if trades:
                agent_decision = AgentDecision(
                    decision=final_decision,
                    reasoning=final_decision.get("reasoning", ""),
                    chain_of_thought=str(final_decision.get("chain_of_thought", "")),
                )
                client.submit_trade_with_decision(session_id, trades, agent_decision)
        except Exception as exc:
            logger.error(f"Decision failed on {data.get('date')}: {exc}")
            logger.error(traceback.format_exc())

        data = client.get_next_day_data(session_id)
        if data.get("message") == "Backtest finished":
            break

        await asyncio.sleep(0.05)

    final_results = client.get_backtest_results(session_id)
    output_path = build_output_path(args, session_id)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(final_results, handle, indent=2, ensure_ascii=False)

    logger.info(
        f"Finished session {session_id} after {trading_days} trading days. "
        f"Return={final_results.get('performance', {}).get('total_return', 0) * 100:.2f}%"
    )
    logger.info(f"Saved final results to {output_path}")


def main():
    args = parse_args()
    log_dir = Path(project_root) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"demo_backtest_{time.strftime('%Y%m%d-%H%M%S')}.log"
    logger.add(str(log_path), level="INFO")

    logger.info(
        f"Running demo backtest with track={args.track}, model={args.model}, "
        f"period={args.start_date}~{args.end_date}"
    )
    try:
        asyncio.run(run_demo_backtest(args))
    except Exception as exc:
        logger.error(f"Demo backtest failed: {exc}")
        logger.error(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
