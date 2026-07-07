from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import pandas as pd

from ashare_research.analysis.reports import (
    ReportPaths,
    SymbolTechnicalReportPaths,
    write_research_report,
    write_symbol_technical_analysis_report,
)
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
class ResearchInputs:
    bars: pd.DataFrame
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


@dataclass(frozen=True)
class SymbolTechnicalAnalysisRun:
    config: ResearchConfig
    inputs: ResearchInputs
    summary: pd.DataFrame


@dataclass(frozen=True)
class SymbolTechnicalAnalysisRunWithReports:
    run: SymbolTechnicalAnalysisRun
    reports: SymbolTechnicalReportPaths


@dataclass(frozen=True)
class DataValidationSummary:
    bar_rows: int
    symbol_count: int
    start_date: str
    end_date: str
    benchmark_rows: int
    trading_calendar_days: int
    universe_rows: int


def run_research(config: ResearchConfig) -> ResearchRun:
    inputs = load_research_inputs(config)
    signals = _run_strategy(config, inputs.bars)
    backtest = run_close_to_close_backtest(
        inputs.bars,
        signals,
        initial_cash=config.backtest.initial_cash,
        commission_rate=config.backtest.commission_rate,
        stamp_tax_rate=config.backtest.stamp_tax_rate,
        slippage_rate=config.backtest.slippage_rate,
        max_names=config.backtest.max_names,
        position_sizing_method=config.backtest.position_sizing_method,
        rebalance_frequency=config.backtest.rebalance_frequency,
        min_holding_days=config.backtest.min_holding_days,
        benchmark_returns=inputs.benchmark_returns,
        trading_calendar=inputs.trading_calendar,
        universe=inputs.universe,
        trade_constraints=_trade_constraints(config.backtest),
    )
    return ResearchRun(
        config=config,
        artifacts=ResearchArtifacts(
            bars=inputs.bars,
            signals=signals,
            benchmark_returns=inputs.benchmark_returns,
            trading_calendar=inputs.trading_calendar,
            universe=inputs.universe,
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
        execution_diagnostics=run.backtest.execution_diagnostics,
        trade_ledger=run.backtest.trade_ledger,
    )
    return ResearchRunWithReports(run=run, reports=reports)


def load_research_inputs(config: ResearchConfig) -> ResearchInputs:
    bars = load_daily_bars(
        config.data.daily_bar_path,
        start_date=config.backtest.start_date,
        end_date=config.backtest.end_date,
        price_adjustment=config.data.price_adjustment,
        adjustment_factor_path=config.data.adjustment_factor_path,
    )
    inputs = ResearchInputs(
        bars=bars,
        trading_calendar=_load_optional_calendar(config),
        universe=_load_optional_universe(config),
        benchmark_returns=_load_optional_benchmark(config),
    )
    validate_research_input_alignment(inputs)
    return inputs


def run_symbol_technical_analysis(
    config: ResearchConfig,
    symbols: tuple[str, ...] | None = None,
) -> SymbolTechnicalAnalysisRun:
    runtime_config = (
        replace(
            config,
            technical_analysis=replace(config.technical_analysis, symbols=symbols),
        )
        if symbols is not None
        else config
    )
    inputs = load_symbol_analysis_inputs(runtime_config)
    from ashare_research.analysis.technical import build_symbol_technical_analysis_report

    summary = build_symbol_technical_analysis_report(
        inputs.bars,
        runtime_config.technical_analysis,
        benchmark_returns=inputs.benchmark_returns,
    )
    return SymbolTechnicalAnalysisRun(
        config=runtime_config,
        inputs=inputs,
        summary=summary,
    )


def run_symbol_technical_analysis_and_write_reports(
    config: ResearchConfig,
    output_dir: str | Path,
    symbols: tuple[str, ...] | None = None,
) -> SymbolTechnicalAnalysisRunWithReports:
    run = run_symbol_technical_analysis(config, symbols=symbols)
    reports = write_symbol_technical_analysis_report(
        output_dir,
        run.inputs.bars,
        run.config.technical_analysis,
        benchmark_returns=run.inputs.benchmark_returns,
    )
    return SymbolTechnicalAnalysisRunWithReports(run=run, reports=reports)


def summarize_research_inputs(inputs: ResearchInputs) -> DataValidationSummary:
    dates = pd.to_datetime(inputs.bars["date"], errors="raise")
    return DataValidationSummary(
        bar_rows=len(inputs.bars),
        symbol_count=int(inputs.bars["symbol"].nunique()),
        start_date=dates.min().date().isoformat(),
        end_date=dates.max().date().isoformat(),
        benchmark_rows=0 if inputs.benchmark_returns is None else len(inputs.benchmark_returns),
        trading_calendar_days=0 if inputs.trading_calendar is None else len(inputs.trading_calendar),
        universe_rows=0 if inputs.universe is None else len(inputs.universe),
    )


def load_symbol_analysis_inputs(config: ResearchConfig) -> ResearchInputs:
    bars = load_daily_bars(
        config.data.daily_bar_path,
        start_date=config.backtest.start_date,
        end_date=config.backtest.end_date,
        price_adjustment=config.data.price_adjustment,
        adjustment_factor_path=config.data.adjustment_factor_path,
    )
    inputs = ResearchInputs(
        bars=bars,
        trading_calendar=None,
        universe=None,
        benchmark_returns=_load_optional_benchmark_for_symbol_analysis(config, bars),
    )
    return validate_symbol_analysis_input_alignment(inputs)


def validate_research_input_alignment(inputs: ResearchInputs) -> None:
    bar_dates = pd.DatetimeIndex(
        pd.to_datetime(inputs.bars["date"], errors="raise").drop_duplicates().sort_values()
    )
    if bar_dates.empty:
        raise ValueError("bars do not contain any trading dates.")

    if inputs.trading_calendar is not None:
        _validate_trading_calendar_alignment(bar_dates, inputs.trading_calendar)
    if inputs.benchmark_returns is not None:
        _validate_benchmark_alignment(bar_dates, inputs.benchmark_returns)
    if inputs.universe is not None:
        _validate_universe_alignment(inputs.bars, bar_dates, inputs.universe)


def validate_symbol_analysis_input_alignment(inputs: ResearchInputs) -> ResearchInputs:
    bar_dates = pd.DatetimeIndex(
        pd.to_datetime(inputs.bars["date"], errors="raise").drop_duplicates().sort_values()
    )
    if bar_dates.empty:
        raise ValueError("bars do not contain any trading dates.")
    if inputs.benchmark_returns is not None:
        return replace(
            inputs,
            benchmark_returns=_align_symbol_analysis_benchmark(
                bar_dates,
                inputs.benchmark_returns,
            ),
        )
    return inputs


def _run_strategy(config: ResearchConfig, bars: pd.DataFrame) -> pd.DataFrame:
    definition = strategy_registry.get_definition(config.strategy.name)
    return definition.runner(
        bars,
        config.strategy.resolved_parameters(definition.parameter_defaults),
    )


def _load_optional_benchmark(config: ResearchConfig) -> pd.DataFrame | None:
    if not config.data.benchmark_path:
        return None
    return load_benchmark_returns(
        config.data.benchmark_path,
        start_date=config.backtest.start_date,
        end_date=config.backtest.end_date,
    )


def _load_optional_benchmark_for_symbol_analysis(
    config: ResearchConfig,
    bars: pd.DataFrame,
) -> pd.DataFrame | None:
    if not config.data.benchmark_path:
        return None
    benchmark_path = Path(config.data.benchmark_path)
    if not benchmark_path.exists():
        return None
    bar_dates = pd.to_datetime(bars["date"], errors="raise")
    try:
        benchmark = load_benchmark_returns(
            benchmark_path,
            start_date=bar_dates.min().date().isoformat(),
            end_date=bar_dates.max().date().isoformat(),
        )
    except ValueError:
        return None
    return benchmark


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
        max_volume_participation=backtest.max_volume_participation,
    )


def _validate_trading_calendar_alignment(
    bar_dates: pd.DatetimeIndex,
    trading_calendar: pd.DatetimeIndex,
) -> None:
    calendar = pd.DatetimeIndex(pd.to_datetime(trading_calendar, errors="raise").drop_duplicates())
    in_range = calendar[(calendar >= bar_dates.min()) & (calendar <= bar_dates.max())].sort_values()
    _raise_on_missing_or_extra_dates(
        actual_dates=in_range,
        expected_dates=bar_dates,
        actual_name="trading_calendar",
        expected_name="bars",
    )


def _validate_benchmark_alignment(
    bar_dates: pd.DatetimeIndex,
    benchmark_returns: pd.DataFrame,
) -> None:
    expected_dates = bar_dates[:-1]
    actual_dates = pd.DatetimeIndex(
        pd.to_datetime(benchmark_returns["date"], errors="raise").drop_duplicates().sort_values()
    )
    _raise_on_missing_or_extra_dates(
        actual_dates=actual_dates,
        expected_dates=expected_dates,
        actual_name="benchmark_returns",
        expected_name="bars close-to-next-close return dates",
    )


def _align_symbol_analysis_benchmark(
    bar_dates: pd.DatetimeIndex,
    benchmark_returns: pd.DataFrame,
) -> pd.DataFrame | None:
    actual_dates = pd.DatetimeIndex(
        pd.to_datetime(benchmark_returns["date"], errors="raise").drop_duplicates().sort_values()
    )
    expected_dates = bar_dates[:-1]
    overlapping_dates = actual_dates.intersection(expected_dates)
    if overlapping_dates.empty:
        return None
    return benchmark_returns.loc[
        pd.to_datetime(benchmark_returns["date"], errors="raise").isin(overlapping_dates)
    ].reset_index(drop=True)


def _validate_universe_alignment(
    bars: pd.DataFrame,
    bar_dates: pd.DatetimeIndex,
    universe: pd.DataFrame,
) -> None:
    universe_in_range = universe.loc[
        universe["date"].between(bar_dates.min(), bar_dates.max()),
        ["date", "symbol"],
    ].copy()
    universe_dates = pd.DatetimeIndex(
        pd.to_datetime(universe_in_range["date"], errors="raise").drop_duplicates().sort_values()
    )
    missing_dates = sorted(set(bar_dates).difference(universe_dates))
    if missing_dates:
        sample = [pd.Timestamp(date).date().isoformat() for date in missing_dates[:5]]
        raise ValueError(f"universe is missing bars dates: {sample}")

    bar_pairs = {
        (pd.Timestamp(row.date), str(row.symbol))
        for row in bars[["date", "symbol"]].drop_duplicates().itertuples(index=False)
    }
    invalid_pairs = [
        {"date": pd.Timestamp(row.date).date().isoformat(), "symbol": str(row.symbol)}
        for row in universe_in_range.drop_duplicates().itertuples(index=False)
        if (pd.Timestamp(row.date), str(row.symbol)) not in bar_pairs
    ]
    if invalid_pairs:
        raise ValueError(f"universe contains date/symbol pairs not present in bars: {invalid_pairs[:5]}")


def _raise_on_missing_or_extra_dates(
    actual_dates: pd.DatetimeIndex,
    expected_dates: pd.DatetimeIndex,
    *,
    actual_name: str,
    expected_name: str,
) -> None:
    missing_dates = sorted(set(expected_dates).difference(actual_dates))
    if missing_dates:
        sample = [pd.Timestamp(date).date().isoformat() for date in missing_dates[:5]]
        raise ValueError(f"{actual_name} is missing {expected_name} dates: {sample}")

    extra_dates = sorted(set(actual_dates).difference(expected_dates))
    if extra_dates:
        sample = [pd.Timestamp(date).date().isoformat() for date in extra_dates[:5]]
        raise ValueError(f"{actual_name} contains dates not present in {expected_name}: {sample}")
