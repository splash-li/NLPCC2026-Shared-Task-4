from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

EFFECTIVE_PRICE_COLUMNS = [
    "preclose",
    "open",
    "high",
    "low",
    "close",
    "change",
    "pctchange",
]

CORE_OUTPUT_COLUMNS = [
    "fund_code",
    "date",
    "currency",
    "preclose",
    "open",
    "high",
    "low",
    "close",
    "change",
    "pctchange",
    "volume",
    "amount",
]


def standardize_price_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    standardized = df.copy()

    has_adjusted_prices = {"adj_preclose", "adj_open", "adj_high", "adj_low", "adj_close"}.issubset(
        standardized.columns
    )

    if has_adjusted_prices:
        for column in EFFECTIVE_PRICE_COLUMNS:
            if column in standardized.columns and f"raw_{column}" not in standardized.columns:
                standardized[f"raw_{column}"] = standardized[column]

        standardized["preclose"] = standardized["adj_preclose"]
        standardized["open"] = standardized["adj_open"]
        standardized["high"] = standardized["adj_high"]
        standardized["low"] = standardized["adj_low"]
        standardized["close"] = standardized["adj_close"]

        standardized["change"] = standardized["close"] - standardized["preclose"]
        with np.errstate(divide="ignore", invalid="ignore"):
            standardized["pctchange"] = np.where(
                standardized["preclose"].astype(float) != 0,
                standardized["change"] / standardized["preclose"] * 100,
                np.nan,
            )

    standardized["price_mode"] = "adj" if has_adjusted_prices else "raw"
    return standardized


def reorder_price_columns(columns: Iterable[str]) -> list[str]:
    ordered = [column for column in CORE_OUTPUT_COLUMNS if column in columns]
    extras = [column for column in columns if column not in ordered]
    return ordered + extras


def load_standardized_price_csv(file_path: str | Path, **read_csv_kwargs) -> pd.DataFrame:
    df = pd.read_csv(file_path, **read_csv_kwargs)
    return standardize_price_dataframe(df)
