import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from .data_loader import get_data_loader
from .fund_info import FUND_INFO

# In-memory store for backtest sessions
backtest_sessions = {}

from logs import server_logger as logger

# default dir:
RESULTS_DIR = Path(__file__).parent.parent.parent / "backtest_results_industry_2024_topx"
RESULTS_DIR.mkdir(exist_ok=True)


# Cache to track loaded directories and files modification times
# Key: directory_path, Value: (last_modified_time, list_of_files)
LOADED_DIRS_CACHE = {}


def _discover_results_dirs(base_dir: Path) -> List[Path]:
    """Discover result directories only from the active exp_logs location."""
    candidates: List[Path] = []

    search_roots = [
        base_dir / "exp_logs",
    ]

    for root in search_roots:
        if not root.exists() or not root.is_dir():
            continue
        candidates.extend(d for d in root.glob("backtest_results*") if d.is_dir())

    # De-duplicate while preserving deterministic order
    unique_dirs = sorted({path.resolve(): path for path in candidates}.values(), key=lambda p: str(p))
    return unique_dirs


def load_historical_sessions(force_reload=False):
    """
    Load completed backtest sessions from JSON files across all
    'backtest_results*' directories.
    """
    base_dir = Path(__file__).parent.parent.parent
    logger.info(
        f"Loading historical backtest sessions from directories matching 'backtest_results*' in {base_dir}..."
    )

    results_dirs = _discover_results_dirs(base_dir)

    if not results_dirs:
        logger.warning(f"No 'backtest_results*' directories found under {base_dir}.")
        return

    for results_dir in results_dirs:
        current_mtime = results_dir.stat().st_mtime
        should_reload = (
            force_reload
            or (results_dir not in LOADED_DIRS_CACHE)
            or (LOADED_DIRS_CACHE[results_dir] != current_mtime)
        )

        if not should_reload:
            logger.debug(f"Skipping loading files for directory: {results_dir}")
        else:
            logger.info(f"Scanning directory: {results_dir}")
            count = 0
            for filepath in results_dir.glob("*.json"):
                try:
                    session_id_from_filename = filepath.stem
                    if not force_reload and session_id_from_filename in backtest_sessions:
                        # Skip if already in memory
                        pass
                    else:
                        with open(filepath, "r", encoding="utf-8") as f:
                            data = json.load(f)

                        session_id = data.get("session_id")
                        if not session_id:
                            logger.warning(f"Skipping file {filepath.name} due to missing session_id.")
                            continue

                        # Create a mock session object to hold the results
                        mock_session = BacktestSession(session_id, data.get("backtest_config", {}))
                        mock_session.is_finished = True
                        mock_session.results = data.get("results")

                        backtest_sessions[session_id] = mock_session
                        count += 1
                except json.JSONDecodeError:
                    logger.error(f"Failed to decode JSON from {filepath.name}.")
                except Exception as e:
                    logger.error(f"Failed to load session from {filepath.name}: {e}")

            logger.info(f"Loaded {count} sessions from {results_dir.name}")
            LOADED_DIRS_CACHE[results_dir] = current_mtime


def load_session_by_id(session_id: str):
    """Load a specific backtest session by ID."""
    if session_id in backtest_sessions:
        return backtest_sessions[session_id]

    base_dir = Path(__file__).parent.parent.parent
    results_dirs = _discover_results_dirs(base_dir)

    for results_dir in results_dirs:
        filepath = results_dir / f"{session_id}.json"
        if filepath.exists():
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Create a mock session object
                mock_session = BacktestSession(session_id, data.get("backtest_config", {}))
                mock_session.is_finished = True
                mock_session.results = data.get("results")

                backtest_sessions[session_id] = mock_session
                logger.info(f"Loaded session: {session_id} from {filepath}")
                return mock_session
            except Exception as e:
                logger.error(f"Failed to load session {session_id} from {filepath}: {e}")
                return None

    logger.warning(f"Session {session_id} not found in any results directory.")
    return None


def create_backtest_session(config):
    session_id = str(uuid.uuid4())
    session = BacktestSession(session_id, config)
    backtest_sessions[session_id] = session
    return session_id


def create_backtest_session_with_restore(session_id, config, saved_data):
    """创建一个新的 backtest session 并恢复之前的持仓状态
    
    Args:
        session_id: 新的 session_id
        config: 回测配置
        saved_data: 从 JSON 文件加载的已保存数据
    """
    session = BacktestSession(session_id, config)
    
    # 恢复持仓状态
    if saved_data:
        # 恢复资金
        if "capital" in saved_data:
            session.capital = saved_data["capital"]
        
        # 恢复持仓
        if "portfolio" in saved_data:
            for fund_id, value in saved_data["portfolio"].items():
                if fund_id in session.portfolio:
                    session.portfolio[fund_id] = value
        
        # 恢复已完成日期的快照
        if "daily_portfolio_snapshots" in saved_data:
            session.daily_portfolio_snapshots = saved_data["daily_portfolio_snapshots"]
        
        # 恢复交易历史
        if "transaction_history" in saved_data:
            session.transaction_history = saved_data["transaction_history"]
        
        # 恢复 agent 决策
        if "agent_decisions" in saved_data:
            session.agent_decisions = saved_data["agent_decisions"]
        
        # 恢复投资组合价值历史
        if "portfolio_value_history" in saved_data:
            session.portfolio_value_history = saved_data["portfolio_value_history"]
    
    backtest_sessions[session_id] = session
    return session_id


def get_backtest_session(session_id):
    return backtest_sessions.get(session_id)


def get_all_backtest_sessions():
    return list(backtest_sessions.values())


class BacktestSession:
    def __init__(self, session_id, backtest_config):
        self.session_id = session_id
        self.backtest_config = backtest_config
        self.agent_name = backtest_config.get("agents", [{}])[0].get("name", "unknown_agent")
        logger.info(f"Initializing backtest session '{self.session_id}'.")

        self._data_loader = None
        self.start_date = int(backtest_config["start_date"].replace("-", ""))
        self.end_date = int(backtest_config["end_date"].replace("-", ""))
        self.current_date = self.start_date
        self.initial_capital = backtest_config["initial_capital"]
        self.capital = self.initial_capital

        fund_pool = backtest_config.get("fund_pool")
        if not fund_pool:
            logger.warning("Fund pool is empty, using all available funds.")
            fund_pool = list(FUND_INFO.keys())
            self.backtest_config["fund_pool"] = fund_pool

        # Portfolio now stores the MONETARY VALUE of each holding
        self.portfolio = {fund_id: 0.0 for fund_id in fund_pool}

        self.portfolio_value_history = []
        self.transaction_history = []
        self.agent_decisions = []
        self.is_finished = False
        self.results = None
        self.settled_for_current_date = False
        # 新增：每日持仓快照列表
        self.daily_portfolio_snapshots = []
        logger.info(f"Backtest session initialized with fund pool: {fund_pool}")

    @property
    def data_loader(self):
        if self._data_loader is None:
            self._data_loader = get_data_loader()
        return self._data_loader

    def start(self):
        logger.info(f"Starting backtest session '{self.session_id}' on date {self.current_date}.")
        self.record_portfolio_value()
        return self.get_day_data()

    def _update_holdings_value(self):
        """
        - Updates the value of current holdings based on the day's percentage change.
        - This should be called at the beginning of a new day to reflect the overnight changes.
        """
        market_data = self.get_market_data()
        for fund_id, value in self.portfolio.items():
            if value > 0:
                pct_change = market_data.get(fund_id, {}).get("pct_change")
                if pct_change is not None:
                    self.portfolio[fund_id] *= 1 + pct_change / 100
                    logger.debug(
                        f"Updated {fund_id} value by {pct_change:.2f}%. New value: {self.portfolio[fund_id]:.2f}"
                    )

    def next_day(self):
        logger.debug(f"Advancing to next day for session '{self.session_id}'.")
        if self.current_date >= self.end_date:
            self.finish()
            return None

        if not self.settled_for_current_date:
            self._update_holdings_value()

        trading_dates = self.data_loader.get_trading_dates(self.start_date, self.end_date)
        current_idx = trading_dates.index(self.current_date) if self.current_date in trading_dates else -1

        if current_idx < len(trading_dates) - 1:
            self.current_date = trading_dates[current_idx + 1]
            self.settled_for_current_date = False
            # The portfolio is not updated here to ensure the agent receives the state from the previous day's close
            return self.get_day_data()
        else:
            self.finish()
            return None

    def get_day_data(self):
        # market_data = self.get_market_data()
        market_data = self.data_loader.get_historical_prices(
            fund_ids=self.backtest_config["fund_pool"],
            current_date=self.current_date,
            lookback_days=self.backtest_config.get("pre_k_days", 1),
        )
        news = self.get_news()
        portfolio_status = self.get_portfolio_status()
        self.record_portfolio_value()
        # 记录交易前的持仓快照
        self._record_daily_snapshot(snapshot_type="before_trade")

        return {
            "date": self._format_date(self.current_date),
            "market_data": market_data,
            "news": news,
            "portfolio": portfolio_status,
            "is_finished": self.is_finished,
        }

    def get_market_data(self) -> Dict[str, Dict]:
        return self.data_loader.get_price_data(self.backtest_config["fund_pool"], self.current_date)

    def get_news(self) -> List[Dict]:
        sources = self.backtest_config.get("news_sources", ["caixin", "tiantian", "sinafinance", "tencent"])
        top_rank = self.backtest_config.get("top_rank", 10)
        pre_k_days = self.backtest_config.get("pre_k_days", 1)
        return self.data_loader.get_news(
            sources=sources, current_date=self.current_date, top_rank=top_rank, pre_k_days=pre_k_days
        )

    def get_portfolio_status(self):
        total_holdings_value = sum(self.portfolio.values())
        total_value = self.capital + total_holdings_value

        holdings_with_price = {}
        market_data = self.get_market_data()
        for fund_id, value in self.portfolio.items():
            if value > 1e-6:  # Filter out negligible values
                holdings_with_price[fund_id] = {
                    "value": value,
                    "price": market_data.get(fund_id, {}).get("close"),
                }

        return {
            "date": self._format_date(self.current_date),
            "capital": self.capital,
            "holdings": holdings_with_price,
            "total_value": total_value,
        }

    def submit_trades(self, trades, agent_decision: Optional[Dict] = None):
        logger.info(
            f"Submitting {len(trades)} trades for session '{self.session_id}' on {self.current_date}."
        )

        # First, update the value of existing holdings based on the current day's market changes
        self._update_holdings_value()
        self.settled_for_current_date = True

        # Get the closing prices for the current day to execute trades
        market_data = self.get_market_data()

        # 记录交易执行结果
        trade_execution_results = []

        # not online trading, only day end trading, so buy first, only use cash
        # so only buy first
        buy_trades = [t for t in trades if t.get("action") == "buy"]
        for trade in buy_trades:
            result = self.execute_trade(trade, market_data)
            trade_execution_results.append(result)

        # NO: Process sell orders first to free up capital
        sell_trades = [t for t in trades if t.get("action") == "sell"]
        for trade in sell_trades:
            result = self.execute_trade(trade, market_data)
            trade_execution_results.append(result)

        # 记录交易后的持仓快照
        self._record_daily_snapshot(snapshot_type="after_trade", trades_executed=trade_execution_results)

        if agent_decision:
            self.agent_decisions.append(
                {
                    "date": self._format_date(self.current_date),
                    "decision": agent_decision,
                    "trades_executed": trades,
                    "trade_results": trade_execution_results,  # 记录每笔交易是否成功
                }
            )

        # Do not update holdings value after trading, as it should be based on the next day's closing
        return {
            "portfolio_status": self.get_portfolio_status(),
            "transaction_history": self.transaction_history,
            "trade_execution_results": trade_execution_results,
        }

    def execute_trade(self, trade, market_data):
        """
        执行单笔交易，返回执行结果
        """
        fund_id = trade.get("fund_id")
        action = trade.get("action")
        close_price = market_data.get(fund_id, {}).get("close")

        # 默认结果
        result = {
            "fund_id": fund_id,
            "action": action,
            "success": False,
            "reason": None,
            "amount": trade.get("amount"),
            "percentage": trade.get("percentage"),
        }

        if close_price is None:
            logger.warning(f"No closing price for {fund_id} on {self.current_date}. Skipping trade.")
            result["reason"] = "No closing price available"
            return result

        if action == "buy":
            amount = trade.get("amount")
            if not amount or amount <= 0:
                logger.warning(f"Invalid amount for BUY trade: {amount}. Skipping.")
                result["reason"] = "Invalid amount"
                return result

            if self.capital + 1e-2 >= amount:  # 避免小数点交易失败
                commission = amount * 0.0001
                self.capital -= amount
                # 防止误差累计
                if self.capital < 0:
                    self.capital = 0
                value_added = amount - commission
                self.portfolio[fund_id] = self.portfolio.get(fund_id, 0) + value_added
                self.transaction_history.append(
                    {
                        "fund_id": fund_id,
                        "action": "buy",
                        "amount": amount,
                        "commission": commission,
                        "date": self._format_date(self.current_date),
                    }
                )
                logger.info(
                    f"Executed BUY on {self._format_date(self.current_date)}: "
                    f"Invested {amount:.2f} CNY in {fund_id} at close price {close_price}. "
                    f"Commission: {commission:.2f}. Remaining Capital: {self.capital:.2f}"
                )
                result["success"] = True
                result["commission"] = commission
                result["executed_amount"] = amount
                result["close_price"] = close_price
                return result
            else:
                logger.warning(
                    f"Insufficient capital to BUY {fund_id} for {amount:.2f} CNY. "
                    f"Required: {amount:.2f}, Available: {self.capital:.2f}"
                )
                result["reason"] = f"Insufficient capital. Required: {amount:.2f}, Available: {self.capital:.2f}"
                return result

        elif action == "sell":
            percentage = trade.get("percentage")
            if not percentage or not (0 < percentage <= 1):
                logger.warning(f"Invalid percentage for SELL trade: {percentage}. Skipping.")
                result["reason"] = "Invalid percentage"
                return result

            current_value = self.portfolio.get(fund_id, 0)
            if current_value > 1e-6:
                value_to_sell = current_value * percentage
                commission = value_to_sell * 0.0001

                self.portfolio[fund_id] -= value_to_sell
                self.capital += value_to_sell - commission

                self.transaction_history.append(
                    {
                        "fund_id": fund_id,
                        "action": "sell",
                        "percentage": percentage,
                        "amount_sold": value_to_sell,
                        "commission": commission,
                        "date": self._format_date(self.current_date),
                    }
                )
                logger.info(
                    f"Executed SELL: {percentage*100:.1f}% of {fund_id} (value: {value_to_sell:.2f} CNY). "
                    f"Capital Added: {value_to_sell - commission:.2f}. Remaining Capital: {self.capital:.2f}"
                )
                result["success"] = True
                result["commission"] = commission
                result["sold_value"] = value_to_sell
                result["close_price"] = close_price
                return result
            else:
                logger.warning(f"No holdings of {fund_id} to sell.")
                result["reason"] = "No holdings to sell"
                return result
        
        return result

    def _record_daily_snapshot(self, snapshot_type="before_trade", trades_executed=None):
        """
        记录每天的持仓快照，用于支持断点续传
        
        Args:
            snapshot_type: 快照类型，"before_trade" 或 "after_trade"
            trades_executed: 当天的交易执行结果列表
        """
        market_data = self.get_market_data()
        total_holdings_value = sum(self.portfolio.values())
        total_value = self.capital + total_holdings_value

        # 构建持仓快照
        holdings_snapshot = {}
        for fund_id, value in self.portfolio.items():
            if value > 1e-6:  # 过滤可忽略的小值
                close_price = market_data.get(fund_id, {}).get("close")
                holdings_snapshot[fund_id] = {
                    "value": value,
                    "close_price": close_price,
                }

        snapshot = {
            "date": self._format_date(self.current_date),
            "snapshot_type": snapshot_type,
            "capital": self.capital,
            "holdings": holdings_snapshot,
            "total_value": total_value,
        }
        
        # 如果是交易后的快照，记录交易执行结果
        if snapshot_type == "after_trade" and trades_executed:
            snapshot["trades_executed"] = trades_executed
        
        self.daily_portfolio_snapshots.append(snapshot)

    def record_portfolio_value(self):
        portfolio_status = self.get_portfolio_status()
        self.portfolio_value_history.append(
            {
                "date": self._format_date(self.current_date),
                "value": portfolio_status["total_value"],
                "cash": self.capital,
            }
        )

    def finish(self):
        self.is_finished = True
        logger.info(f"Finishing backtest session '{self.session_id}'.")

        # Update holdings value for the last day to calculate final P/L
        self._update_holdings_value()
        # Record the final portfolio value before finishing
        self.record_portfolio_value()

        if self.portfolio_value_history:
            if self.initial_capital == 0:
                total_return = 0
            else:
                total_return = (
                    self.portfolio_value_history[-1]["value"] - self.initial_capital
                ) / self.initial_capital
            self.results = {
                "performance": {
                    "total_return": total_return,
                    "final_portfolio_value": self.portfolio_value_history[-1]["value"],
                    "annualized_return": self._calculate_annualized_return(),
                },
                "portfolio_value_history": self.portfolio_value_history,
                "transaction_history": self.transaction_history,
                "agent_decisions": self.agent_decisions,
                "daily_portfolio_snapshots": self.daily_portfolio_snapshots,
                "fund_performance": self._calculate_fund_performance(),
            }
            logger.info(
                f"Finishing backtest session '{self.session_id}', result is {self.results['performance']}."
            )
            logger.info(
                f"Visualization for session '{self.session_id}' is available at: http://localhost:6207/backtest_visualization.html?session_id={self.session_id}"
            )
            self._save_results_to_file()

    def _save_results_to_file(self):
        """Saves the backtest results to a JSON file."""
        if not self.results:
            logger.warning(f"No results to save for session '{self.session_id}'.")
            return

        results_dir_name = self.backtest_config.get("results_dir")
        if results_dir_name:
            # explicit config overrides default
            results_dir = Path(__file__).parent.parent.parent / results_dir_name
            results_dir.mkdir(parents=True, exist_ok=True)
        else:
            # use default global RESULTS_DIR
            results_dir = RESULTS_DIR

        file_path = results_dir / f"{self.session_id}.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "session_id": self.session_id,
                        "backtest_config": self.backtest_config,
                        "results": self.results,
                    },
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
            logger.info(f"Successfully saved backtest results to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save results for session '{self.session_id}': {e}")

    def _calculate_annualized_return(self):
        if not self.portfolio_value_history or self.initial_capital == 0:
            return 0

        total_days = len(self.portfolio_value_history)
        if total_days == 0:
            return 0

        total_return = (
            self.portfolio_value_history[-1]["value"] - self.initial_capital
        ) / self.initial_capital
        annualized_return = (1 + total_return) ** (252 / total_days) - 1
        return annualized_return

    def _format_date(self, date_int: int) -> str:
        date_str = str(date_int)
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

    def get_results(self):
        return self.results

    def _calculate_fund_performance(self):
        fund_performance = {}
        fund_pool = self.backtest_config.get("fund_pool", [])
        if not fund_pool:
            return {}

        all_fund_data = self.data_loader.get_historical_prices_for_funds(
            fund_ids=fund_pool, start_date=self.start_date, end_date=self.end_date
        )

        for fund_id, price_data in all_fund_data.items():
            if not price_data:
                continue

            # Sort price data by date to ensure correct calculations
            price_data.sort(key=lambda x: x["date"])
            initial_price = price_data[0].get("close")

            if initial_price is None or initial_price == 0:
                continue

            performance_history = []
            for data_point in price_data:
                current_price = data_point.get("close")
                if current_price is not None:
                    # Normalize the performance based on the initial price
                    normalized_performance = current_price / initial_price
                    performance_history.append({"date": data_point["date"], "value": normalized_performance})

            fund_performance[fund_id] = performance_history

        return fund_performance
