from __future__ import annotations

from pathlib import Path

import pandas as pd

from ashare_research.contracts.schemas import BENCHMARK_SOURCE_SCHEMA
from ashare_research.contracts.validation import (
    validate_columns_not_null,
    validate_non_empty_frame,
    validate_numeric_column_positive,
    validate_primary_keys_unique,
    validate_required_columns,
    validate_string_column_not_blank,
)

REQUIRED_BENCHMARK_COLUMNS = BENCHMARK_SOURCE_SCHEMA.required_field_set


def load_benchmark_returns(
    path: str | Path,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    """Load benchmark closes and convert them into next-day close returns."""
    data_path = Path(path)
    benchmark = pd.read_csv(data_path, parse_dates=["date"])
    benchmark["date"] = pd.to_datetime(benchmark["date"], errors="coerce")
    if "close" in benchmark.columns:
        benchmark["close"] = pd.to_numeric(benchmark["close"], errors="coerce")
    if "symbol" in benchmark.columns:
        benchmark["symbol"] = benchmark["symbol"].astype("string").str.strip()
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
    validate_required_columns(benchmark, BENCHMARK_SOURCE_SCHEMA)
    validate_non_empty_frame(benchmark, BENCHMARK_SOURCE_SCHEMA)
    validate_primary_keys_unique(benchmark, BENCHMARK_SOURCE_SCHEMA)
    validate_columns_not_null(benchmark, BENCHMARK_SOURCE_SCHEMA, ["date", "close"])
    validate_numeric_column_positive(benchmark, BENCHMARK_SOURCE_SCHEMA, "close")
    if "symbol" in benchmark.columns:
        validate_string_column_not_blank(benchmark, BENCHMARK_SOURCE_SCHEMA, "symbol")
