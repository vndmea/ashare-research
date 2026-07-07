from __future__ import annotations

import pandas as pd

from ashare_research.config import parse_config
from ashare_research.pipeline.run import run_research_and_write_reports


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
