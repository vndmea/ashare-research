from __future__ import annotations

import pandas as pd


def moving_average(
    bars: pd.DataFrame,
    window: int,
    price_column: str = "close",
) -> pd.Series:
    """Calculate per-symbol rolling moving averages."""
    if window <= 0:
        raise ValueError("window must be positive")

    return (
        bars.sort_values(["symbol", "date"])
        .groupby("symbol", sort=False)[price_column]
        .transform(lambda series: series.rolling(window=window, min_periods=window).mean())
    )
