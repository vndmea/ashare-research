from __future__ import annotations

from pathlib import Path

import pandas as pd

REQUIRED_BENCHMARK_COLUMNS = {"date", "close"}


def load_benchmark_returns(
    path: str | Path,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    """Load benchmark closes and convert them into next-day close returns."""
    data_path = Path(path)
    benchmark = pd.read_csv(data_path, parse_dates=["date"])
    validate_benchmark_bars(benchmark)

    benchmark = benchmark.sort_values("date").reset_index(drop=True)
    if start_date is not None:
        benchmark = benchmark[benchmark["date"] >= pd.Timestamp(start_date)]
    if end_date is not None:
        benchmark = benchmark[benchmark["date"] <= pd.Timestamp(end_date)]

    benchmark["next_close"] = benchmark["close"].shift(-1)
    benchmark["benchmark_return"] = benchmark["next_close"].div(benchmark["close"]).sub(1.0)
    return benchmark[["date", "benchmark_return"]].dropna().reset_index(drop=True)


def validate_benchmark_bars(benchmark: pd.DataFrame) -> None:
    missing = REQUIRED_BENCHMARK_COLUMNS.difference(benchmark.columns)
    if missing:
        raise ValueError(f"Benchmark data is missing required columns: {sorted(missing)}")

    if benchmark.empty:
        raise ValueError("Benchmark data is empty.")

    duplicated = benchmark.duplicated(["date"])
    if duplicated.any():
        sample = benchmark.loc[duplicated, ["date"]].head().to_dict("records")
        raise ValueError(f"Benchmark data contains duplicate dates: {sample}")
