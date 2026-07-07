from __future__ import annotations

from dataclasses import replace
from itertools import product
from pathlib import Path

import pandas as pd

from ashare_research.config import ResearchConfig, StrategyConfig
from ashare_research.pipeline.run import ResearchRun, run_research


def run_parameter_sweep(
    config: ResearchConfig,
    *,
    fast_windows: list[int],
    slow_windows: list[int],
) -> tuple[pd.DataFrame, list[ResearchRun]]:
    runs: list[ResearchRun] = []
    rows: list[dict[str, float | int | str]] = []

    for fast_window, slow_window in product(fast_windows, slow_windows):
        if fast_window >= slow_window:
            continue
        strategy = replace(
            config.strategy,
            fast_window=fast_window,
            slow_window=slow_window,
        )
        run_config = replace(config, strategy=strategy)
        run = run_research(run_config)
        runs.append(run)
        metrics = run.backtest.metrics.to_dict()
        rows.append(
            {
                "strategy_name": run_config.strategy.name,
                "fast_window": fast_window,
                "slow_window": slow_window,
                **metrics,
            }
        )

    return pd.DataFrame(rows), runs


def write_parameter_sweep_summary(
    summary: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(path, index=False)
    return path
