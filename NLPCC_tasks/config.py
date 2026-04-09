# -*- coding: utf-8 -*-
from pathlib import Path

# --- General Settings ---
PROJECT_ROOT = Path(__file__).parent

# --- Agent Platform Settings ---
AGENT_PLATFORM = {
    "BASE_URL": "http://localhost:6207",
    "AGENT_USERNAME": "llm_agent",
    "AGENT_PASSWORD": "password",
}

# --- Server Platform Settings ---
SERVER_PLATFORM = {
    "HOST": "0.0.0.0",
    "PORT": 6207,
    "RELOAD": False,
}

# --- Data Directories ---
DATA_DIRS = {
    "PRICE_DATA": PROJECT_ROOT / "dataset" / "price_data" / "export_data",
    "NEWS_DATA": PROJECT_ROOT / "dataset" / "news_data" / "export_data",
}

# --- Logging Settings ---
LOGGING = {
    "LOG_DIR": PROJECT_ROOT / "logs",
    "SERVER_LOG_FILE": "server_platform.log",
    "AGENT_LOG_FILE": "agent_platform.log",
    "LEVEL": "INFO",
    # "ROTATION": "10 MB",
    # "RETENTION": "7 days",
}

# --- Backtest Default Settings ---
BACKTEST_DEFAULTS = {
    "start_date": "2025-01-02",
    "end_date": "2025-01-31",
    "initial_capital": 100000,
    "fund_pool": ["000300.SH", "000905.SH", "399006.SZ", "000688.SH"],
    "agents": [
        {"name": "default_agent", "prompt": "Make investment decisions based on market data and news."}
    ],
    "news_sources": ["caixin", "tiantian", "sinafinance", "tencent"],
    "top_rank": 10,
    "pre_k_days": 1,
    "risk_free_rate": 0.0,  # Annual risk-free rate, default 0
}
