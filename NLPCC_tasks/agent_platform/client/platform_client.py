import json
import os
import sys
from typing import Dict, List

import requests

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from logs import agent_logger as logger
from server_platform.app.models.backtest import AgentDecision


class PlatformClient:
    def __init__(self, base_url):
        self.base_url = base_url
        self.token = None

    def _request(self, method: str, endpoint: str, **kwargs):
        """Centralized request function with logging."""
        url = f"{self.base_url}{endpoint}"
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}

        logger.debug(f"Sending {method.upper()} request to {url}")
        if "json" in kwargs:
            logger.trace(f"Request body: {json.dumps(kwargs['json'], indent=2)}")

        try:
            response = requests.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            logger.debug(f"Received successful response from {url} (Status: {response.status_code})")
            return response.json()
        except requests.exceptions.HTTPError as err:
            logger.error(
                f"HTTP error for {method.upper()} {url}: {err.response.status_code} - {err.response.text}"
            )
            raise
        except requests.exceptions.RequestException as err:
            logger.critical(f"Request failed for {method.upper()} {url}: {err}")
            raise

    def register(self, username, password):
        logger.info(f"Registering user '{username}'...")
        try:
            response = self._request(
                "post", "/api/agents/register", json={"username": username, "password": password}
            )

            # 检查响应状态
            if response.get("status") == "existing_user_authenticated":
                logger.info(f"User '{username}' already exists and password verified, attempting login...")
                # 用户已存在且密码正确，自动登录
                return self.login(username, password)
            elif response.get("status") == "new_user_created":
                logger.info(f"New user '{username}' created successfully, attempting login...")
                # 新用户创建成功，自动登录
                return self.login(username, password)
            else:
                # 兼容旧版本的响应格式
                logger.info(f"User '{username}' registration successful, attempting login...")
                return self.login(username, password)

        except Exception as e:
            logger.error(f"Registration failed for user '{username}': {e}")
            # 如果注册失败，尝试验证是否是用户已存在的情况
            try:
                logger.info(f"Attempting to login with existing credentials for user '{username}'...")
                return self.login(username, password)
            except Exception as login_e:
                logger.error(f"Login also failed for user '{username}': {login_e}")
                raise e

    def login(self, username, password):
        logger.info(f"Logging in user '{username}'...")
        # Login uses form data, so we handle it specially
        url = f"{self.base_url}/api/agents/token"
        data = {"username": username, "password": password}
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        response = requests.post(url, data=data, headers=headers)
        response.raise_for_status()
        self.token = response.json().get("access_token")
        logger.info(f"Successfully logged in and received token for user '{username}'.")
        return self.token

    def start_backtest(self, config):
        return self._request("post", "/api/backtest/start", json=config)

    def resume_backtest(self, config, saved_data):
        """从已保存的数据恢复 backtest session"""
        payload = {"config": config, "saved_data": saved_data}
        return self._request("post", "/api/backtest/resume", json=payload)

    def submit_trade_with_decision(self, session_id, trades: List[Dict], agent_decision: AgentDecision):
        # 确保 AgentDecision 对象被正确序列化
        agent_decision_dict = agent_decision.dict() if hasattr(agent_decision, 'dict') else agent_decision
        payload = {"trades": trades, "agent_decision": agent_decision_dict}
        return self._request("post", f"/api/backtest/{session_id}/trade", json=payload)

    def get_backtest_status(self, session_id):
        return self._request("get", f"/api/backtest/{session_id}/status")

    def get_next_day_data(self, session_id):
        return self._request("get", f"/api/backtest/{session_id}/next_day")

    def get_news_data(self, session_id, sources: List[str] = None, top_rank: int = 10, pre_k_days: int = 1):
        data = {
            "sources": sources or ["caixin", "tiantian", "sinafinance", "tencent"],
            "top_rank": top_rank,
            "pre_k_days": pre_k_days,
        }
        return self._request("post", f"/api/backtest/{session_id}/news", json=data)

    def get_market_data(self, session_id):
        return self._request("get", f"/api/backtest/{session_id}/market_data")

    def get_historical_prices(self, session_id, lookback_days: int = 1):
        params = {"lookback_days": lookback_days}
        return self._request("get", f"/api/backtest/{session_id}/historical_prices", params=params)

    def get_agent_decisions(self, session_id):
        return self._request("get", f"/api/backtest/{session_id}/decisions")

    def get_backtest_results(self, session_id):
        return self._request("get", f"/api/backtest/results/{session_id}")

    def get_day_data_resume(self, session_id):
        """获取当前交易日的数据（用于断点续传）"""
        return self._request("get", f"/api/backtest/{session_id}/day_data")

    def get_fund_info(self):
        return self._request("get", "/api/funds/funds")
