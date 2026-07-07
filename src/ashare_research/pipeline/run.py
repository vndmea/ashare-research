from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ashare_research.analysis.reports import ReportPaths, write_research_report
from ashare_research.backtest.engine import BacktestResult, run_close_to_close_backtest
from ashare_research.config import BacktestConfig, ResearchConfig
from ashare_research.data.benchmarks import load_benchmark_returns
from ashare_research.data.calendar import load_trading_calendar
from ashare_research.data.daily_bars import load_daily_bars
from ashare_research.data.universe import load_universe_snapshot
from ashare_research.risk.tradeability import TradeConstraints
from ashare_research.strategies import registry as strategy_registry


@dataclass(frozen=True)
class ResearchArtifacts:
    bars: pd.DataFrame
    signals: pd.DataFrame
    benchmark_returns: pd.DataFrame | None
    trading_calendar: pd.DatetimeIndex | None
    universe: pd.DataFrame | None


@dataclass(frozen=True)
class ResearchRun:
    config: ResearchConfig
    artifacts: ResearchArtifacts
    backtest: BacktestResult


@dataclass(frozen=True)
class ResearchRunWithReports:
    run: ResearchRun
    reports: ReportPaths


def run_research(config: ResearchConfig) -> ResearchRun:
    bars = load_daily_bars(
        config.data.daily_bar_path,
        start_date=config.backtest.start_date,
        end_date=config.backtest.end_date,
        price_adjustment=config.data.price_adjustment,
        adjustment_factor_path=config.data.adjustment_factor_path,
    )
    trading_calendar = _load_optional_calendar(config)
    universe = _load_optional_universe(config)
    benchmark_returns = _load_optional_benchmark(config)
    signals = _run_strategy(config, bars)
    backtest = run_close_to_close_backtest(
        bars,
        signals,
        initial_cash=config.backtest.initial_cash,
        commission_rate=config.backtest.commission_rate,
        stamp_tax_rate=config.backtest.stamp_tax_rate,
        max_names=config.backtest.max_names,
        position_sizing_method=config.backtest.position_sizing_method,
        rebalance_frequency=config.backtest.rebalance_frequency,
        min_holding_days=config.backtest.min_holding_days,
        benchmark_returns=benchmark_returns,
        trading_calendar=trading_calendar,
        universe=universe,
        trade_constraints=_trade_constraints(config.backtest),
    )
    return ResearchRun(
        config=config,
        artifacts=ResearchArtifacts(
            bars=bars,
            signals=signals,
            benchmark_returns=benchmark_returns,
            trading_calendar=trading_calendar,
            universe=universe,
        ),
        backtest=backtest,
    )


def run_research_and_write_reports(
    config: ResearchConfig,
    output_dir: str | Path,
) -> ResearchRunWithReports:
    run = run_research(config)
    reports = write_research_report(
        output_dir,
        run.backtest.equity_curve,
        run.backtest.positions,
        run.backtest.metrics,
        bars=run.artifacts.bars,
        benchmark_returns=run.artifacts.benchmark_returns,
    )
    return ResearchRunWithReports(run=run, reports=reports)


def _run_strategy(config: ResearchConfig, bars: pd.DataFrame) -> pd.DataFrame:
    runner = strategy_registry.get(config.strategy.name)
    return runner(
        bars,
        {
            "fast_window": config.strategy.fast_window,
            "slow_window": config.strategy.slow_window,
        },
    )


def _load_optional_benchmark(config: ResearchConfig) -> pd.DataFrame | None:
    if not config.data.benchmark_path:
        return None
    return load_benchmark_returns(
        config.data.benchmark_path,
        start_date=config.backtest.start_date,
        end_date=config.backtest.end_date,
    )


def _load_optional_calendar(config: ResearchConfig) -> pd.DatetimeIndex | None:
    if not config.data.trading_calendar_path:
        return None
    calendar_path = Path(config.data.trading_calendar_path)
    if not calendar_path.exists():
        return None
    return load_trading_calendar(calendar_path)


def _load_optional_universe(config: ResearchConfig) -> pd.DataFrame | None:
    if not config.data.universe_path:
        return None
    universe_path = Path(config.data.universe_path)
    if not universe_path.exists():
        return None
    return load_universe_snapshot(universe_path)


def _trade_constraints(backtest: BacktestConfig) -> TradeConstraints:
    return TradeConstraints(
        exclude_suspended=backtest.exclude_suspended,
        exclude_st=backtest.exclude_st,
        block_limit_up_buys=backtest.block_limit_up_buys,
        block_limit_down_sells=backtest.block_limit_down_sells,
        min_amount=backtest.min_amount,
    )
