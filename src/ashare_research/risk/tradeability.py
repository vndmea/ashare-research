from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class TradeConstraints:
    exclude_suspended: bool = True
    exclude_st: bool = True
    block_limit_up_buys: bool = True
    block_limit_down_sells: bool = True
    min_amount: float = 0.0


def filter_signals_for_universe(
    signals: pd.DataFrame,
    universe: pd.DataFrame | None,
) -> pd.DataFrame:
    """Keep only signals that are in the date-aware research universe."""
    if universe is None or universe.empty:
        return signals
    return signals.merge(universe[["date", "symbol"]].drop_duplicates(), on=["date", "symbol"])


def filter_signals_for_eligibility(
    signals: pd.DataFrame,
    bars: pd.DataFrame,
    constraints: TradeConstraints,
) -> pd.DataFrame:
    """Remove names that should not be selected as target holdings."""
    eligibility = bars[["date", "symbol"]].drop_duplicates().copy()
    eligibility["eligible"] = True

    if constraints.exclude_suspended and "is_suspended" in bars.columns:
        eligibility = eligibility.merge(
            bars[["date", "symbol", "is_suspended"]],
            on=["date", "symbol"],
            how="left",
        )
        eligibility["eligible"] &= ~eligibility["is_suspended"].fillna(False)
        eligibility = eligibility.drop(columns=["is_suspended"])

    if "tradable" in bars.columns:
        eligibility = eligibility.merge(
            bars[["date", "symbol", "tradable"]],
            on=["date", "symbol"],
            how="left",
        )
        eligibility["eligible"] &= eligibility["tradable"].fillna(False)
        eligibility = eligibility.drop(columns=["tradable"])

    if constraints.exclude_st and "st_status" in bars.columns:
        eligibility = eligibility.merge(
            bars[["date", "symbol", "st_status"]],
            on=["date", "symbol"],
            how="left",
        )
        eligibility["eligible"] &= ~eligibility["st_status"].map(_is_st_status)
        eligibility = eligibility.drop(columns=["st_status"])

    if constraints.min_amount > 0.0 and "amount" in bars.columns:
        eligibility = eligibility.merge(
            bars[["date", "symbol", "amount"]],
            on=["date", "symbol"],
            how="left",
        )
        eligibility["eligible"] &= eligibility["amount"].fillna(0.0) >= constraints.min_amount
        eligibility = eligibility.drop(columns=["amount"])

    eligible_pairs = eligibility.loc[eligibility["eligible"], ["date", "symbol"]]
    return signals.merge(eligible_pairs, on=["date", "symbol"])


def apply_trade_constraints(
    target_weights: pd.DataFrame,
    bars: pd.DataFrame,
    trading_dates: pd.DatetimeIndex,
    constraints: TradeConstraints,
) -> pd.DataFrame:
    """Apply suspension and limit-up/down execution constraints to target weights."""
    if target_weights.empty:
        return pd.DataFrame(columns=["date", "symbol", "weight"])

    dates = pd.DatetimeIndex(pd.to_datetime(trading_dates).drop_duplicates().sort_values())
    if dates.empty:
        return pd.DataFrame(columns=["date", "symbol", "weight"])

    weights = target_weights.copy()
    weights["date"] = pd.to_datetime(weights["date"])
    symbols = sorted(weights["symbol"].drop_duplicates())
    targets = (
        weights.pivot(index="date", columns="symbol", values="weight")
        .reindex(index=dates, columns=symbols)
        .fillna(0.0)
    )

    available = _availability_matrix(bars, dates, symbols)
    tradable = available.copy()
    if constraints.exclude_suspended and "is_suspended" in bars.columns:
        tradable &= ~_flag_matrix(bars, "is_suspended", dates, symbols, default=False)
    if "tradable" in bars.columns:
        tradable &= _flag_matrix(bars, "tradable", dates, symbols, default=False)

    limit_up = _flag_matrix(bars, "limit_up", dates, symbols, default=False)
    limit_down = _flag_matrix(bars, "limit_down", dates, symbols, default=False)

    rows: list[pd.DataFrame] = []
    previous = pd.Series(0.0, index=targets.columns)
    for date in targets.index:
        desired = targets.loc[date].astype(float)
        current = desired.copy()
        blocked = ~tradable.loc[date]

        if constraints.block_limit_up_buys:
            blocked |= limit_up.loc[date] & (desired > previous)
        if constraints.block_limit_down_sells:
            blocked |= limit_down.loc[date] & (desired < previous)

        current.loc[blocked] = previous.loc[blocked]
        current = current.clip(lower=0.0)

        locked_weight = float(current.loc[blocked].sum())
        free = ~blocked
        free_weight = float(current.loc[free].sum())
        capacity = max(0.0, 1.0 - locked_weight)
        if free_weight > capacity and free_weight > 0.0:
            current.loc[free] *= capacity / free_weight

        positive = current[current > 0.0]
        if not positive.empty:
            rows.append(
                pd.DataFrame(
                    {
                        "date": date,
                        "symbol": positive.index,
                        "weight": positive.to_numpy(),
                    }
                )
            )
        previous = current

    if not rows:
        return pd.DataFrame(columns=["date", "symbol", "weight"])
    return pd.concat(rows, ignore_index=True).sort_values(["date", "symbol"]).reset_index(drop=True)


def _availability_matrix(
    bars: pd.DataFrame,
    dates: pd.DatetimeIndex,
    symbols: list[str],
) -> pd.DataFrame:
    state = bars[["date", "symbol"]].drop_duplicates().copy()
    state["available"] = True
    return (
        state.pivot(index="date", columns="symbol", values="available")
        .reindex(index=dates, columns=symbols)
        .fillna(False)
        .astype(bool)
    )


def _flag_matrix(
    bars: pd.DataFrame,
    column: str,
    dates: pd.DatetimeIndex,
    symbols: list[str],
    *,
    default: bool,
) -> pd.DataFrame:
    if column not in bars.columns:
        return pd.DataFrame(default, index=dates, columns=symbols)
    return (
        bars.pivot(index="date", columns="symbol", values=column)
        .reindex(index=dates, columns=symbols)
        .fillna(default)
        .astype(bool)
    )


def _is_st_status(value: object) -> bool:
    if pd.isna(value):
        return False
    text = str(value).strip().lower()
    return text not in {"", "0", "false", "none", "normal", "nan"}
