from __future__ import annotations

from pathlib import Path

import pandas as pd

PRICE_COLUMNS = ("open", "high", "low", "close")
ADJUSTMENT_FACTOR_COLUMNS = {"date", "symbol", "adj_factor"}
VALID_ADJUSTMENT_MODES = {"none", "forward", "backward"}


def load_adjustment_factors(path: str | Path) -> pd.DataFrame:
    """Load external adjustment factors with date, symbol, and adj_factor columns."""
    factor_path = Path(path)
    factors = pd.read_csv(factor_path, parse_dates=["date"])
    missing = ADJUSTMENT_FACTOR_COLUMNS.difference(factors.columns)
    if missing:
        raise ValueError(f"Adjustment factors are missing required columns: {sorted(missing)}")

    factors = factors[["date", "symbol", "adj_factor"]].copy()
    factors["symbol"] = factors["symbol"].astype("string").str.strip()
    factors["adj_factor"] = pd.to_numeric(factors["adj_factor"], errors="raise")
    _validate_adjustment_factors(factors)
    return factors.sort_values(["date", "symbol"]).reset_index(drop=True)


def merge_adjustment_factors(bars: pd.DataFrame, factors: pd.DataFrame) -> pd.DataFrame:
    """Attach external adjustment factors to bars, overriding any existing adj_factor column."""
    data = bars.drop(columns=["adj_factor"], errors="ignore").copy()
    merged = data.merge(factors, on=["date", "symbol"], how="left")
    missing = merged["adj_factor"].isna()
    if missing.any():
        sample = merged.loc[missing, ["date", "symbol"]].head().to_dict("records")
        raise ValueError(f"Missing adjustment factors for bar rows: {sample}")
    return merged


def apply_price_adjustment(
    bars: pd.DataFrame,
    mode: str = "none",
    *,
    keep_raw_prices: bool = True,
) -> pd.DataFrame:
    """Apply forward or backward price adjustment using adj_factor.

    This follows the common A-share factor convention used by vendors such as Tushare:
    forward adjustment uses price * adj_factor / latest_adj_factor, and backward
    adjustment uses price * adj_factor / first_adj_factor.
    """
    normalized_mode = _normalize_adjustment_mode(mode)
    data = bars.copy()
    if normalized_mode == "none":
        return data

    if "adj_factor" not in data.columns:
        raise ValueError("Price adjustment requires an adj_factor column or external factor file.")

    data = data.sort_values(["symbol", "date"]).reset_index(drop=True)
    data["adj_factor"] = pd.to_numeric(data["adj_factor"], errors="raise")
    _validate_adjustment_factors(data[["date", "symbol", "adj_factor"]])

    anchor_method = "last" if normalized_mode == "forward" else "first"
    anchor = data.groupby("symbol", sort=False)["adj_factor"].transform(anchor_method)
    ratio = data["adj_factor"] / anchor

    for column in PRICE_COLUMNS:
        if column not in data.columns:
            continue
        if keep_raw_prices and f"raw_{column}" not in data.columns:
            data[f"raw_{column}"] = data[column]
        data[column] = pd.to_numeric(data[column], errors="raise") * ratio

    data["price_adjustment"] = normalized_mode
    return data.sort_values(["date", "symbol"]).reset_index(drop=True)


def _normalize_adjustment_mode(mode: str) -> str:
    normalized = str(mode).strip().lower()
    aliases = {
        "": "none",
        "no": "none",
        "raw": "none",
        "qfq": "forward",
        "front": "forward",
        "pre": "forward",
        "hfq": "backward",
        "back": "backward",
        "post": "backward",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in VALID_ADJUSTMENT_MODES:
        raise ValueError(
            f"Unsupported price adjustment mode: {mode}. "
            f"Expected one of {sorted(VALID_ADJUSTMENT_MODES)}."
        )
    return normalized


def _validate_adjustment_factors(factors: pd.DataFrame) -> None:
    if factors.empty:
        raise ValueError("Adjustment factors are empty.")
    duplicated = factors.duplicated(["date", "symbol"])
    if duplicated.any():
        sample = factors.loc[duplicated, ["date", "symbol"]].head().to_dict("records")
        raise ValueError(f"Adjustment factors contain duplicate rows: {sample}")
    invalid = factors["adj_factor"].isna() | (factors["adj_factor"] <= 0)
    if invalid.any():
        sample = factors.loc[invalid, ["date", "symbol", "adj_factor"]].head().to_dict("records")
        raise ValueError(f"Adjustment factors must be positive: {sample}")
