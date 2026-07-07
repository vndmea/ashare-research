from __future__ import annotations

import json

import pandas as pd

from ashare_research.config import parse_config
from ashare_research.experiments.sweep import run_parameter_sweep, write_parameter_sweep_artifacts


def test_run_parameter_sweep_returns_summary(tmp_path) -> None:
    bars_path = tmp_path / "daily_bars.csv"
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
        }
    )
    bars.to_csv(bars_path, index=False)

    config = parse_config(
        {
            "data": {
                "daily_bar_path": str(bars_path),
            },
            "backtest": {},
            "strategy": {
                "name": "moving_average_crossover",
                "fast_window": 5,
                "slow_window": 20,
            },
        }
    )

    summary, runs = run_parameter_sweep(
        config,
        fast_windows=[5, 10],
        slow_windows=[20, 30],
    )

    assert len(runs) == 4
    assert len(summary) == 4
    assert {"run_id", "fast_window", "slow_window", "total_return"}.issubset(summary.columns)


def test_run_parameter_sweep_supports_generic_parameter_grid_and_artifacts(tmp_path) -> None:
    bars_path = tmp_path / "daily_bars.csv"
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
        }
    )
    bars.to_csv(bars_path, index=False)

    config = parse_config(
        {
            "data": {
                "daily_bar_path": str(bars_path),
            },
            "backtest": {},
            "strategy": {
                "name": "relative_strength",
                "lookback_window": 10,
            },
            "report": {
                "output_dir": str(tmp_path / "sweeps"),
            },
        }
    )

    summary, runs = run_parameter_sweep(
        config,
        parameter_grid={
            "lookback_window": [5, 10],
            "min_positive_return": [0.0, 0.01],
        },
    )
    artifacts = write_parameter_sweep_artifacts(summary, config, tmp_path / "sweeps")

    manifest = json.loads(artifacts.manifest.read_text(encoding="utf-8"))

    assert len(runs) == 4
    assert len(summary) == 4
    assert {"lookback_window", "min_positive_return", "run_id"}.issubset(summary.columns)
    assert artifacts.summary.exists()
    assert artifacts.manifest.exists()
    assert manifest["run_count"] == 4
    assert manifest["strategy_name"] == "relative_strength"
