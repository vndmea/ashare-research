from __future__ import annotations

from pathlib import Path

import pandas as pd

from ashare_research.contracts.schemas import TRADING_CALENDAR_SOURCE_SCHEMA


def load_trading_calendar(path: str | Path) -> pd.DatetimeIndex:
    """Load a trading calendar CSV with a `date` column."""
    calendar_path = Path(path)
    calendar = pd.read_csv(calendar_path, parse_dates=["date"])
    if "date" not in TRADING_CALENDAR_SOURCE_SCHEMA.required_field_set.intersection(calendar.columns):
        raise ValueError("Trading calendar is missing a date column.")
    dates = pd.DatetimeIndex(calendar["date"].drop_duplicates().sort_values())
    if dates.empty:
        raise ValueError("Trading calendar is empty.")
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
