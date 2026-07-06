from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from ashare_research.analysis.metrics import PerformanceMetrics, calculate_metrics
from ashare_research.risk.position_sizing import PositionSizingMethod, build_target_positions
from ashare_research.risk.tradeability import (
    TradeConstraints,
    apply_trade_constraints,
    filter_signals_for_eligibility,
    filter_signals_for_universe,
)

RebalanceFrequency = Literal["daily", "weekly", "monthly"]


@dataclass(frozen=True)
class BacktestResult:
    equity_curve: pd.DataFrame
    positions: pd.DataFrame
    metrics: PerformanceMetrics


def run_close_to_close_backtest(
    bars: pd.DataFrame,
    signals: pd.DataFrame,
    initial_cash: float = 1_000_000,
    commission_rate: float = 0.0003,
    stamp_tax_rate: float = 0.0005,
    max_names: int = 20,
    position_sizing_method: PositionSizingMethod = "equal_weight",
    rebalance_frequency: RebalanceFrequency = "daily",
    min_holding_days: int = 0,
    benchmark_returns: pd.DataFrame | None = None,
    trading_calendar: pd.DatetimeIndex | None = None,
    universe: pd.DataFrame | None = None,
    trade_constraints: TradeConstraints | None = None,
) -> BacktestResult:
    """Run a simple close-to-close daily portfolio backtest.

    The model applies target weights at each close and earns next-day close returns.
    It is intentionally minimal and intended for strategy logic validation only.
    """
    if initial_cash <= 0:
        raise ValueError("initial_cash must be positive")

    returns = _daily_symbol_returns(bars)
    trading_dates = _resolve_trading_dates(returns, trading_calendar)
    constraints = trade_constraints or TradeConstraints()
    eligible_signals = filter_signals_for_universe(signals, universe)
    eligible_signals = filter_signals_for_eligibility(eligible_signals, bars, constraints)
    target_weights = build_target_positions(
        eligible_signals,
        max_names=max_names,
        method=position_sizing_method,
    )
    target_weights = _apply_rebalance_schedule(
        target_weights,
        trading_dates=trading_dates,
        rebalance_frequency=rebalance_frequency,
        min_holding_days=min_holding_days,
    )
    positions = apply_trade_constraints(target_weights, bars, trading_dates, constraints)

    portfolio = positions.merge(returns, on=["date", "symbol"], how="left").fillna({"return": 0.0})
    portfolio["weighted_return"] = portfolio["weight"] * portfolio["return"]
    portfolio_returns = portfolio.groupby("date", as_index=False).agg(
        gross_return=("weighted_return", "sum")
    )

    turnover = _daily_turnover(positions)
    exposure = _daily_exposure(positions)
    rebalance_flags = _daily_rebalance_flags(positions)
    trading_date_frame = pd.DataFrame({"date": trading_dates})
    portfolio_returns = (
        trading_date_frame.merge(portfolio_returns, on="date", how="left")
        .merge(turnover, on="date", how="left")
        .merge(exposure, on="date", how="left")
        .merge(rebalance_flags, on="date", how="left")
        .fillna(0.0)
    )
    portfolio_returns = portfolio_returns.sort_values("date").reset_index(drop=True)
    portfolio_returns["cash_weight"] = (1.0 - portfolio_returns["gross_exposure"]).clip(lower=0.0)
    portfolio_returns["cost"] = portfolio_returns["turnover"] * commission_rate
    portfolio_returns["tax"] = portfolio_returns["sell_turnover"] * stamp_tax_rate
    portfolio_returns["net_return"] = (
        portfolio_returns["gross_return"] - portfolio_returns["cost"] - portfolio_returns["tax"]
    )
    portfolio_returns["equity"] = initial_cash * (1.0 + portfolio_returns["net_return"]).cumprod()

    metrics = calculate_metrics(
        portfolio_returns,
        initial_cash=initial_cash,
        benchmark_returns=benchmark_returns,
    )
    return BacktestResult(
        equity_curve=portfolio_returns,
        positions=positions,
        metrics=metrics,
    )


def _daily_symbol_returns(bars: pd.DataFrame) -> pd.DataFrame:
    data = bars.sort_values(["symbol", "date"]).copy()
    data["next_close"] = data.groupby("symbol", sort=False)["close"].shift(-1)
    data["return"] = data["next_close"].div(data["close"]).sub(1.0)
    return data[["date", "symbol", "return"]].dropna(subset=["return"])


def _daily_turnover(weights: pd.DataFrame) -> pd.DataFrame:
    if weights.empty:
        return pd.DataFrame(columns=["date", "turnover", "sell_turnover"])

    wide = weights.pivot(index="date", columns="symbol", values="weight").fillna(0.0).sort_index()
    previous = wide.shift(1).fillna(0.0)
    changes = wide - previous
    turnover = changes.abs().sum(axis=1)
    sell_turnover = changes.clip(upper=0.0).abs().sum(axis=1)
    return pd.DataFrame(
        {
            "date": wide.index,
            "turnover": turnover.to_numpy(),
            "sell_turnover": sell_turnover.to_numpy(),
        }
    )


def _daily_exposure(weights: pd.DataFrame) -> pd.DataFrame:
    if weights.empty:
        return pd.DataFrame(columns=["date", "gross_exposure"])
    return weights.groupby("date", as_index=False).agg(gross_exposure=("weight", "sum"))


def _daily_rebalance_flags(weights: pd.DataFrame) -> pd.DataFrame:
    if weights.empty:
        return pd.DataFrame(columns=["date", "is_rebalance_day"])

    wide = weights.pivot(index="date", columns="symbol", values="weight").fillna(0.0).sort_index()
    changed = wide.ne(wide.shift(1).fillna(0.0)).any(axis=1)
    return pd.DataFrame(
        {
            "date": wide.index,
            "is_rebalance_day": changed.astype(float).to_numpy(),
        }
    )


def _resolve_trading_dates(
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


def _apply_rebalance_schedule(
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
