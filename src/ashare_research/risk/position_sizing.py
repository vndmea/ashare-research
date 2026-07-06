from __future__ import annotations

import pandas as pd


def equal_weight_positions(signals: pd.DataFrame, max_names: int = 20) -> pd.DataFrame:
    """Convert positive signals into equal-weight daily target weights."""
    if max_names <= 0:
        raise ValueError("max_names must be positive")

    selected = signals[signals["signal"] > 0].sort_values(["date", "symbol"]).copy()
    selected["rank"] = selected.groupby("date").cumcount() + 1
    selected = selected[selected["rank"] <= max_names]

    selected["weight"] = 1.0 / selected.groupby("date")["symbol"].transform("count")
    weights = selected[["date", "symbol", "weight"]]
    return weights.sort_values(["date", "symbol"]).reset_index(drop=True)
