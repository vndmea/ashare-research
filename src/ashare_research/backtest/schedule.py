from __future__ import annotations

from typing import Literal

import pandas as pd

RebalanceFrequency = Literal["daily", "weekly", "monthly"]


def apply_rebalance_schedule(
    target_weights: pd.DataFrame,
    trading_dates: pd.DatetimeIndex,
    rebalance_frequency: RebalanceFrequency,
    min_holding_days: int,
) -> pd.DataFrame:
    if min_holding_days < 0:
        raise ValueError("min_holding_days must be non-negative")
    if rebalance_frequency == "daily":
        if min_holding_days == 0:
            return target_weights
    if rebalance_frequency not in {"weekly", "monthly"}:
        if rebalance_frequency != "daily":
            raise ValueError(f"Unsupported rebalance_frequency: {rebalance_frequency}")
    if target_weights.empty or trading_dates.empty:
        return pd.DataFrame(columns=["date", "symbol", "weight"])

    dates = pd.DatetimeIndex(pd.to_datetime(trading_dates).drop_duplicates().sort_values())
    rebalance_dates = _rebalance_dates(dates, rebalance_frequency)
    eligible_symbols = sorted(target_weights["symbol"].drop_duplicates())
    signals_by_date = {
        pd.Timestamp(date): frame[["symbol", "weight"]].copy()
        for date, frame in target_weights.groupby("date", sort=True)
    }

    rows: list[pd.DataFrame] = []
    current = pd.Series(0.0, index=eligible_symbols, dtype=float)
    holding_days = pd.Series(0, index=eligible_symbols, dtype=int)
    for date in dates:
        if date in rebalance_dates:
            next_weights = signals_by_date.get(pd.Timestamp(date))
            if next_weights is None:
                proposed = pd.Series(0.0, index=eligible_symbols, dtype=float)
            else:
                proposed = pd.Series(0.0, index=eligible_symbols, dtype=float)
                proposed.loc[next_weights["symbol"]] = next_weights["weight"].to_numpy()

            current, holding_days = _apply_min_holding_days(
                current=current,
                proposed=proposed,
                holding_days=holding_days,
                min_holding_days=min_holding_days,
            )

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
            holding_days.loc[positive.index] += 1

    if not rows:
        return pd.DataFrame(columns=["date", "symbol", "weight"])
    return pd.concat(rows, ignore_index=True).sort_values(["date", "symbol"]).reset_index(drop=True)


def resolve_trading_dates(
    returns: pd.DataFrame,
    trading_calendar: pd.DatetimeIndex | None,
) -> pd.DatetimeIndex:
    if returns.empty:
        return pd.DatetimeIndex([])

    first_date = returns["date"].min()
    last_date = returns["date"].max()
    if trading_calendar is None:
        return pd.DatetimeIndex(returns["date"].drop_duplicates().sort_values())

    calendar = pd.DatetimeIndex(pd.to_datetime(trading_calendar).drop_duplicates().sort_values())
    return calendar[(calendar >= first_date) & (calendar <= last_date)]


def _rebalance_dates(
    trading_dates: pd.DatetimeIndex,
    rebalance_frequency: RebalanceFrequency,
) -> pd.DatetimeIndex:
    if rebalance_frequency == "weekly":
        periods = trading_dates.to_period("W-FRI")
    else:
        periods = trading_dates.to_period("M")
    rebalance = trading_dates.to_series().groupby(periods).min().sort_values()
    return pd.DatetimeIndex(rebalance.to_numpy())


def _apply_min_holding_days(
    current: pd.Series,
    proposed: pd.Series,
    holding_days: pd.Series,
    min_holding_days: int,
) -> tuple[pd.Series, pd.Series]:
    if min_holding_days == 0:
        next_current = proposed.copy()
        next_holding_days = pd.Series(0, index=current.index, dtype=int)
        next_holding_days.loc[next_current[next_current > 0.0].index] = 0
        return next_current, next_holding_days

    blocked = (current > proposed) & (current > 0.0) & (holding_days < min_holding_days)
    next_current = proposed.copy()
    next_current.loc[blocked] = current.loc[blocked]

    if next_current.sum() > 1.0:
        locked_weight = float(next_current.loc[blocked].sum())
        free = ~blocked & (next_current > 0.0)
        free_weight = float(next_current.loc[free].sum())
        capacity = max(0.0, 1.0 - locked_weight)
        if free_weight > capacity and free_weight > 0.0:
            next_current.loc[free] *= capacity / free_weight

    next_holding_days = pd.Series(0, index=current.index, dtype=int)
    continuing = (current > 0.0) & (next_current > 0.0)
    next_holding_days.loc[continuing] = holding_days.loc[continuing]
    return next_current, next_holding_days
