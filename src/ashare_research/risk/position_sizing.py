from __future__ import annotations

from typing import Literal

import pandas as pd

PositionSizingMethod = Literal["equal_weight", "signal_weight"]


def build_target_positions(
    signals: pd.DataFrame,
    max_names: int = 20,
    method: PositionSizingMethod = "equal_weight",
) -> pd.DataFrame:
    """Convert positive signals into daily target weights."""
    if method == "equal_weight":
        return equal_weight_positions(signals, max_names=max_names)
    if method == "signal_weight":
        return signal_weight_positions(signals, max_names=max_names)
    raise ValueError(f"Unsupported position sizing method: {method}")


def equal_weight_positions(signals: pd.DataFrame, max_names: int = 20) -> pd.DataFrame:
    """Convert positive signals into equal-weight daily target weights."""
    selected = _select_positive_signals(signals, max_names=max_names)
    if selected.empty:
        return pd.DataFrame(columns=["date", "symbol", "weight"])

    selected["weight"] = 1.0 / selected.groupby("date")["symbol"].transform("count")
    weights = selected[["date", "symbol", "weight"]]
    return weights.sort_values(["date", "symbol"]).reset_index(drop=True)


def signal_weight_positions(signals: pd.DataFrame, max_names: int = 20) -> pd.DataFrame:
    """Convert positive signals into signal-strength-proportional target weights."""
    selected = _select_positive_signals(signals, max_names=max_names)
    if selected.empty:
        return pd.DataFrame(columns=["date", "symbol", "weight"])

    selected["weight"] = selected["signal_strength"].div(
        selected.groupby("date")["signal_strength"].transform("sum")
    )
    weights = selected[["date", "symbol", "weight"]]
    return weights.sort_values(["date", "symbol"]).reset_index(drop=True)


def _select_positive_signals(signals: pd.DataFrame, max_names: int) -> pd.DataFrame:
    if max_names <= 0:
        raise ValueError("max_names must be positive")

    selected = signals[signals["signal"] > 0].copy()
    if selected.empty:
        return selected

    selected["signal_strength"] = _signal_strength(selected)
    selected = selected[selected["signal_strength"] > 0.0]
    if selected.empty:
        return selected

    selected = selected.sort_values(
        ["date", "signal_strength", "symbol"],
        ascending=[True, False, True],
    )
    selected["rank"] = selected.groupby("date").cumcount() + 1
    return selected[selected["rank"] <= max_names].copy()


def _signal_strength(signals: pd.DataFrame) -> pd.Series:
    if "signal_strength" in signals.columns:
        return pd.to_numeric(signals["signal_strength"], errors="coerce").fillna(0.0)
    return pd.to_numeric(signals["signal"], errors="coerce").fillna(0.0)
