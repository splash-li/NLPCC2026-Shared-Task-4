# Dataset & DataLoader

`NLPCC_tasks/dataset/` 提供比赛所需的价格数据、新闻数据与本地 DataLoader。

## 目录结构

- `price_data/export_data/`
  - 候选 ETF / 指数的日频价格数据
- `news_data/export_data/`
  - 每日财经热榜新闻数据
- `dataloader_eval.py`
  - 供本地评测或离线实验使用的 DataLoader
- `price_data/price_normalizer.py`
  - 统一价格口径的辅助逻辑

## 价格数据规则

- 主价格列 `preclose/open/high/low/close/change/pctchange` 表示项目默认使用的有效价格。
- 如果某只资产有后复权价格，DataLoader 默认优先使用后复权价格。
- 如果某个资产没有复权价格，DataLoader 自动回退到原始价格。
- 对有复权数据的文件，还会保留这些辅助列：
  - `adj_preclose/adj_open/adj_high/adj_low/adj_close/adj_factor`
  - `raw_preclose/raw_open/raw_high/raw_low/raw_close/raw_change/raw_pctchange`
  - `price_mode`

## 新闻数据规则

- 数据来自公开可获取的主流财经平台热榜。
- 当前公开包中主要包含：
  - `caixin`
  - `sinafinance`
  - `tencent`
  - `tiantian`
- DataLoader 会按 `RANKING` 截取前 `N` 条热点新闻。

## 新闻 DataLoader 逻辑

新闻读取主逻辑在：

- [server_platform/app/core/data_loader.py](../server_platform/app/core/data_loader.py)
- [dataloader_eval.py](dataloader_eval.py)

核心流程如下：

1. 根据新闻源名称定位对应 CSV 文件
   - 例如 `caixin` 会读取 `caixin_daily_dedup.csv`
2. 读取并缓存整张新闻表
   - 关键字段包括 `THEDATE`、`PUBLISH_TIME`、`TITLE`、`CONTENT`、`RANKING`
3. 按交易日窗口截取新闻
   - 从 `current_date` 往前回看 `pre_k_days` 个交易日
4. 对当前决策日做时间截断
   - 仅保留当天 `15:00` 之前发布的新闻
5. 再按 `RANKING <= top_rank` 筛选
6. 最后返回按热度排序后的新闻列表

换句话说，Agent 在某个交易日能看到的新闻，是“截至当天下午 3 点之前，且位于热榜前列的公开新闻”。

## 为什么建议直接使用这套无 leakage DataLoader

我们强烈建议参赛者直接复用当前提供的 DataLoader，而不是自己手写新闻切片逻辑，原因有三点：

1. 它已经显式处理了未来信息泄露问题
   - 当前交易日只保留 15:00 之前的新闻
2. 它已经对交易日窗口做了统一定义
   - 不需要自己处理非交易日、节假日与日期对齐
3. 它和官方回测引擎使用同一套读取逻辑
   - 本地实验与正式评测的输入口径更一致

如果你自己实现新闻读取逻辑，最容易出错的地方通常是：

- 把当天收盘后发布的新闻也喂给了 Agent
- 直接按自然日而不是交易日回看
- 没有统一 `top_rank` 截断规则
- 不同新闻源的过滤方式不一致

## 防未来数据泄露

比赛默认使用的 `DataLoader.get_historical_prices(...)` 采用防泄露设计：

1. 返回过去 `lookback_days - 1` 个交易日的完整行情。
2. 对当前决策日，仅返回当日开盘价。
3. 隐藏当前决策日收盘价、最高价、最低价、涨跌幅等未来信息。

新闻侧 `DataLoader.get_news(...)` 的规则是：

1. 按交易日向前回看 `pre_k_days`。
2. 对当前决策日，只保留 15:00 之前发布的新闻。
3. 再按热度排名截断。

因此，从比赛公平性和结果可复现性角度，推荐直接把这套 `get_news(...)` 作为标准新闻输入接口。

## 常用接口

- `DataLoader.get_trading_dates(start_date, end_date)`
- `DataLoader.get_previous_trading_date(current_date, k=1)`
- `DataLoader.get_price_data(fund_ids, date)`
- `DataLoader.get_historical_prices(fund_ids, current_date, lookback_days)`
- `DataLoader.get_historical_prices_for_funds(fund_ids, start_date, end_date)`
- `DataLoader.get_benchmark_data(start_date, end_date)`
- `DataLoader.get_news(sources, current_date, top_rank=10, pre_k_days=1)`

## 建议的阅读顺序

如果你想快速理解数据流，建议这样看：

1. 先看 [dataset/README.md](README.md)
2. 再看 [server_platform/app/core/data_loader.py](../server_platform/app/core/data_loader.py)
3. 然后看 [server_platform/app/core/backtest.py](../server_platform/app/core/backtest.py)

这样最容易看明白：

- 数据文件长什么样
- 每天给 Agent 的输入长什么样
- 回测引擎如何消化 Agent 的交易决策

## 本地测试

在 `NLPCC_tasks` 目录下运行：

```bash
python dataset/dataloader_eval.py
```
