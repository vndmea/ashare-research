from __future__ import annotations

import pandas as pd
import pytest

from ashare_research.data.benchmarks import load_benchmark_returns
from ashare_research.data.calendar import load_trading_calendar
from ashare_research.data.daily_bars import load_daily_bars
from ashare_research.data.universe import load_universe_snapshot


def test_load_daily_bars_rejects_non_positive_prices(tmp_path) -> None:
    bars = _daily_bars()
    bars.loc[0, "close"] = 0.0
    path = tmp_path / "daily_bars.csv"
    bars.to_csv(path, index=False)

    with pytest.raises(ValueError, match="daily_bars_csv.close must be positive"):
        load_daily_bars(path)


def test_load_daily_bars_rejects_blank_symbol(tmp_path) -> None:
    bars = _daily_bars()
    bars.loc[0, "symbol"] = " "
    path = tmp_path / "daily_bars.csv"
    bars.to_csv(path, index=False)

    with pytest.raises(ValueError, match="daily_bars_csv.symbol contains blank values"):
        load_daily_bars(path)


def test_load_benchmark_returns_rejects_non_positive_close(tmp_path) -> None:
    benchmark = pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-03"],
            "close": [100.0, -1.0],
        }
    )
    path = tmp_path / "benchmark.csv"
    benchmark.to_csv(path, index=False)

    with pytest.raises(ValueError, match="benchmark_csv.close must be positive"):
        load_benchmark_returns(path)


def test_load_trading_calendar_rejects_invalid_dates(tmp_path) -> None:
    calendar = pd.DataFrame({"date": ["2024-01-02", "not-a-date"]})
    path = tmp_path / "calendar.csv"
    calendar.to_csv(path, index=False)

    with pytest.raises(ValueError, match="trading_calendar_csv.date contains null values"):
        load_trading_calendar(path)


def test_load_universe_snapshot_rejects_blank_symbol(tmp_path) -> None:
    universe = pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-02"],
            "symbol": ["000001.SZ", ""],
        }
    )
    path = tmp_path / "universe.csv"
    universe.to_csv(path, index=False)

    with pytest.raises(ValueError, match="universe_csv.symbol contains null values"):
        load_universe_snapshot(path)


def _daily_bars() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-03"],
            "symbol": ["000001.SZ", "000001.SZ"],
            "open": [10.0, 10.5],
            "high": [10.2, 10.8],
            "low": [9.8, 10.1],
            "close": [10.1, 10.6],
            "volume": [1_000_000, 1_100_000],
        }
    )
