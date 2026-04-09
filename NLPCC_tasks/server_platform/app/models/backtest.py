from typing import Any, Dict, List, Optional

from pydantic import BaseModel, root_validator


class Trade(BaseModel):
    fund_id: str
    action: str  # "buy" or "sell"
    amount: Optional[float] = None  # For "buy" action: the amount of money to invest
    percentage: Optional[float] = (
        None  # For "sell" action: the percentage of holdings to sell (e.g., 0.5 for 50%)
    )

    @root_validator(pre=True)
    def check_action_fields(cls, values):
        action = values.get("action")
        amount = values.get("amount")
        percentage = values.get("percentage")

        if action == "buy":
            if amount is None or percentage is not None:
                raise ValueError("For 'buy' action, 'amount' must be set and 'percentage' must be None.")
            if amount <= 0:
                raise ValueError("'amount' must be positive for 'buy' action.")
        elif action == "sell":
            if percentage is None or amount is not None:
                raise ValueError("For 'sell' action, 'percentage' must be set and 'amount' must be None.")
            if not (0 < percentage <= 1):
                raise ValueError("'percentage' must be between 0 and 1 for 'sell' action.")

        return values


class AgentConfig(BaseModel):
    name: str
    prompt: str


class BacktestConfig(BaseModel):
    start_date: str
    end_date: str
    initial_capital: float
    fund_pool: Optional[List[str]] = None  # 允许为空，默认使用所有基金
    agents: List[AgentConfig]
    news_sources: Optional[List[str]] = ["caixin", "tiantian", "sinafinance", "tencent"]
    top_rank: Optional[int] = 10
    lookback_days: Optional[int] = 1  # 回看几天的行情信息
    pre_k_days: Optional[int] = 1  # 前几天的新闻
    view_platform_trading_history_days: Optional[int] = 1
    decision_model_name: Optional[str] = None
    results_dir: Optional[str] = "backtest_results_industry_2024"


class BacktestResult(BaseModel):
    agent_name: str
    performance: Dict[str, float]
    transaction_history: List[Trade]
    agent_decisions: Optional[List[Dict[str, Any]]] = None


class AgentDecision(BaseModel):
    decision: Dict[str, Any]
    reasoning: str
    chain_of_thought: Optional[str] = None


class NewsRequest(BaseModel):
    sources: List[str] = ["caixin", "tiantian", "sinafinance", "tencent"]
    top_rank: int = 10
    pre_k_days: int = 1
