from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ashare_research.analysis.metrics import PerformanceMetrics, calculate_metrics
from ashare_research.backtest.accounting import (
    build_portfolio_equity_curve,
    build_trade_ledger,
    daily_symbol_returns,
)
from ashare_research.backtest.schedule import RebalanceFrequency, apply_rebalance_schedule, resolve_trading_dates
from ashare_research.risk.position_sizing import PositionSizingMethod, build_target_positions
from ashare_research.risk.tradeability import (
    TradeConstraints,
    apply_trade_constraints,
    filter_signals_for_eligibility,
    filter_signals_for_universe,
)


@dataclass(frozen=True)
class BacktestResult:
    equity_curve: pd.DataFrame
    positions: pd.DataFrame
    trade_ledger: pd.DataFrame
    execution_diagnostics: pd.DataFrame
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
    slippage_rate: float = 0.0,
) -> BacktestResult:
    """Run a simple close-to-close daily portfolio backtest.

    The model applies target weights at each close and earns next-day close returns.
    It is intentionally minimal and intended for strategy logic validation only.
    """
    if initial_cash <= 0:
        raise ValueError("initial_cash must be positive")

    returns = daily_symbol_returns(bars)
    trading_dates = resolve_trading_dates(returns, trading_calendar)
    constraints = trade_constraints or TradeConstraints()
    eligible_signals = filter_signals_for_universe(signals, universe)
    eligible_signals = filter_signals_for_eligibility(eligible_signals, bars, constraints)
    target_weights = build_target_positions(
        eligible_signals,
        max_names=max_names,
        method=position_sizing_method,
    )
    target_weights = apply_rebalance_schedule(
        target_weights,
        trading_dates=trading_dates,
        rebalance_frequency=rebalance_frequency,
        min_holding_days=min_holding_days,
    )
    execution = apply_trade_constraints(
        target_weights,
        bars,
        trading_dates,
        constraints,
        reference_cash=initial_cash,
    )
    portfolio_returns = build_portfolio_equity_curve(
        execution.positions,
        returns,
        trading_dates,
        initial_cash=initial_cash,
        commission_rate=commission_rate,
        stamp_tax_rate=stamp_tax_rate,
        slippage_rate=slippage_rate,
    )
    trade_ledger = build_trade_ledger(
        execution.execution_diagnostics,
        portfolio_returns,
        initial_cash=initial_cash,
    )

    metrics = calculate_metrics(
        portfolio_returns,
        initial_cash=initial_cash,
        benchmark_returns=benchmark_returns,
    )
    return BacktestResult(
        equity_curve=portfolio_returns,
        positions=execution.positions,
        trade_ledger=trade_ledger,
        execution_diagnostics=execution.execution_diagnostics,
        metrics=metrics,
    )
