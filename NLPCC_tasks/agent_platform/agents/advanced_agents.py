import asyncio
import json
import os
import re
import sys
from typing import Dict, List

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from loguru import logger

# from luluai.langchain_contrib.chat_models.openai import EFundChatModel

load_dotenv()

# 添加项目根目录到Python路径
# agents/advanced_agents.py 相对于项目根目录的路径是两层 parent (agents -> agent_platform -> 项目根目录)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 此时 project_root = agent_platform 目录
sys.path.insert(0, project_root)

# 直接用缓存的fund info, 也可以通过client get_fund_info实现
from agent_platform.utils import CustomJsonOutputParser

from .fund_info import FUND_INFO
from .trading_strategy_prompt import BASELINE_TRADING_PROMPT, NONEWS_TRADING_PROMPT

# 全局缓存变量
GLOBAL_NEWS_CACHE = {}
# 正在处理中的任务，用于防止重复请求 {cache_key: Future}
PROCESSING_TASKS = {}
# project_root 已经是 agent_platform 目录，所以直接用 project_root 保存 cache
CACHE_FILE_PATH = os.path.join(project_root, "news_summary_cache.json")
CACHE_LOADED = False
SAVE_COUNTER = 0


def load_global_cache():
    global GLOBAL_NEWS_CACHE, CACHE_LOADED
    if CACHE_LOADED:
        return

    if os.path.exists(CACHE_FILE_PATH):
        try:
            with open(CACHE_FILE_PATH, "r", encoding="utf-8") as f:
                GLOBAL_NEWS_CACHE = json.load(f)
            logger.info(f"Loaded {len(GLOBAL_NEWS_CACHE)} items from news cache.")
        except Exception as e:
            logger.warning(f"Failed to load news cache: {e}")
    CACHE_LOADED = True


def _save_cache_sync():
    try:
        # 确保目录存在
        cache_dir = os.path.dirname(CACHE_FILE_PATH)
        if cache_dir and not os.path.exists(cache_dir):
            os.makedirs(cache_dir, exist_ok=True)
            logger.info(f"Created cache directory: {cache_dir}")

        # 使用原子写入：先写临时文件，再重命名
        temp_file = CACHE_FILE_PATH + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(GLOBAL_NEWS_CACHE, f, ensure_ascii=False, indent=2)
        os.replace(temp_file, CACHE_FILE_PATH)
    except Exception as e:
        logger.error(f"Failed to save news cache: {e}")


async def save_global_cache():
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _save_cache_sync)


class NewsProcessingAgent:
    """新闻处理Agent - 负责新闻摘要提取"""

    def __init__(self):
        self.llm = ChatOpenAI(
            base_url=os.getenv("OPENAI_API_BASE"),
            api_key=os.getenv("OPENAI_API_KEY"),
            model="EFundGPT-pro",  # default to light-model
            temperature=0.1,
        )
        load_global_cache()  # avoid duplicate requests to save tokens

    async def extract_news_summary(self, news_item: Dict) -> Dict:
        """提取单条新闻摘要"""
        global SAVE_COUNTER

        # Generate cache key: THEDATE+TITLE+APP_TYPE+RANKING
        cache_key = f"{news_item.get('THEDATE', 'N/A')}_{news_item.get('TITLE', 'N/A')}_{news_item.get('APP_TYPE', 'N/A')}_{news_item.get('RANKING', 'N/A')}"

        # 1. Check Global Cache
        if cache_key in GLOBAL_NEWS_CACHE:
            logger.debug(f"  - [Cache Hit] {cache_key}")
            summary = GLOBAL_NEWS_CACHE[cache_key]
            return self._format_result(news_item, summary)

        # 2. Check if currently processing (In-flight Deduplication)
        if cache_key in PROCESSING_TASKS:
            logger.debug(f"  - [Waiting for In-flight] {cache_key}")
            try:
                # Add timeout to prevent infinite waiting
                summary = await asyncio.wait_for(
                    PROCESSING_TASKS[cache_key], timeout=120
                )
                return self._format_result(news_item, summary)
            except asyncio.TimeoutError:
                logger.warning(f"Timeout waiting for in-flight task: {cache_key}")
                return self._format_result(news_item, "处理超时 (In-flight wait)")
            except Exception as e:
                logger.warning(f"Pending task failed for {cache_key}: {e}")
                return self._format_result(news_item, f"In-flight处理失败: {e}")

        # 3. Create new processing task
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        PROCESSING_TASKS[cache_key] = future

        try:
            prompt = f"""
请将以下金融新闻提取为非常简短的摘要（1-2句话），只保留核心信息：

**原始新闻**:
时间：{news_item.get("THEDATE", "无日期")}
标题: {news_item.get("TITLE", "无标题")}
来源: {news_item.get("APP_TYPE", "未知")}
排名: {news_item.get("RANKING", "N/A")}
内容: {news_item.get("CONTENT", "无内容")}

**要求**:
1. 提取最核心的市场影响信息
2. 用1-2句话概括，非常简短精炼
3. 如果是无关的市场噪音，返回"无关键信息"
4. 只返回摘要内容，不要额外解释

**摘要**:
"""
            # Add retry logic for LLM call
            retry_count = 5
            base_delay = 2
            response = None
            last_error = None

            for i in range(retry_count):
                try:
                    # Add timeout for LLM call
                    response = await asyncio.wait_for(
                        self.llm.ainvoke(prompt), timeout=60
                    )
                    # Validate response
                    if response and hasattr(response, "content") and response.content:
                        break
                    else:
                        logger.warning(
                            f"Empty response from LLM (attempt {i + 1}/{retry_count}) for {cache_key}"
                        )
                        response = None
                except asyncio.TimeoutError:
                    last_error = f"Timeout after 45s"
                    logger.warning(
                        f"News summary timeout (attempt {i + 1}/{retry_count}) for {cache_key}"
                    )
                except Exception as e:
                    last_error = e
                    logger.warning(
                        f"News summary failed (attempt {i + 1}/{retry_count}) for {cache_key}: {e}"
                    )

                if i < retry_count - 1:
                    delay = base_delay * (2**i)  # Exponential backoff
                    await asyncio.sleep(delay)

            if (
                response is None
                or not hasattr(response, "content")
                or response.content is None
            ):
                raise last_error or Exception(
                    "Failed to generate summary after all retries"
                )

            summary = response.content.strip()

            # 清理摘要内容
            summary = re.sub(r'["\']', "", summary)
            if len(summary) > 500:
                summary = summary[:497] + "..."

            logger.debug(f"  - [New Summary] {cache_key}")

            # Update Global Cache
            GLOBAL_NEWS_CACHE[cache_key] = summary

            # Resolve waiting tasks
            if not future.done():
                future.set_result(summary)

            # Periodically save cache (e.g., every 1000 new items)
            SAVE_COUNTER += 1
            if SAVE_COUNTER % 1000 == 0:
                # Fire and forget save to avoid waiting
                asyncio.create_task(save_global_cache())

            return self._format_result(news_item, summary)

        except Exception as e:
            error_msg = str(e)
            logger.error(f"News processing error {cache_key}: {e}")

            # Set exception for waiting tasks
            if not future.done():
                future.set_exception(Exception(error_msg))

            return self._format_result(news_item, f"处理失败: {error_msg[:100]}")

        finally:
            # Cleanup pending task safely
            if cache_key in PROCESSING_TASKS and PROCESSING_TASKS[cache_key] is future:
                del PROCESSING_TASKS[cache_key]

    def _format_result(self, news_item, summary):
        return {
            "thedate": news_item.get("THEDATE", "无日期"),
            "title": news_item.get("TITLE", ""),
            "source": news_item.get("APP_TYPE", ""),
            "ranking": news_item.get("RANKING", 0),
            "summary": summary,
            "original_content": news_item.get("CONTENT", "")[:100] + "...",
        }

    async def process_news_batch(
        self, news_list: List[Dict], max_workers: int = 5
    ) -> List[Dict]:
        """批量处理新闻摘要（并发）"""
        if not news_list:
            return []

        semaphore = asyncio.Semaphore(max_workers)

        async def sem_task(news_item):
            async with semaphore:
                return await self.extract_news_summary(news_item)

        tasks = [sem_task(news_item) for news_item in news_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 过滤处理失败的结果
        processed_news = []
        for result in results:
            if isinstance(result, Dict) and "summary" in result:
                processed_news.append(result)
        return processed_news


class SentimentAnalysisAgent:
    """舆情分析Agent - 负责市场舆情判断"""

    def __init__(
        self,
        model_name="EFundGPT-pro",
    ):
        self.llm = ChatOpenAI(
            base_url=os.getenv("OPENAI_API_BASE"),
            api_key=os.getenv("OPENAI_API_KEY"),
            model=model_name,
            temperature=0.1,
        )
        self.parser = CustomJsonOutputParser()

    async def analyze_sentiment(
        self,
        date_to_decision: str,
        processed_news: List[Dict],
        fund_pool: List[str],
        llm_retry: int = 5,
    ) -> Dict:
        """分析新闻舆情对基金的影响"""
        if not processed_news:
            return {
                "overall_sentiment": "neutral",
                "fund_analysis": {},
                "summary": "无相关新闻信息",
            }

        # 构建基金列表文本
        funds_text = "\n".join(
            [
                f"- {fund} ({FUND_INFO.get(fund, {}).get('name', 'Unknown')}): {FUND_INFO.get(fund, {}).get('scope', 'N/A')}。 ({FUND_INFO.get(fund, {}).get('meaning', 'Unknown')})"
                for fund in fund_pool
            ]
        )

        # 构建处理后的新闻文本
        news_text = "\n\n".join(
            [
                f"{news.get('thedate', '无日期')} 【{news['source']}】排名{news['ranking']}: {news['title']}\n摘要: {news['summary']}"
                for news in processed_news
            ]
        )
        output_formatter = {
            "overall_sentiment": "positive/negative/neutral",
            "fund_analysis": {
                "基金代码": {
                    "sentiment": "positive/negative/neutral",
                    "reason": "简要原因",
                    "confidence": 0.8,
                }
            },
            "summary": "整体市场舆情摘要",
        }

        prompt = f"""
你是一个专业的金融市场舆情分析师。请分析以下新闻对指定投资基金的影响，用于后续生成今日的交易指令，今天是{date_to_decision}：

**可投资基金列表**:
{funds_text}

**处理后的新闻摘要**（共{len(processed_news)}条）:
{news_text}

**分析要求**:
1. 判断新闻对哪些基金可能有正面/负面/中性影响，注意这些新闻并不都是今天，综合时间线，考虑市场的可能的行情
2. 排除完全无关的新闻内容
3. 对每个基金，给出整体的舆情判断（positive/negative/neutral）
4. 提供简要的市场舆情状态和预测，考虑不同天舆情的变化存在的因素
5. 如果没有相关信息，明确说明"无相关信息"

**输出格式**（为严格的JSON）:
{output_formatter}

请给出你的输出：
"""

        try:
            for i in range(llm_retry):
                try:
                    response = await asyncio.wait_for(
                        self.llm.ainvoke(prompt), timeout=120
                    )
                    # logger.debug(f"analyze agent input: {prompt}")
                    # process response
                    analysis = self.parser.parse(response.content)
                    logger.info(f"LLM analysis: {analysis}")
                    return analysis
                except asyncio.TimeoutError:
                    logger.warning(f"LLM call timeout on attempt {i + 1}/{llm_retry}")
                    if i == llm_retry - 1:
                        raise
                except Exception as e:
                    logger.warning(f"Parser failed on attempt {i + 1}/{llm_retry}: {e}")
                    if i == llm_retry - 1:
                        raise e
        except Exception as e:
            logger.error(f"analyze_sentiment failed after {llm_retry} attempts: {e}")
            return {
                "overall_sentiment": "neutral",
                "fund_analysis": {},
                "summary": f"舆情分析失败: {str(e)}",
            }


class TradingStrategyAgent:
    """行情分析Agent - 负责投资决策"""

    def __init__(
        self,
        prompt_template: str = BASELINE_TRADING_PROMPT,
        model_name="",
    ):

        self.llm = ChatOpenAI(
            base_url=os.getenv("OPENAI_API_BASE"),
            api_key=os.getenv("OPENAI_API_KEY"),
            model=model_name,
            temperature=0.1,
        )
        self.parser = CustomJsonOutputParser()
        self.prompt_template = prompt_template
        logger.info(f"decision_model is {model_name}")

    async def make_trading_decision(
        self,
        date_to_decision: str,
        sentiment_analysis: Dict,
        historical_prices: Dict,
        current_portfolio: Dict,
        market_data: Dict,
        fund_pool: List[str],
        trading_history: List[Dict],
        platform_trading_history: List[Dict],
        view_platform_trading_history_days: int = 3,
    ) -> Dict:
        """基于舆情和历史行情做出交易决策"""

        # 构建基金信息文本
        funds_text = "\n".join(
            [
                f"- {fund} ({FUND_INFO.get(fund, {}).get('name', 'Unknown')}): {FUND_INFO.get(fund, {}).get('scope', 'N/A')}。 ({FUND_INFO.get(fund, {}).get('meaning', 'Unknown')})"
                for fund in fund_pool
            ]
        )
        logger.info(f"current_portfolio {current_portfolio}")
        # 格式化持仓信息
        holdings = current_portfolio.get("holdings", {})
        capital = current_portfolio.get("capital", 0)
        # portfolio_date = current_portfolio.get("date", "Unknown")
        holdings_text = "\n".join(
            [
                f"- {fund}: 持仓价值 {details['value']:.2f} 元 (当前价: {details['price']:.2f})"
                for fund, details in holdings.items()
            ]
        )

        # 格式化历史价格数据
        history_text = ""
        for fund, prices in historical_prices.items():
            if prices:
                history_text += f"{fund} 最近{len(prices)}天:\n"
                for price in prices[-4:]:  # 显示最近4天
                    close_price = price.get("close", "N/A")
                    pct_change = price.get("pct_change", "N/A")
                    if close_price is None:
                        close_price = "N/A"
                    if pct_change is None:
                        pct_change = "N/A"
                    else:
                        pct_change = f"{pct_change}%"
                    history_text += f"  {price['date']}: 开{price.get('open', 'N/A')} 收{close_price} 涨跌{pct_change}\n"
                history_text += "\n"

        history_trading = ""
        if platform_trading_history:
            # Group trades by date
            trades_by_date = {}
            for trade in platform_trading_history:
                date = trade.get("date")
                if date not in trades_by_date:
                    trades_by_date[date] = []
                trades_by_date[date].append(trade)

            # Get the last 3 dates with trades
            sorted_dates = sorted(trades_by_date.keys(), reverse=True)
            recent_dates = sorted_dates[:view_platform_trading_history_days]

            # Build the history string, sorted chronologically
            day_trade_strings = []
            for date in sorted(recent_dates):
                trades_for_day = trades_by_date[date]
                trade_lines = []
                for trade in trades_for_day:
                    trade_str = f"{trade.get('date')} {trade.get('fund_id')} {trade.get('action')}"
                    if trade.get("action") == "buy":
                        trade_str += f" amount: {trade.get('amount', 0):.2f}"
                    elif trade.get("action") == "sell":
                        trade_str += f" percentage: {trade.get('percentage', 0):.2%}, amount_sold: {trade.get('amount_sold', 0):.2f}"
                    trade_lines.append(trade_str)
                day_trade_strings.append("\n".join(trade_lines))

            history_trading = "\n\n".join(day_trade_strings)

        prompt = self.prompt_template.format(
            funds_text=funds_text,
            date_to_decision=date_to_decision,
            capital=capital,
            holdings_text=holdings_text if holdings_text else "  (空仓)",
            history_trading=history_trading if history_trading else "  (无历史交易)",
            sentiment_summary=sentiment_analysis.get("summary", "无舆情分析"),
            sentiment_details=json.dumps(
                sentiment_analysis.get("fund_analysis", {}),
                indent=2,
                ensure_ascii=False,
            ),
            history_text=history_text if history_text else "  (无历史价格)",
        )

        try:
            for i in range(5):
                try:
                    # logger.debug(f"trading agent prompt: {prompt}")
                    response = await self.llm.ainvoke(prompt)
                    decision = self.parser.parse(response.content)
                    logger.info(f"LLM Agent decision: {decision}")
                    return decision
                except Exception as e:
                    logger.exception(f"Parser failed on attempt {i + 1}/5: {e}")
                    if i == 4:
                        raise  # OutputParserException already contains LLM output
        except Exception as e:
            logger.error(f"决策生成失败，采取保守策略")
            return {
                "reasoning": "决策生成失败，采取保守策略",
                "chain_of_thought": f"系统错误: {str(e)}",
                "trades": [
                    {"fund_id": fund, "action": "hold", "reason": "系统错误，保守持有"}
                    for fund in holdings.keys()
                ],
                "risk_assessment": "高风险-系统错误",
            }


class AdvancedTradingAgent:
    """高级交易Agent - 协调三个专业Agent"""

    def __init__(
        self,
        agent_id: str,
        trading_prompt_template: str = None,
        decision_model_name="EFundGPT-max",
    ):
        self.agent_id = agent_id
        self.news_agent = NewsProcessingAgent()  # default to small model
        self.sentiment_agent = SentimentAnalysisAgent(model_name=decision_model_name)
        self.trading_agent = TradingStrategyAgent(
            prompt_template=trading_prompt_template or BASELINE_TRADING_PROMPT,
            model_name=decision_model_name,
        )
        self.decision_history = []
        self.trading_history = []
        self.platform_trading_history = []

    async def make_decision(
        self,
        date_to_decision: str,
        news_data: List[Dict],
        historical_prices: Dict,
        current_portfolio: Dict,
        market_data: Dict,
        fund_pool: List[str],
        view_platform_trading_history_days: int = 5,
    ) -> Dict:
        """完整的决策流程"""

        logger.info(f"🤖 {self.agent_id} 开始决策流程...")

        # 1. 新闻处理阶段
        logger.info("📰 新闻处理中...")
        processed_news = await self.news_agent.process_news_batch(news_data)
        logger.info(f"  处理完成: {len(processed_news)}/{len(news_data)} 条新闻")

        # 2. 舆情分析阶段
        logger.info("🎯 舆情分析中...")
        sentiment_analysis = await self.sentiment_agent.analyze_sentiment(
            date_to_decision, processed_news, fund_pool
        )
        logger.info(
            f"  舆情结果: {sentiment_analysis.get('overall_sentiment', 'unknown')}"
        )

        # 3. 交易决策阶段
        logger.info("💹 交易决策中...")
        trading_decision = await self.trading_agent.make_trading_decision(
            date_to_decision,
            sentiment_analysis,
            historical_prices,
            current_portfolio,
            market_data,
            fund_pool,
            self.trading_history,
            self.platform_trading_history,
            view_platform_trading_history_days,
        )
        logger.info(f"  生成 {len(trading_decision.get('trades', []))} 个交易指令")
        logger.info(
            f"  [Model Decision]: {json.dumps(trading_decision, indent=2, ensure_ascii=False)}"
        )

        # 记录决策历史
        decision_record = {
            "date": current_portfolio.get("date", "Unknown"),
            "processed_news_count": len(processed_news),
            "sentiment_analysis": sentiment_analysis,
            "trading_decision": trading_decision,
            "portfolio_value": current_portfolio.get("total_value", 0),
        }
        self.decision_history.append(decision_record)
        self.trading_history.append(
            {
                decision_record["date"]: decision_record["trading_decision"].get(
                    "trades", []
                )
            }
        )
        return {
            "final_decision": trading_decision,
            "intermediate_results": {
                "processed_news": processed_news,
                "sentiment_analysis": sentiment_analysis,
            },
        }

    def get_decision_history(self) -> List[Dict]:
        """获取决策历史"""
        return self.decision_history

    def clear_history(self):
        """清空历史记录"""
        self.decision_history = []


class SillyTradingAgent:
    """无新闻输入的Agent - 仅使用历史数据进行交易决策"""

    def __init__(
        self,
        agent_id: str,
        trading_prompt_template: str = None,
        decision_model_name="EFundGPT-max",
    ):
        self.agent_id = agent_id
        # 使用NONEWS_TRADING_PROMPT模板，忽略新闻数据
        self.trading_agent = TradingStrategyAgent(
            prompt_template=trading_prompt_template or NONEWS_TRADING_PROMPT,
            model_name=decision_model_name,
        )
        self.decision_history = []
        self.trading_history = []
        self.platform_trading_history = []

    async def make_decision(
        self,
        date_to_decision: str,
        news_data: List[Dict],
        historical_prices: Dict,
        current_portfolio: Dict,
        market_data: Dict,
        fund_pool: List[str],
        view_platform_trading_history_days: int = 5,
    ) -> Dict:
        """完整的决策流程 - 忽略新闻数据，仅使用历史价格"""

        logger.info(f"🤖 {self.agent_id} 开始无新闻决策流程...")

        # 跳过新闻处理和舆情分析阶段，直接使用空数据
        sentiment_analysis = {
            "overall_sentiment": "neutral",
            "fund_analysis": {},
            "summary": "无新闻输入，仅基于历史价格分析",
        }

        # 交易决策阶段
        logger.info("💹 基于历史价格的交易决策中...")
        trading_decision = await self.trading_agent.make_trading_decision(
            date_to_decision,
            sentiment_analysis,
            historical_prices,
            current_portfolio,
            market_data,
            fund_pool,
            self.trading_history,
            self.platform_trading_history,
            view_platform_trading_history_days,
        )
        logger.info(f"  生成 {len(trading_decision.get('trades', []))} 个交易指令")
        logger.info(
            f"  [Model Decision]: {json.dumps(trading_decision, indent=2, ensure_ascii=False)}"
        )

        # 记录决策历史
        decision_record = {
            "date": current_portfolio.get("date", "Unknown"),
            "processed_news_count": 0,  # 无新闻处理
            "sentiment_analysis": sentiment_analysis,
            "trading_decision": trading_decision,
            "portfolio_value": current_portfolio.get("total_value", 0),
        }
        self.decision_history.append(decision_record)
        self.trading_history.append(
            {
                decision_record["date"]: decision_record["trading_decision"].get(
                    "trades", []
                )
            }
        )
        return {
            "final_decision": trading_decision,
            "intermediate_results": {
                "processed_news": [],  # 返回空新闻列表
                "sentiment_analysis": sentiment_analysis,
            },
        }

    def get_decision_history(self) -> List[Dict]:
        """获取决策历史"""
        return self.decision_history

    def clear_history(self):
        """清空历史记录"""
        self.decision_history = []


# 全局Agent实例
advanced_agent = None


def get_advanced_agent(
    agent_id: str = "advanced_agent",
    trading_prompt_template: str = None,
    decision_model_name="EFundGPT-max",
) -> AdvancedTradingAgent:
    """获取高级Agent实例 (每次返回新实例以支持并发回测)"""
    # 在并发回测场景下，每个session需要独立的Agent实例来维护自己的history
    return AdvancedTradingAgent(
        agent_id,
        trading_prompt_template=trading_prompt_template,
        decision_model_name=decision_model_name,
    )
