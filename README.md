# NLPCC2026-Shared-Task-4: LLM-based Investment Advisor Agents for Asset Allocation in the Chinese Market

[中文](README-CN.md)

> ⚠️ **IMPORTANT DISCLAIMER**
> 
> **All data, competition materials, and code related to this task are intended for academic research purposes only and do not constitute any form of investment advice.**
## Abstract
This task evaluates the ability of LLM-based Investment Advisor Agents to perform complex reasoning and quantitative decision-making in the Chinese capital market. Moving beyond traditional text analysis, the competition challenges participants to develop agents that interpret daily macroeconomic signals and sectoral shifts to execute daily asset allocation strategies.
Operating in a backtesting environment, agents are provided with a "Top-20 Financial Hot News" feed and historical price data. Agents must autonomously generate daily rebalancing instructions (target weights) for specific ETF pools. All submissions will be evaluated via a standardized daily-frequency backtesting engine with a 0.01% transaction friction cost. The core challenge lies in filtering news noise and maintaining consistent investment logic without "future-data bias."
The competition consists of two tracks:
* Track 1: Macro-Asset Allocation: Evaluates macro-inference capabilities by rebalancing approximately 11 macro-category ETFs (e.g., broad indices, treasury bonds, and gold) to navigate economic cycles.
* Track 2: Sector-Rotation Allocation: Focuses on sensitivity to industrial policies and trends, requiring tactical adjustments across approximately 14 industry-themed ETFs (e.g., New Energy, Semiconductors, and Healthcare).


Performance will be ranked primarily by Sharpe Ratio, alongside cumulative returns and maximum drawdown, to measure risk-adjusted performance in the backtesting scenario. Note: This task and related datasets are intended for academic research only and do not constitute any form of investment advice.

## Timeline and Data Release
* Task Schedule: Please refer to [http://tcci.ccf.org.cn/conference/2026/](http://tcci.ccf.org.cn/conference/2026/shared-tasks/) for the official conference timeline.
* Task Details: Detailed task specifications and starter materials are listed in the `Materials` section below.
* ~Public Data Release: The public price and news dataset will be released when the competition officially begins.~
* Public Data Release: The Dataset, corresponding DataLoader, and Starter Kit are now **officially released**.
## Materials
* **Dataset and DataLoader**: The Dataset, corresponding DataLoader, and Starter Kit are now **officially released**. The datasets are located under the path `NLPCC_tasks/dataset`. We recommend referring to the starter kit for usage guidance.
  *   The full-year data of 2024 is provided as the training set for Agent development.
  *   The 2025 dataset has been released and serves as the Phase A leaderboard.
  *   We will continue collecting 2026 data to construct the non-public Phase B leaderboard subsequently.
* Starter kit guide in Chinese: [NLPCC_tasks/README-CN.md](NLPCC_tasks/README-CN.md)
* Starter kit guide in English: [NLPCC_tasks/README.md](NLPCC_tasks/README.md)



## Awards & Conference Support
* NLPCC & CCF-NLP Certification: The top 1 participating team of each track will be certified by NLPCC and CCF-NLP.
* Workshop Registration Support: One member from each of the top 3 teams of each track who attends the conference in person will receive support for the workshop registration fee.

## Organizer: 
E Fund Management Co., Ltd., Tsinghua University, Peking University, Wuhan University, The Hong Kong University of Science and Technology (Guangzhou), The Hong Kong Polytechnic University

Contact: 
* Shilong Li (lishilong@efunds.com.cn), Jiangpeng Yan (yanjiangpeng@efunds.com.cn)

**Note: This task and related datasets are intended for academic research only and do not constitute any form of investment advice. This dataset is limited to non-commercial academic evaluation and research experiments only. The copyright of all news content is reserved by each original platform. This project shall not be utilized for commercial training, secondary reproduction, or any profit-making activities. Should any copyright objections exist, please contact the project principal for immediate data removal.**
