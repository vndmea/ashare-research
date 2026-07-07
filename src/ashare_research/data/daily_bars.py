from __future__ import annotations

from pathlib import Path

import pandas as pd

from ashare_research.contracts.schemas import BARS_SCHEMA, DAILY_BARS_SOURCE_SCHEMA
from ashare_research.data.adjustments import (
    apply_price_adjustment,
    load_adjustment_factors,
    merge_adjustment_factors,
)

REQUIRED_DAILY_BAR_COLUMNS = DAILY_BARS_SOURCE_SCHEMA.required_field_set

OPTIONAL_DAILY_BAR_COLUMNS = BARS_SCHEMA.optional_field_set.difference(
    {"raw_open", "raw_high", "raw_low", "raw_close"}
)

BOOLEAN_DAILY_BAR_COLUMNS = {
    "is_suspended",
    "limit_up",
    "limit_down",
    "tradable",
}

NUMERIC_DAILY_BAR_COLUMNS = {
    "amount",
    "adj_factor",
}


def load_daily_bars(
    path: str | Path,
    start_date: str | None = None,
    end_date: str | None = None,
    price_adjustment: str = "none",
    adjustment_factor_path: str | Path | None = None,
    keep_raw_prices: bool = True,
) -> pd.DataFrame:
    """Load daily OHLCV bars from CSV.

    Expected columns: date, symbol, open, high, low, close, volume.
    Prices should already be adjusted consistently for the intended research question.
    """
    data_path = Path(path)
    bars = pd.read_csv(data_path, parse_dates=["date"])
    bars = coerce_daily_bar_types(bars)
    if adjustment_factor_path is not None:
        factors = load_adjustment_factors(adjustment_factor_path)
        bars = merge_adjustment_factors(bars, factors)
    bars = apply_price_adjustment(
        bars,
        mode=price_adjustment,
        keep_raw_prices=keep_raw_prices,
    )
    validate_daily_bars(bars)

    bars = bars.sort_values(["date", "symbol"]).reset_index(drop=True)
    if start_date is not None:
        bars = bars[bars["date"] >= pd.Timestamp(start_date)]
    if end_date is not None:
        bars = bars[bars["date"] <= pd.Timestamp(end_date)]
    return bars.reset_index(drop=True)


def validate_daily_bars(bars: pd.DataFrame) -> None:
    missing = REQUIRED_DAILY_BAR_COLUMNS.difference(bars.columns)
    if missing:
        raise ValueError(f"Daily bars are missing required columns: {sorted(missing)}")

    if bars.empty:
        raise ValueError("Daily bars are empty.")

    duplicated = bars.duplicated(["date", "symbol"])
    if duplicated.any():
        sample = bars.loc[duplicated, ["date", "symbol"]].head().to_dict("records")
        raise ValueError(f"Daily bars contain duplicate date/symbol rows: {sample}")


def coerce_daily_bar_types(bars: pd.DataFrame) -> pd.DataFrame:
    """Normalize optional market flags and numeric fields when present."""
    data = bars.copy()
    if "date" in data.columns:
        data["date"] = pd.to_datetime(data["date"], errors="raise")
    if "symbol" in data.columns:
        data["symbol"] = data["symbol"].astype("string").str.strip()

    for column in NUMERIC_DAILY_BAR_COLUMNS.intersection(data.columns):
        data[column] = pd.to_numeric(data[column], errors="coerce")

    for column in BOOLEAN_DAILY_BAR_COLUMNS.intersection(data.columns):
        data[column] = _coerce_boolean_series(data[column])

    if "st_status" in data.columns:
        data["st_status"] = data["st_status"].astype("string").fillna("")

    for column in {"industry", "sector"}.intersection(data.columns):
        data[column] = data[column].astype("string").fillna("")

    return data


def _coerce_boolean_series(series: pd.Series) -> pd.Series:
    normalized = series.astype("string").str.strip().str.lower()
    return normalized.isin({"1", "true", "t", "yes", "y", "on"})
