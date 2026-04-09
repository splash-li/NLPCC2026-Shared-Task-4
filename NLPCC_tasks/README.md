# NLPCC Investment Agent Competition Starter Kit

[中文](README-CN.md)

This directory provides a minimal but complete competition starter kit, including:

- a standardized backtesting server
- public price and news datasets
- leakage-safe DataLoader logic
- agent client and demo runner
- API and submission guidance

The public price and news datasets will be officially released at the start of the competition.

## Task Overview

This task evaluates the ability of LLM-based Investment Advisor Agents to perform complex reasoning and quantitative decision-making in the Chinese capital market. Moving beyond traditional text analysis, the competition challenges participants to develop agents that interpret daily macroeconomic signals and sectoral shifts to execute daily asset allocation strategies.

Operating in a backtesting environment, agents are provided with a daily `Top-20 Financial Hot News` feed and historical price data. Agents must autonomously generate daily rebalancing instructions for predefined ETF pools. All submissions are evaluated via a standardized daily-frequency backtesting engine with a `0.01%` transaction friction cost. The core challenge is to filter news noise while maintaining stable investment logic without future-data bias.

## Tracks

### Track 1: Macro-Asset Allocation

This track focuses on macro-level allocation over roughly 11 broad asset ETFs and indices. The public candidate pool in the starter kit is:

- `000300.SH` CSI 300
- `000905.SH` CSI 500
- `399006.SZ` ChiNext Index
- `000688.SH` STAR 50
- `000932.SH` CSI Consumer
- `000941.SH` New Energy Index
- `399971.SZ` CSI Media
- `000819.SH` Nonferrous Metals Index
- `000928.SH` CSI Energy Index
- `000012.SH` Treasury Bond Index
- `518880.SH` Gold ETF

### Track 2: Sector-Rotation Allocation

This track focuses on sector rotation over industry-themed ETFs. The public candidate pool is defined in [fund_info.py](server_platform/app/core/fund_info.py), including:

- `512880.SH` Securities ETF
- `512800.SH` Banking ETF
- `512070.SH` Insurance ETF
- `159995.SZ` Semiconductor ETF
- `159819.SZ` AI ETF
- `515880.SH` Communication Equipment ETF
- `159852.SZ` Software ETF
- `512010.SH` Pharma ETF
- `512170.SH` Healthcare ETF
- `159992.SZ` Innovative Drug ETF
- `515170.SH` Food & Beverage ETF
- `512690.SH` Liquor ETF
- `512400.SH` Nonferrous Metals ETF
- `515220.SH` Coal ETF
- `159870.SZ` Chemicals ETF
- `512200.SH` Real Estate ETF

## Data Split

- Public training set: `2024-01-01` to `2024-12-31`
  - fully public for participants to build and tune agents
- A leaderboard test set: `2025-01-01` to `2025-12-31`
  - fully public; teams submit daily allocation logs and backtest results for this period
- B leaderboard test set: `2026-01-01` to `2026-06-01`
  - kept private and run centrally by the organizers

## Backtest Rules

- Initial capital: `100000` CNY
- Transaction friction cost: `0.01%`
- Trading frequency: daily
- Execution price: closing price of the trading day; backward-adjusted price if available
- Trading abstraction: ETF-linked fund style simulation, with no minimum lot size
- Buy logic: buy by cash amount, for example “buy 10,000 CNY of Gold ETF”
- Sell logic: sell by current holding percentage, for example “sell 30% of current Gold ETF holdings”

## Inputs

### 1. News

- sourced from publicly accessible Chinese financial hot-topic rankings
- default sources include:
  - Sina Finance
  - Tiantian Fund
  - Tencent Finance / Tencent Stock
  - Caixin
- the main competition setting uses daily Top-20 hot financial news

### 2. Market Data

- daily OHLCV-style signals for candidate ETFs / indices
- major fields include:
  - `open`
  - `close`
  - `high`
  - `low`
  - `volume`
  - `pctchange`

For more detail, see [dataset/README.md](dataset/README.md).

## No Future Leakage

The official DataLoader enforces explicit anti-leakage rules:

- historical price APIs return full history for previous trading days, plus only the current-day open
- the current day close, high, low, and return are hidden from the agent
- same-day news is truncated to items published before 15:00

Participants are strongly encouraged to reuse this DataLoader rather than implementing their own slicing logic.

Additional constraints:

- Any future-price forecasting behavior or future-price label injection is prohibited
- Participants must not use any data, features, labels, or external signals that would only become available after the decision timestamp
- If a submission uses training, fine-tuning, or retrieval/index construction, the team must submit the full training data, preprocessing pipeline, dependency specification, and enough materials for reproducibility
- If extra runtime dependencies are required, participants must also provide an executable Docker container or an equivalent reproducible environment for B leaderboard evaluation

## Server and APIs

Main server-side files:

- [server_platform/app/main.py](server_platform/app/main.py)
- [server_platform/app/api/backtest.py](server_platform/app/api/backtest.py)
- [server_platform/app/core/backtest.py](server_platform/app/core/backtest.py)
- [server_platform/app/core/data_loader.py](server_platform/app/core/data_loader.py)

Common competition APIs:

- `POST /api/backtest/start`
- `POST /api/backtest/resume`
- `POST /api/backtest/{session_id}/trade`
- `GET /api/backtest/{session_id}/status`
- `GET /api/backtest/{session_id}/next_day`
- `GET /api/backtest/{session_id}/day_data`
- `GET /api/backtest/{session_id}/historical_prices`
- `POST /api/backtest/{session_id}/news`
- `GET /api/backtest/results/{session_id}`

## Save / Restore Logic

The current starter kit already includes:

- daily portfolio value persistence
- daily holdings snapshot persistence
- daily trade execution records
- agent decision logs
- resume-from-saved-state APIs
- portfolio history alignment logic

The core implementation lives in:

- [server_platform/app/core/backtest.py](server_platform/app/core/backtest.py)
- [server_platform/app/api/backtest.py](server_platform/app/api/backtest.py)
- [agent_platform/client/platform_client.py](agent_platform/client/platform_client.py)
- [agent_platform/demo_backtest.py](agent_platform/demo_backtest.py)

## Demo and Usage

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure `.env` and LLM Access

The agent-side LLM calls are implemented in [advanced_agents.py](agent_platform/agents/advanced_agents.py) via `ChatOpenAI`, and `python-dotenv` loads settings from the project-root `.env`.

Required environment variables:

- `OPENAI_API_BASE`
- `OPENAI_API_KEY`

Recommended setup:

1. Copy the template:

```bash
cp .env.example .env
```

2. Fill in your endpoint and key:

```bash
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_API_KEY=your_api_key_here
```

3. Select the model at runtime:

```bash
python agent_platform/demo_backtest.py --model gpt-5
```

Notes:

- Any OpenAI-compatible endpoint should work in most cases.
- If you use a gateway, proxy, or self-hosted compatible service, simply change `OPENAI_API_BASE`.
- News summarization, sentiment analysis, and trading decision modules currently share the same `.env` configuration.

### 3. Start the Server

```bash
python start_server.py
```

Default address:

- `http://localhost:6207`

### 4. Run the Demo Agent

```bash
python agent_platform/demo_backtest.py
```

Example:

```bash
python agent_platform/demo_backtest.py --track macro --model gpt-5 --start-date 2025-01-02 --end-date 2025-03-31
```

## Suggested Submission Outputs

Teams are encouraged to keep at least:

- daily trade logs
- daily allocation / holdings logs
- final backtest result JSON
- model and prompt documentation
- raw model outputs for each decision step
- executable code and run scripts

For the A leaderboard stage, suggested submission contents are:

1. agent code or executable script
2. daily trade logs for `2025`
3. daily allocation / holdings logs for `2025`
4. raw model outputs for each decision in `2025`
5. backtest results for `2025`
6. clear run instructions

The B leaderboard stage is run centrally by the organizers on the private set, so each team must submit executable code and complete runtime dependencies for reproducible execution.

If the submission includes training, fine-tuning, or additional knowledge construction, teams must also provide:

- the full training data and data-source description
- preprocessing and build scripts
- model weights or a reproducible way to obtain them
- a Docker container or an equivalent reproducible environment description

## Evaluation

We will evaluate submissions by jointly considering Sharpe ratio, with separate evaluation categories under different turnover levels.

## How To Read the Codebase

If you are new to this starter kit, the recommended reading order is:

1. [README.md](README.md)
2. [dataset/README.md](dataset/README.md)
3. [server_platform/app/core/data_loader.py](server_platform/app/core/data_loader.py)
4. [server_platform/app/core/backtest.py](server_platform/app/core/backtest.py)
5. [server_platform/app/api/backtest.py](server_platform/app/api/backtest.py)
6. [agent_platform/client/platform_client.py](agent_platform/client/platform_client.py)
7. [agent_platform/demo_backtest.py](agent_platform/demo_backtest.py)

If you want to modify the agent strategy itself, start with:

- [agent_platform/agents/advanced_agents.py](agent_platform/agents/advanced_agents.py)
- [agent_platform/agents/trading_strategy_prompt.py](agent_platform/agents/trading_strategy_prompt.py)

If your priority is avoiding leakage, do not bypass:

- [server_platform/app/core/data_loader.py](server_platform/app/core/data_loader.py)
- [dataset/dataloader_eval.py](dataset/dataloader_eval.py)

## Repository Layout

```text
NLPCC_tasks/
├── agent_platform/      # participant-side client and demo agent
├── dataset/             # public price and news data
├── server_platform/     # official backtest engine and APIs
├── config.py
├── logs.py
├── requirements.txt
└── start_server.py
```
