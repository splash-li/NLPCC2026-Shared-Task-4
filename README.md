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

## FAQ

### 1. Is formal registration required for Task 4?

Yes. Formal registration is required for Task 4. Please download the registration form template from:

[http://tcci.ccf.org.cn/conference/2026/shared-tasks/RegistrationForm-Task4.doc](http://tcci.ccf.org.cn/conference/2026/shared-tasks/RegistrationForm-Task4.doc)

After completing the form, please send it to the task contact email.

### 2. Does the May 25, 2026 registration deadline apply to Task 4?

Yes. The registration deadline is May 25, 2026, and it also applies to Task 4. This task follows the official NLPCC shared task schedule.

### 3. Is there an official participant group?

Yes. We maintain an official WeChat group for registered teams. After the organizing committee receives your completed registration form, we will invite your team to join the group.

### 4. Is there a public leaderboard or online submission platform for the A-list evaluation?

There is no public online leaderboard at the moment. The A-list test data has been released for participant-side evaluation, and teams may discuss progress and questions in the official WeChat group.

### 5. What are the A-list and B-list evaluation rules?

The shared task schedule follows the official NLPCC dates page:

[http://tcci.ccf.org.cn/conference/2026/shared-tasks/#dates](http://tcci.ccf.org.cn/conference/2026/shared-tasks/#dates)

Because Task 4 uses both A-list and B-list evaluations, and agent execution may take a long time, we have released the complete A-list data for 20250101-20251231. The B-list test data is not public. The organizing committee will run each team's submitted agent code on the secret B-list dataset to produce the final official ranking.

Models, extra datasets, and knowledge bases used by participating systems must be limited to resources available before 2026.

### 6. What are the submission deadlines?

All participating teams should submit A-list results and full code between June 11 and June 20, 2026. The final B-list ranking will be produced by the organizing committee using the submitted code on the non-public B-list dataset.

### 7. What should participants submit for the final evaluation?

The required final evaluation materials include:

* Full code
* A runnable agent
* A-list prediction files
* Intermediate logs

Detailed packaging and submission instructions will be announced through this repository and the official participant group.

### 8. What does the paper deadline around May 26, 2026 on the conference page or OpenReview refer to?

The paper deadline shown around May 26, 2026 on the conference page or OpenReview is not the deadline for this shared task. The system report and shared task paper schedule for Task 4 will be arranged later, after the evaluation process. Participants do not need to submit Task 4 results, code, system reports, or shared task paper materials by this paper deadline.

### 9. Will there be a system report or shared task paper after the evaluation?

System reports and shared task papers will follow the final publication requirements of the conference. The tentative format is the NLPCC paper template, with no more than two pages per team.

We currently expect the final shared task paper to cover the top three teams in each track, together with selected reports that are creative or especially informative. Inclusion is voluntary for each team and subject to the final conference publication arrangement.

No separate system report deadline has been set yet. Further details will be announced together with the official conference publication process.
