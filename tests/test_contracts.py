from __future__ import annotations

from ashare_research.contracts.schemas import (
    ALL_DATASET_SCHEMAS,
    BENCHMARK_RETURNS_SCHEMA,
    BENCHMARK_SOURCE_SCHEMA,
    BARS_SCHEMA,
    DAILY_BARS_SOURCE_SCHEMA,
    INDUSTRY_EXPOSURE_SCHEMA,
    RUNTIME_DATASET_SCHEMAS,
    SIGNALS_SCHEMA,
    SOURCE_DATASET_SCHEMAS,
    STRATEGY_ATTRIBUTION_SCHEMA,
    get_dataset_schema,
)
from ashare_research.data.benchmarks import REQUIRED_BENCHMARK_COLUMNS
from ashare_research.data.daily_bars import (
    OPTIONAL_DAILY_BAR_COLUMNS,
    REQUIRED_DAILY_BAR_COLUMNS,
)


def test_contract_registry_contains_all_official_structures() -> None:
    expected_source = {
        "daily_bars_csv",
        "benchmark_csv",
        "trading_calendar_csv",
        "universe_csv",
    }
    expected_runtime = {
        "bars",
        "benchmark_returns",
        "signals",
        "positions",
        "equity_curve",
        "drawdowns",
        "rolling_metrics",
        "monthly_returns",
        "industry_exposure",
        "strategy_attribution",
    }

    assert expected_source.issubset(SOURCE_DATASET_SCHEMAS)
    assert expected_runtime.issubset(RUNTIME_DATASET_SCHEMAS)
    assert expected_source.union(expected_runtime).issubset(ALL_DATASET_SCHEMAS)


def test_daily_bar_loader_columns_follow_contracts() -> None:
    assert REQUIRED_DAILY_BAR_COLUMNS == DAILY_BARS_SOURCE_SCHEMA.required_field_set
    assert OPTIONAL_DAILY_BAR_COLUMNS.issubset(BARS_SCHEMA.optional_field_set)
    assert {"raw_open", "raw_high", "raw_low", "raw_close"}.issubset(BARS_SCHEMA.optional_field_set)


def test_benchmark_loader_columns_follow_contracts() -> None:
    assert REQUIRED_BENCHMARK_COLUMNS == BENCHMARK_SOURCE_SCHEMA.required_field_set
    assert BENCHMARK_RETURNS_SCHEMA.required_field_set == {"date", "benchmark_return"}


def test_runtime_contracts_capture_current_semantics() -> None:
    assert SIGNALS_SCHEMA.required_field_set == {"date", "symbol", "signal"}
    assert "signal_strength" in SIGNALS_SCHEMA.optional_field_set
    assert INDUSTRY_EXPOSURE_SCHEMA.required_field_set == {"date", "group_name", "exposure"}
    contribution_field = next(
        field for field in STRATEGY_ATTRIBUTION_SCHEMA.fields if field.name == "contribution"
    )
    assert "not realized return contribution" in contribution_field.description


def test_get_dataset_schema_returns_schema_by_name() -> None:
    schema = get_dataset_schema("bars")

    assert schema.name == "bars"
    assert schema.primary_keys == ("date", "symbol")
