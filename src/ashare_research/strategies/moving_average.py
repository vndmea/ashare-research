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
    raw_strength = data["fast_ma"].div(data["slow_ma"]).sub(1.0)
    raw_signal = (raw_strength > 0.0).astype(float)
    data["signal"] = raw_signal.groupby(data["symbol"], sort=False).shift(1).fillna(0.0)
    data["signal_strength"] = raw_strength.groupby(data["symbol"], sort=False).shift(1).fillna(0.0)
    data["signal_strength"] = data["signal_strength"].clip(lower=0.0)
    return (
        data[["date", "symbol", "signal", "signal_strength"]]
        .sort_values(["date", "symbol"])
        .reset_index(drop=True)
    )
