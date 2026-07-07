from __future__ import annotations

import pandas as pd

from ashare_research.strategies.registry import registry


def relative_strength_signals(
    bars: pd.DataFrame,
    lookback_window: int = 20,
    min_positive_return: float = 0.0,
) -> pd.DataFrame:
    """Generate cross-sectional relative-strength signals from trailing returns."""
    if lookback_window <= 0:
        raise ValueError("lookback_window must be positive")

    data = bars.sort_values(["symbol", "date"]).copy()
    trailing_return = data.groupby("symbol", sort=False)["close"].pct_change(lookback_window)
    shifted_return = trailing_return.groupby(data["symbol"], sort=False).shift(1)
    data["signal_strength"] = shifted_return.fillna(0.0)
    data["signal"] = (data["signal_strength"] > float(min_positive_return)).astype(float)
    data["signal_strength"] = data["signal_strength"].clip(lower=0.0)
    return (
        data[["date", "symbol", "signal", "signal_strength"]]
        .sort_values(["date", "symbol"])
        .reset_index(drop=True)
    )


def run_relative_strength(
    bars: pd.DataFrame,
    config: dict[str, object],
) -> pd.DataFrame:
    return relative_strength_signals(
        bars,
        lookback_window=int(config.get("lookback_window", 20)),
        min_positive_return=float(config.get("min_positive_return", 0.0)),
    )


registry.register(
    "relative_strength",
    run_relative_strength,
    description="Cross-sectional long-only signal based on lagged trailing returns.",
    parameter_defaults={
        "lookback_window": 20,
        "min_positive_return": 0.0,
    },
)
