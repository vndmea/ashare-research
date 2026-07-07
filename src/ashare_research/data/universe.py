from __future__ import annotations

from pathlib import Path

import pandas as pd

from ashare_research.contracts.schemas import UNIVERSE_SOURCE_SCHEMA
from ashare_research.contracts.validation import (
    validate_columns_not_null,
    validate_non_empty_frame,
    validate_required_columns,
    validate_string_column_not_blank,
)


def load_universe_snapshot(path: str | Path) -> pd.DataFrame:
    """Load a date-aware universe snapshot with `date` and `symbol` columns."""
    snapshot_path = Path(path)
    snapshot = pd.read_csv(snapshot_path, parse_dates=["date"])
    snapshot["date"] = pd.to_datetime(snapshot["date"], errors="coerce")
    if "symbol" in snapshot.columns:
        snapshot["symbol"] = snapshot["symbol"].astype("string").str.strip()
    validate_required_columns(snapshot, UNIVERSE_SOURCE_SCHEMA)
    validate_non_empty_frame(snapshot, UNIVERSE_SOURCE_SCHEMA)
    validate_columns_not_null(snapshot, UNIVERSE_SOURCE_SCHEMA, ["date", "symbol"])
    validate_string_column_not_blank(snapshot, UNIVERSE_SOURCE_SCHEMA, "symbol")
    snapshot = snapshot[["date", "symbol"]].drop_duplicates().sort_values(["date", "symbol"])
    return snapshot.reset_index(drop=True)


def universe_from_bars(bars: pd.DataFrame) -> pd.DataFrame:
    """Infer a daily universe snapshot from the symbols present in the bar data."""
    validate_required_columns(bars, UNIVERSE_SOURCE_SCHEMA)
    validate_columns_not_null(bars, UNIVERSE_SOURCE_SCHEMA, ["date", "symbol"])
    validate_string_column_not_blank(bars, UNIVERSE_SOURCE_SCHEMA, "symbol")

    snapshot = bars[["date", "symbol"]].drop_duplicates().sort_values(["date", "symbol"])
    if snapshot.empty:
        raise ValueError("Bars do not contain any universe rows.")
    return snapshot.reset_index(drop=True)
