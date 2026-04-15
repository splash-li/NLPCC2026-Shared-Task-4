import bisect
import glob
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

try:
    from dataset.price_data.price_normalizer import load_standardized_price_csv
except ModuleNotFoundError:
    from AgentFundsArena.dataset.price_data.price_normalizer import (
        load_standardized_price_csv,
    )


# Mock logger for evaluation
class MockLogger:
    def info(self, msg):
        print(f"[INFO] {msg}")

    def debug(self, msg):
        print(f"[DEBUG] {msg}")

    def warning(self, msg):
        print(f"[WARNING] {msg}")

    def error(self, msg, exc_info=False):
        print(f"[ERROR] {msg}")


logger = MockLogger()


def _clean_nan_value(value):
    """Convert NaN, inf, -inf values to None for JSON serialization."""
    if value is None:
        return None
    try:
        if pd.isna(value) or np.isinf(value):
            return None
        return value
    except (TypeError, ValueError):
        return value


class DataLoader:
    def __init__(self, price_data_dir: str, news_data_dir: str):
        self.price_data_dir = price_data_dir
        self.news_data_dir = news_data_dir

        # Caching dictionaries
        self.price_data_cache: Dict[str, pd.DataFrame] = {}
        self.news_data_cache: Dict[str, pd.DataFrame] = {}
        self.trading_dates: List[int] = []

        self._load_trading_dates()

    def _load_trading_dates(self):
        """Load the list of trading dates from the HS300 index file."""
        hs300_file = os.path.join(self.price_data_dir, "000300.SH.csv")
        if not os.path.exists(hs300_file):
            hs300_file = os.path.join(self.price_data_dir, "000300.SH_demo.csv")

        if os.path.exists(hs300_file):
            try:
                df = pd.read_csv(hs300_file, usecols=["date"])
                df.replace([np.inf, -np.inf, np.nan], None, inplace=True)
                self.trading_dates = sorted(
                    [int(dt) for dt in df["date"].dropna().unique()]
                )
                logger.info(
                    f"Successfully loaded {len(self.trading_dates)} trading dates."
                )
            except Exception as e:
                logger.error(f"Error loading trading dates from {hs300_file}: {e}")
                self._generate_fallback_trading_dates()
        else:
            self._generate_fallback_trading_dates()

    def _generate_fallback_trading_dates(self):
        """Generate a fallback list of trading dates if the HS300 file is not available."""
        logger.warning(
            "HS300 file not found. Generating fallback trading dates for 2025 H1."
        )
        start_date = datetime(2025, 1, 1)
        end_date = datetime(2026, 1, 1)
        current = start_date
        while current <= end_date:
            if current.weekday() < 5:  # Monday to Friday
                self.trading_dates.append(int(current.strftime("%Y%m%d")))
            current += timedelta(days=1)

    def get_trading_dates(self, start_date: int, end_date: int) -> List[int]:
        """Get trading dates within a specified range."""
        start_idx = bisect.bisect_left(self.trading_dates, start_date)
        end_idx = bisect.bisect_right(self.trading_dates, end_date)
        return self.trading_dates[start_idx:end_idx]

    def get_previous_trading_date(self, current_date: int, k: int = 1) -> int:
        """Get the trading date k days before the current date."""
        try:
            idx = self.trading_dates.index(current_date)
            return self.trading_dates[idx - k] if idx >= k else self.trading_dates[0]
        except ValueError:
            idx = bisect.bisect_left(self.trading_dates, current_date)
            return self.trading_dates[idx - k] if idx >= k else self.trading_dates[0]

    def _get_price_df(self, fund_id: str) -> Optional[pd.DataFrame]:
        """Loads a price CSV into a pandas DataFrame and caches it."""
        if fund_id in self.price_data_cache:
            return self.price_data_cache[fund_id]

        filepath = os.path.join(self.price_data_dir, f"{fund_id}.csv")
        if not os.path.exists(filepath):
            filepath = os.path.join(self.price_data_dir, f"{fund_id}_demo.csv")
            if not os.path.exists(filepath):
                return None

        try:
            df = load_standardized_price_csv(filepath, encoding="utf-8")
            df.set_index("date", inplace=True)
            df.replace([np.inf, -np.inf, np.nan], None, inplace=True)
            self.price_data_cache[fund_id] = df
            logger.debug(f"Cached price data for '{fund_id}'.")
            return df
        except Exception as e:
            logger.error(f"Error loading price data for {fund_id} from {filepath}: {e}")
            return None

    def get_price_data(self, fund_ids: List[str], date: int) -> Dict[str, Dict]:
        """Get price data for multiple funds on a given date."""
        result = {}
        for fund_id in fund_ids:
            df = self._get_price_df(fund_id)
            # print(df.head())
            if df is not None and date in df.index:
                data = df.loc[date]
                result[fund_id] = {
                    "open": _clean_nan_value(data.get("open", 0)),
                    "close": _clean_nan_value(data.get("close", 0)),
                    "change": _clean_nan_value(data.get("change", 0)),
                    "pct_change": _clean_nan_value(data.get("pctchange", 0)),
                    "volume": _clean_nan_value(data.get("volume", 0)),
                }
        return result

    def get_historical_prices(
        self, fund_ids: List[str], current_date: int, lookback_days: int
    ) -> Dict[str, List[Dict]]:
        result = {}
        try:
            current_idx = self.trading_dates.index(current_date)
        except ValueError:
            current_idx = bisect.bisect_left(self.trading_dates, current_date) - 1

        if current_idx < 0:
            for fund_id in fund_ids:
                result[fund_id] = []
            return result

        hist_end_idx = current_idx - 1
        hist_start_idx = max(0, hist_end_idx - (lookback_days - 1) + 1)

        if hist_end_idx >= 0:
            historical_dates = self.trading_dates[hist_start_idx : hist_end_idx + 1]
            for fund_id in fund_ids:
                df = self._get_price_df(fund_id)
                if df is None:
                    result[fund_id] = []
                    continue

                fund_data = df[df.index.isin(historical_dates)].reset_index()
                records = []
                for _, row in fund_data.iterrows():
                    date = int(row["date"])
                    records.append(
                        {
                            "date": datetime.strptime(str(date), "%Y%m%d").strftime(
                                "%Y-%m-%d"
                            ),
                            "date_int": date,
                            "open": _clean_nan_value(row.get("open")),
                            "close": _clean_nan_value(row.get("close")),
                            "high": _clean_nan_value(row.get("high")),
                            "low": _clean_nan_value(row.get("low")),
                            "change": _clean_nan_value(row.get("change")),
                            "pct_change": _clean_nan_value(row.get("pctchange")),
                        }
                    )
                result[fund_id] = records
        else:
            for fund_id in fund_ids:
                result[fund_id] = []

        current_trading_date = self.trading_dates[current_idx]
        for fund_id in fund_ids:
            df = self._get_price_df(fund_id)
            if df is not None and current_trading_date in df.index:
                current_data = df.loc[current_trading_date]
                if fund_id not in result:
                    result[fund_id] = []
                result[fund_id].append(
                    {
                        "date": datetime.strptime(
                            str(current_trading_date), "%Y%m%d"
                        ).strftime("%Y-%m-%d"),
                        "date_int": current_trading_date,
                        "open": _clean_nan_value(current_data.get("open")),
                        "close": None,
                        "high": None,
                        "low": None,
                        "change": None,
                        "pct_change": None,
                    }
                )

        return result

    def get_historical_prices_for_funds(
        self, fund_ids: List[str], start_date: int, end_date: int
    ) -> Dict[str, List[Dict]]:
        result = {}
        trading_dates_in_range = self.get_trading_dates(start_date, end_date)

        for fund_id in fund_ids:
            df = self._get_price_df(fund_id)
            if df is None:
                result[fund_id] = []
                continue

            fund_data = df[df.index.isin(trading_dates_in_range)].reset_index()
            records = []
            for _, row in fund_data.iterrows():
                date = int(row["date"])
                records.append(
                    {
                        "date": datetime.strptime(str(date), "%Y%m%d").strftime(
                            "%Y-%m-%d"
                        ),
                        "open": _clean_nan_value(row.get("open")),
                        "close": _clean_nan_value(row.get("close")),
                        "high": _clean_nan_value(row.get("high")),
                        "low": _clean_nan_value(row.get("low")),
                        "change": _clean_nan_value(row.get("change")),
                        "pct_change": _clean_nan_value(row.get("pctchange")),
                    }
                )
            result[fund_id] = records

        return result

    def get_benchmark_data(self, start_date: int, end_date: int) -> List[Dict]:
        hs300_file = os.path.join(self.price_data_dir, "000300.SH.csv")
        if not os.path.exists(hs300_file):
            hs300_file = os.path.join(self.price_data_dir, "000300.SH_demo.csv")

        if not os.path.exists(hs300_file):
            logger.warning("HS300 benchmark file not found.")
            return []

        try:
            df = load_standardized_price_csv(hs300_file, encoding="utf-8")
            df.set_index("date", inplace=True)
            df.replace([np.inf, -np.inf, np.nan], None, inplace=True)
            trading_dates_in_range = self.get_trading_dates(start_date, end_date)
            benchmark_data = df[df.index.isin(trading_dates_in_range)].reset_index()
            records = []
            for _, row in benchmark_data.iterrows():
                date = int(row["date"])
                records.append(
                    {
                        "date": datetime.strptime(str(date), "%Y%m%d").strftime(
                            "%Y-%m-%d"
                        ),
                        "close": _clean_nan_value(row.get("close")),
                    }
                )
            return records
        except Exception as e:
            logger.error(f"Error loading benchmark data from {hs300_file}: {e}")
            return []

    def _get_news_df(self, source: str) -> Optional[pd.DataFrame]:
        source_key = source.lower()
        if source_key in self.news_data_cache:
            return self.news_data_cache[source_key]

        pattern = os.path.join(self.news_data_dir, f"{source_key}_daily_dedup.csv")
        files = glob.glob(pattern)
        print(files)
        if not files:
            filepath = os.path.join(self.news_data_dir, f"{source_key}.csv")
            if not os.path.exists(filepath):
                return None
        else:
            filepath = files[0]

        try:
            df = pd.read_csv(
                filepath, encoding="utf-8", parse_dates=["PUBLISH_TIME", "THEDATE"]
            )
            df.replace([np.inf, -np.inf, np.nan], None, inplace=True)
            df["THEDATE"] = df["THEDATE"].dt.date
            self.news_data_cache[source_key] = df
            logger.debug(f"Cached news data for '{source}'.")
            return df
        except Exception as e:
            logger.error(f"Error loading news data for {source} from {filepath}: {e}")
            return None

    def get_news(
        self,
        sources: List[str],
        current_date: int,
        top_rank: int = 10,
        pre_k_days: int = 1,
    ) -> List[Dict]:
        all_news = []
        try:
            end_date_dt = datetime.strptime(str(current_date), "%Y%m%d").date()
        except:
            return []

        start_trading_date = self.get_previous_trading_date(current_date, k=pre_k_days)
        start_date_dt = datetime.strptime(str(start_trading_date), "%Y%m%d").date()

        for source in sources:
            df = self._get_news_df(source)
            if df is None:
                continue

            mask = (df["THEDATE"] >= start_date_dt) & (df["THEDATE"] <= end_date_dt)
            filtered_df = df[mask].copy()

            if not filtered_df.empty:
                today_mask = filtered_df["THEDATE"] == end_date_dt
                time_mask = filtered_df["PUBLISH_TIME"].dt.hour < 15
                final_mask = ~today_mask | (today_mask & time_mask)
                filtered_df = filtered_df[final_mask]

            filtered_df = filtered_df[filtered_df["RANKING"] <= top_rank]
            news_records = filtered_df.to_dict("records")

            cleaned_news = []
            for record in news_records:
                cleaned_record = {k: _clean_nan_value(v) for k, v in record.items()}
                cleaned_news.append(cleaned_record)

            all_news.extend(cleaned_news)

        all_news.sort(key=lambda x: x.get("RANKING", 999))
        return all_news


def test_dataloader():
    print("=== Testing DataLoader (CSV Version) ===")
    price_dir = "./price_data/export_data"
    print(os.listdir(price_dir))
    news_dir = "./news_data/export_data"

    loader = DataLoader(price_dir, news_dir)

    # 1. Test get_trading_dates
    dates = loader.get_trading_dates(20250101, 20250110)
    print(f"Trading dates (20250101-20250110): {dates[:5]}... (total {len(dates)})")

    # 2. Test get_previous_trading_date
    if loader.trading_dates:
        test_date = loader.trading_dates[min(5, len(loader.trading_dates) - 1)]
        prev_date = loader.get_previous_trading_date(test_date, k=1)
        print(f"Previous trading date of {test_date}: {prev_date}")

    # 3. Test get_price_data
    fund_ids = ["000300.SH"]
    if loader.trading_dates:
        price_info = loader.get_price_data(fund_ids, loader.trading_dates[0])
        print(f"Price data for {fund_ids} on {loader.trading_dates[0]}: {price_info}")

    # 4. Test get_historical_prices
    if loader.trading_dates:
        hist_prices = loader.get_historical_prices(
            fund_ids,
            loader.trading_dates[min(10, len(loader.trading_dates) - 1)],
            lookback_days=3,
        )
        if hist_prices:
            first_key = list(hist_prices.keys())[0]
            print(
                f"Historical prices for {first_key}: Found {len(hist_prices[first_key])} records."
            )
        else:
            print("No historical prices found.")

    # 5. Test get_news
    sources = ["caixin", "tiantian_fund"]
    if loader.trading_dates:
        news = loader.get_news(
            sources,
            loader.trading_dates[min(10, len(loader.trading_dates) - 1)],
            top_rank=5,
        )
        print(f"News: Found {len(news)} items")


if __name__ == "__main__":
    test_dataloader()
