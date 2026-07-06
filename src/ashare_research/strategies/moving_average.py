from __future__ import annotations

import pandas as pd

from ashare_research.factors.technical import moving_average


def moving_average_crossover_signals(
    bars: pd.DataFrame,
    fast_window: int = 20,
    slow_window: int = 60,
) -> pd.DataFrame:
    """Generate long-only signals where fast MA is above slow MA.

    Signals are shifted by one trading row per symbol to avoid same-close look-ahead bias.
    """
    if fast_window >= slow_window:
        raise ValueError("fast_window must be smaller than slow_window")

    data = bars.sort_values(["symbol", "date"]).copy()
    data["fast_ma"] = moving_average(data, fast_window)
    data["slow_ma"] = moving_average(data, slow_window)
    raw_signal = (data["fast_ma"] > data["slow_ma"]).astype(float)
    data["signal"] = raw_signal.groupby(data["symbol"], sort=False).shift(1).fillna(0.0)
    return data[["date", "symbol", "signal"]].sort_values(["date", "symbol"]).reset_index(drop=True)
