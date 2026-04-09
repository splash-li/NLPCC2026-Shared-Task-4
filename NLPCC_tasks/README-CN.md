# NLPCC 投资智能体竞赛 Starter Kit

[English](README.md)

本目录提供比赛用的最小完整工程，包括：

- 标准化回测服务端
- 公开价格与新闻数据
- 防未来泄露的 DataLoader
- Agent client / demo
- 基础接口与提交说明

其中公开价格与新闻数据将在比赛开始时统一公开。

## 任务介绍

本任务评估基于大语言模型的投资顾问智能体在中国资本市场中的复杂推理与量化决策能力。比赛不再停留于传统文本分析，而是要求参赛者构建能够结合每日宏观信号、行业变化与历史行情信息，进行日频资产配置的智能体。

在标准化回测环境中，Agent 将获得每日 `Top-20` 财经热点新闻和历史价格数据，并需要对给定 ETF 池生成自主调仓指令。所有提交都将在统一的日频回测引擎中进行评估，交易摩擦成本为 `0.01%`。核心挑战在于如何过滤新闻噪声，并在严格避免未来数据泄露的前提下保持稳定的投资逻辑。

## 赛道设置

### Track 1: Macro-Asset Allocation

面向宏观配置能力，围绕约 11 只大类 ETF / 指数进行日频调仓。当前 starter kit 的公开候选池为：

- `000300.SH` 沪深300
- `000905.SH` 中证500
- `399006.SZ` 创业板指
- `000688.SH` 科创50
- `000932.SH` 中证消费
- `000941.SH` 新能源指数
- `399971.SZ` 中证传媒
- `000819.SH` 有色金属指数
- `000928.SH` 中证能源指数
- `000012.SH` 国债指数
- `518880.SH` 黄金ETF

### Track 2: Sector-Rotation Allocation

面向行业轮动能力，围绕行业主题 ETF 进行日频调仓。当前 starter kit 的公开候选池定义在 [fund_info.py](server_platform/app/core/fund_info.py)，默认包括：

- `512880.SH` 证券ETF
- `512800.SH` 银行ETF
- `512070.SH` 保险ETF
- `159995.SZ` 半导体ETF
- `159819.SZ` 人工智能ETF
- `515880.SH` 通信设备ETF
- `159852.SZ` 软件ETF
- `512010.SH` 医药生物ETF
- `512170.SH` 医疗保健ETF
- `159992.SZ` 创新药ETF
- `515170.SH` 食品饮料ETF
- `512690.SH` 白酒ETF
- `512400.SH` 有色金属ETF
- `515220.SH` 煤炭ETF
- `159870.SZ` 化工ETF
- `512200.SH` 房地产ETF

## 数据时间划分

- 公开训练集：`2024-01-01` 到 `2024-12-31`
  - 全量公开，供参赛者构建 Agent
- A 榜测试集：`2025-01-01` 到 `2025-12-31`
  - 全量公开，参赛团队需提交该年度智能体自主每日资产配置日志以及收益结果
- B 榜测试集：`2026-01-01` 到 `2026-06-01`
  - 数据不公开，由组委会统一运行 Agent 并排名

## 回测引擎规则

- 初始模拟资金：`100000` 元
- 交易摩擦成本：买卖均为`0.01%`
- 交易频率：日频
- 撮合价格：对应交易日收盘价；若指数/基金标的有后复权价格，则使用后复权价格，交易摩擦带来的影响较小，用后复权价格计算即可
- 回测场景：模拟购买对应的 ETF 联结基金，无最低交易量限制，日频买卖
- 买入逻辑：按现金金额买入，例如“买入 10000 元黄金 ETF”，买入必须使用当天的现金，当日卖出的金额不能用于当日的买入
- 卖出逻辑：按当前持仓比例卖出，例如“卖出当前黄金持仓的 30%”

## 输入数据

### 1. 新闻输入

- 来源于公开可获取的中国主流财经平台热榜
- 默认包括：
  - 新浪财经
  - 天天基金
  - 腾讯财经
  - 财新
- 比赛主设定是每日 Top-20 热门财经新闻

### 2. 行情输入

- 提供候选 ETF / 指数的日频量价特征
- 主要字段包括：
  - `open`
  - `close`
  - `high`
  - `low`
  - `volume`
  - `pctchange`

更详细的数据与 DataLoader 说明见 [dataset/README.md](dataset/README.md)。

## 防未来数据泄露

比赛引擎的 DataLoader 做了显式防泄露约束：

- 历史价格接口仅返回过去交易日完整数据，以及“当前交易日开盘价”
- 不向 Agent 暴露当前交易日收盘价、最高价、最低价和当日涨跌幅
- 当前交易日新闻只保留 15:00 前发布的内容

因此参赛者无需自己额外做时间切片，但不能在 Agent 中引入外部未来信息。

额外约束：

- 禁止任何形式的未来价格预测或未来价格标签注入行为
- 禁止使用任何在决策时点之后才可获得的数据、指标、人工标注结果或外部信号
- 如果对模型做了训练、微调或检索增强构建，参赛者需要提交完整训练数据、预处理方式、依赖说明与可复现环境
- 对于需要额外环境的方案，需同时提交可执行的 Docker 容器或等价依赖说明，以保证 B 榜可复现测试

## 服务端与接口

主要服务端代码位于：

- [server_platform/app/main.py](server_platform/app/main.py)
- [server_platform/app/api/backtest.py](server_platform/app/api/backtest.py)
- [server_platform/app/core/backtest.py](server_platform/app/core/backtest.py)
- [server_platform/app/core/data_loader.py](server_platform/app/core/data_loader.py)

比赛常用接口：

- `POST /api/backtest/start`
  - 启动一个回测 session
- `POST /api/backtest/resume`
  - 从已保存结果恢复 session
- `POST /api/backtest/{session_id}/trade`
  - 提交交易指令
- `GET /api/backtest/{session_id}/status`
  - 获取当前组合状态
- `GET /api/backtest/{session_id}/next_day`
  - 推进到下一交易日
- `GET /api/backtest/{session_id}/day_data`
  - 获取当前交易日状态，适合断点恢复
- `GET /api/backtest/{session_id}/historical_prices`
  - 获取防泄露历史价格
- `POST /api/backtest/{session_id}/news`
  - 获取新闻
- `GET /api/backtest/results/{session_id}`
  - 获取最终回测结果

## 保存与恢复逻辑

当前 starter kit 已包含这部分能力：

- 每日组合净值保存
- 每日持仓快照保存
- 每日交易执行结果保存
- Agent 决策日志保存
- 断点恢复接口
- 组合时间序列对齐逻辑

这部分逻辑主要在：

- [server_platform/app/core/backtest.py](server_platform/app/core/backtest.py)
- [server_platform/app/api/backtest.py](server_platform/app/api/backtest.py)
- [agent_platform/client/platform_client.py](agent_platform/client/platform_client.py)
- [agent_platform/demo_backtest.py](agent_platform/demo_backtest.py)

## Demo 与运行方式

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 `.env` 与大模型

Agent 侧的 LLM 调用使用 [advanced_agents.py](agent_platform/agents/advanced_agents.py) 中的 `ChatOpenAI`，并通过 `python-dotenv` 自动读取项目根目录下的 `.env`。

当前默认读取的环境变量是：

- `OPENAI_API_BASE`
- `OPENAI_API_KEY`

推荐做法：

1. 复制模板文件：

```bash
cp .env.example .env
```

2. 在 `.env` 中填写你自己的模型服务地址与密钥，例如：

```bash
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_API_KEY=your_api_key_here
```

3. 运行 demo 时通过 `--model` 指定你希望使用的模型名，例如：

```bash
python agent_platform/demo_backtest.py --model gpt-5
```

说明：

- 只要你的服务兼容 OpenAI 风格接口，通常都可以通过这两个环境变量接入。
- 如果你使用的是代理网关、企业中转层或自建兼容服务，只需要把 `OPENAI_API_BASE` 改成对应地址即可。
- 新闻摘要、舆情分析和交易决策目前共用同一组 `.env` 配置。

### 3. 启动服务端

```bash
python start_server.py
```

默认启动地址：

- `http://localhost:6207`

### 4. 运行 demo Agent

```bash
python agent_platform/demo_backtest.py
```

常用参数示例：

```bash
python agent_platform/demo_backtest.py --track macro --model gpt-5 --start-date 2025-01-02 --end-date 2025-03-31
```

## 参赛者建议提交流水

建议至少保留以下产物：

- 每日交易日志
- 每日资产配置 / 持仓日志
- 最终回测结果 JSON
- 模型与 prompt 说明
- 每次模型决策的原始输出
- 可直接执行的代码与运行脚本

A 榜阶段建议提交：

1. Agent 代码或可执行脚本
2. `2025` 年每日交易日志
3. `2025` 年每日资产配置 / 持仓日志
4. `2025` 年每次模型决策的原始输出
5. `2025` 年回测收益结果
6. 必要的运行说明

B 榜阶段由组委会统一在保密数据上运行，因此参赛者必须提交可执行代码与完整依赖，确保可以在统一环境中复现运行。

如果参赛方案包含训练、微调或额外知识构建，需同时提交：

- 全部训练数据及其来源说明
- 数据预处理与构建脚本
- 模型权重或可复现获取方式
- Docker 容器或等价可复现环境说明

## 评价指标

我们会综合考虑夏普比率，并根据不同换手率分类别进行评估。

## 如何读懂这份代码

如果你是第一次看这套比赛工程，建议按下面顺序阅读：

1. 先看 [README-CN.md](README-CN.md)
2. 再看 [dataset/README.md](dataset/README.md)
3. 然后看 [server_platform/app/core/data_loader.py](server_platform/app/core/data_loader.py)
4. 接着看 [server_platform/app/core/backtest.py](server_platform/app/core/backtest.py)
5. 再看 [server_platform/app/api/backtest.py](server_platform/app/api/backtest.py)
6. 然后看 [agent_platform/client/platform_client.py](agent_platform/client/platform_client.py)
7. 最后看 [agent_platform/demo_backtest.py](agent_platform/demo_backtest.py)

样例Agent和接口，重点看：

- [agent_platform/agents/advanced_agents.py](agent_platform/agents/advanced_agents.py)
- [agent_platform/agents/trading_strategy_prompt.py](agent_platform/agents/trading_strategy_prompt.py)

如果你只想保证自己不引入未来信息，最重要的是不要绕开：

- [server_platform/app/core/data_loader.py](server_platform/app/core/data_loader.py)
- [dataset/dataloader_eval.py](dataset/dataloader_eval.py)

建议直接复用这套 DataLoader，而不是自己重新切分价格和新闻数据。

## 目录结构

```text
NLPCC_tasks/
├── agent_platform/      # 参赛者侧 client / agent demo
├── dataset/             # 公开价格与新闻数据
├── server_platform/     # 标准回测引擎与 API
├── config.py
├── logs.py
├── requirements.txt
└── start_server.py
```
