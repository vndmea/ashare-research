from __future__ import annotations

import pandas as pd
import pytest

from ashare_research.config import parse_config
from ashare_research.pipeline.run import (
    load_research_inputs,
    load_symbol_analysis_inputs,
    run_research_and_write_reports,
    summarize_research_inputs,
)


def test_run_research_and_write_reports(tmp_path) -> None:
    bars_path = tmp_path / "daily_bars.csv"
    benchmark_path = tmp_path / "benchmark.csv"
    calendar_path = tmp_path / "trading_calendar.csv"
    universe_path = tmp_path / "universe.csv"
    output_dir = tmp_path / "reports"

    dates = pd.bdate_range("2024-01-01", periods=80)
    bars = pd.DataFrame(
        {
            "date": list(dates) * 2,
            "symbol": ["000001.SZ"] * len(dates) + ["600000.SH"] * len(dates),
            "open": [10.0 + index * 0.1 for index in range(len(dates))] * 2,
            "high": [10.2 + index * 0.1 for index in range(len(dates))] * 2,
            "low": [9.8 + index * 0.1 for index in range(len(dates))] * 2,
            "close": [10.0 + index * 0.1 for index in range(len(dates))] * 2,
            "volume": [1_000_000] * len(dates) * 2,
            "industry": ["Bank"] * len(dates) + ["Broker"] * len(dates),
        }
    )
    benchmark = pd.DataFrame(
        {
            "date": dates,
            "symbol": ["000300.SH"] * len(dates),
            "close": [3500 + index for index in range(len(dates))],
        }
    )
    calendar = pd.DataFrame({"date": dates})
    universe = bars[["date", "symbol"]].drop_duplicates()

    bars.to_csv(bars_path, index=False)
    benchmark.to_csv(benchmark_path, index=False)
    calendar.to_csv(calendar_path, index=False)
    universe.to_csv(universe_path, index=False)

    config = parse_config(
        {
            "data": {
                "daily_bar_path": str(bars_path),
                "benchmark_path": str(benchmark_path),
                "trading_calendar_path": str(calendar_path),
                "universe_path": str(universe_path),
                "price_adjustment": "none",
            },
            "backtest": {
                "start_date": "2024-01-01",
                "end_date": "2024-04-30",
                "initial_cash": 1_000_000,
                "commission_rate": 0.0003,
                "stamp_tax_rate": 0.0005,
                "max_names": 2,
                "position_sizing_method": "equal_weight",
                "rebalance_frequency": "daily",
                "min_holding_days": 0,
            },
            "strategy": {
                "name": "moving_average_crossover",
                "fast_window": 5,
                "slow_window": 20,
            },
        }
    )

    research = run_research_and_write_reports(config, output_dir)

    assert not research.run.backtest.equity_curve.empty
    assert research.reports.summary.exists()
    assert research.reports.industry_exposure.exists()
    assert research.reports.strategy_attribution.exists()
    assert research.reports.execution_diagnostics.exists()
    assert research.reports.trade_ledger.exists()


def test_load_research_inputs_and_summarize(tmp_path) -> None:
    bars_path = tmp_path / "daily_bars.csv"
    benchmark_path = tmp_path / "benchmark.csv"
    calendar_path = tmp_path / "trading_calendar.csv"
    universe_path = tmp_path / "universe.csv"

    dates = pd.bdate_range("2024-01-01", periods=5)
    bars = pd.DataFrame(
        {
            "date": list(dates) * 2,
            "symbol": ["000001.SZ"] * len(dates) + ["600000.SH"] * len(dates),
            "open": [10.0, 10.1, 10.2, 10.3, 10.4] * 2,
            "high": [10.2, 10.3, 10.4, 10.5, 10.6] * 2,
            "low": [9.8, 9.9, 10.0, 10.1, 10.2] * 2,
            "close": [10.1, 10.2, 10.3, 10.4, 10.5] * 2,
            "volume": [1_000_000] * len(dates) * 2,
        }
    )
    benchmark = pd.DataFrame(
        {
            "date": dates,
            "symbol": ["000300.SH"] * len(dates),
            "close": [3500, 3510, 3520, 3530, 3540],
        }
    )
    calendar = pd.DataFrame({"date": dates})
    universe = bars[["date", "symbol"]].drop_duplicates()

    bars.to_csv(bars_path, index=False)
    benchmark.to_csv(benchmark_path, index=False)
    calendar.to_csv(calendar_path, index=False)
    universe.to_csv(universe_path, index=False)

    config = parse_config(
        {
            "data": {
                "daily_bar_path": str(bars_path),
                "benchmark_path": str(benchmark_path),
                "trading_calendar_path": str(calendar_path),
                "universe_path": str(universe_path),
            },
            "backtest": {
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
            },
            "strategy": {
                "name": "moving_average_crossover",
                "fast_window": 2,
                "slow_window": 3,
            },
        }
    )

    inputs = load_research_inputs(config)
    summary = summarize_research_inputs(inputs)

    assert summary.bar_rows == 10
    assert summary.symbol_count == 2
    assert summary.start_date == "2024-01-01"
    assert summary.end_date == "2024-01-05"
    assert summary.benchmark_rows == 4
    assert summary.trading_calendar_days == 5
    assert summary.universe_rows == 10


def test_load_research_inputs_rejects_calendar_missing_bars_dates(tmp_path) -> None:
    paths = _write_research_input_files(
        tmp_path,
        calendar_dates=pd.bdate_range("2024-01-01", periods=4),
    )
    config = _config_for_paths(paths)

    with pytest.raises(
        ValueError,
        match="trading_calendar is missing bars dates",
    ):
        load_research_inputs(config)


def test_load_research_inputs_rejects_benchmark_date_misalignment(tmp_path) -> None:
    paths = _write_research_input_files(
        tmp_path,
        benchmark_dates=pd.bdate_range("2024-01-02", periods=5),
    )
    config = _config_for_paths(paths)

    with pytest.raises(
        ValueError,
        match="benchmark_returns is missing bars close-to-next-close return dates",
    ):
        load_research_inputs(config)


def test_load_research_inputs_rejects_universe_pairs_missing_from_bars(tmp_path) -> None:
    paths = _write_research_input_files(
        tmp_path,
        universe_rows=pd.DataFrame(
            {
                "date": pd.bdate_range("2024-01-01", periods=5).tolist()
                + [pd.Timestamp("2024-01-03")],
                "symbol": [
                    "000001.SZ",
                    "000001.SZ",
                    "000001.SZ",
                    "000001.SZ",
                    "000001.SZ",
                    "300750.SZ",
                ],
            }
        ),
    )
    config = _config_for_paths(paths)

    with pytest.raises(
        ValueError,
        match="universe contains date/symbol pairs not present in bars",
    ):
        load_research_inputs(config)


def test_load_symbol_analysis_inputs_tolerates_missing_benchmark_dates(tmp_path) -> None:
    paths = _write_research_input_files(
        tmp_path,
        benchmark_dates=pd.bdate_range("2024-01-03", periods=4),
    )
    config = _config_for_paths(paths)

    inputs = load_symbol_analysis_inputs(config)

    assert not inputs.bars.empty


def _write_research_input_files(
    tmp_path,
    *,
    calendar_dates: pd.DatetimeIndex | None = None,
    benchmark_dates: pd.DatetimeIndex | None = None,
    universe_rows: pd.DataFrame | None = None,
) -> dict[str, object]:
    bars_path = tmp_path / "daily_bars.csv"
    benchmark_path = tmp_path / "benchmark.csv"
    calendar_path = tmp_path / "trading_calendar.csv"
    universe_path = tmp_path / "universe.csv"

    dates = pd.bdate_range("2024-01-01", periods=5)
    bars = pd.DataFrame(
        {
            "date": list(dates) * 2,
            "symbol": ["000001.SZ"] * len(dates) + ["600000.SH"] * len(dates),
            "open": [10.0, 10.1, 10.2, 10.3, 10.4] * 2,
            "high": [10.2, 10.3, 10.4, 10.5, 10.6] * 2,
            "low": [9.8, 9.9, 10.0, 10.1, 10.2] * 2,
            "close": [10.1, 10.2, 10.3, 10.4, 10.5] * 2,
            "volume": [1_000_000] * len(dates) * 2,
        }
    )
    benchmark_source_dates = benchmark_dates if benchmark_dates is not None else dates
    benchmark = pd.DataFrame(
        {
            "date": benchmark_source_dates,
            "symbol": ["000300.SH"] * len(benchmark_source_dates),
            "close": [3500 + index * 10 for index in range(len(benchmark_source_dates))],
        }
    )
    calendar = pd.DataFrame({"date": calendar_dates if calendar_dates is not None else dates})
    universe = (
        universe_rows
        if universe_rows is not None
        else bars[["date", "symbol"]].drop_duplicates().reset_index(drop=True)
    )

    bars.to_csv(bars_path, index=False)
    benchmark.to_csv(benchmark_path, index=False)
    calendar.to_csv(calendar_path, index=False)
    universe.to_csv(universe_path, index=False)

    return {
        "bars_path": bars_path,
        "benchmark_path": benchmark_path,
        "calendar_path": calendar_path,
        "universe_path": universe_path,
    }


def _config_for_paths(paths: dict[str, object]):
    return parse_config(
        {
            "data": {
                "daily_bar_path": str(paths["bars_path"]),
                "benchmark_path": str(paths["benchmark_path"]),
                "trading_calendar_path": str(paths["calendar_path"]),
                "universe_path": str(paths["universe_path"]),
            },
            "backtest": {
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
            },
            "strategy": {
                "name": "moving_average_crossover",
                "fast_window": 2,
                "slow_window": 3,
            },
        }
    )
