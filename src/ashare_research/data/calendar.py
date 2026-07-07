from __future__ import annotations

from pathlib import Path

import pandas as pd

from ashare_research.contracts.schemas import TRADING_CALENDAR_SOURCE_SCHEMA
from ashare_research.contracts.validation import (
    validate_columns_not_null,
    validate_non_empty_frame,
    validate_required_columns,
)


def load_trading_calendar(path: str | Path) -> pd.DatetimeIndex:
    """Load a trading calendar CSV with a `date` column."""
    calendar_path = Path(path)
    calendar = pd.read_csv(calendar_path, parse_dates=["date"])
    calendar["date"] = pd.to_datetime(calendar["date"], errors="coerce")
    validate_required_columns(calendar, TRADING_CALENDAR_SOURCE_SCHEMA)
    validate_non_empty_frame(calendar, TRADING_CALENDAR_SOURCE_SCHEMA)
    validate_columns_not_null(calendar, TRADING_CALENDAR_SOURCE_SCHEMA, ["date"])
    dates = pd.DatetimeIndex(calendar["date"].drop_duplicates().sort_values())
    return dates


def infer_trading_calendar(bars: pd.DataFrame) -> pd.DatetimeIndex:
    """Infer a trading calendar from available bar data."""
    if "date" not in bars.columns:
        raise ValueError("Bars are missing a date column.")
    dates = pd.DatetimeIndex(
        pd.to_datetime(bars["date"], errors="raise").drop_duplicates().sort_values()
    )
    if dates.empty:
        raise ValueError("Bars do not contain any trading dates.")
    return dates
