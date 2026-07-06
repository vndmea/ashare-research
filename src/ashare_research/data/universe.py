from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_universe_snapshot(path: str | Path) -> pd.DataFrame:
    """Load a date-aware universe snapshot with `date` and `symbol` columns."""
    snapshot_path = Path(path)
    snapshot = pd.read_csv(snapshot_path, parse_dates=["date"])
    required = {"date", "symbol"}
    missing = required.difference(snapshot.columns)
    if missing:
        raise ValueError(f"Universe snapshot is missing required columns: {sorted(missing)}")
    snapshot = snapshot[["date", "symbol"]].drop_duplicates().sort_values(["date", "symbol"])
    if snapshot.empty:
        raise ValueError("Universe snapshot is empty.")
    return snapshot.reset_index(drop=True)


def universe_from_bars(bars: pd.DataFrame) -> pd.DataFrame:
    """Infer a daily universe snapshot from the symbols present in the bar data."""
    required = {"date", "symbol"}
    missing = required.difference(bars.columns)
    if missing:
        raise ValueError(
            f"Bars are missing required columns for universe inference: {sorted(missing)}"
        )

    snapshot = bars[["date", "symbol"]].drop_duplicates().sort_values(["date", "symbol"])
    if snapshot.empty:
        raise ValueError("Bars do not contain any universe rows.")
    return snapshot.reset_index(drop=True)
