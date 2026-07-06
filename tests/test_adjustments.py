from __future__ import annotations

import pandas as pd
import pytest

from ashare_research.data.adjustments import (
    apply_price_adjustment,
    load_adjustment_factors,
    merge_adjustment_factors,
)
from ashare_research.data.daily_bars import coerce_daily_bar_types, load_daily_bars


def test_forward_adjustment_uses_latest_factor() -> None:
    bars = _bars()

    adjusted = apply_price_adjustment(bars, mode="forward")

    assert list(adjusted["close"].round(4)) == [5.0, 5.0, 6.0]
    assert list(adjusted["raw_close"]) == [10.0, 5.0, 6.0]
    assert adjusted["price_adjustment"].unique().tolist() == ["forward"]


def test_backward_adjustment_uses_first_factor() -> None:
    bars = _bars()

    adjusted = apply_price_adjustment(bars, mode="backward")

    assert list(adjusted["close"].round(4)) == [10.0, 10.0, 12.0]
    assert list(adjusted["raw_close"]) == [10.0, 5.0, 6.0]


def test_load_daily_bars_with_external_adjustment_factors(tmp_path) -> None:
    bars = _bars().drop(columns=["adj_factor"])
    bars_path = tmp_path / "daily_bars.csv"
    factors_path = tmp_path / "adjustment_factors.csv"
    bars.to_csv(bars_path, index=False)
    _bars()[["date", "symbol", "adj_factor"]].to_csv(factors_path, index=False)

    adjusted = load_daily_bars(
        bars_path,
        price_adjustment="forward",
        adjustment_factor_path=factors_path,
    )

    assert list(adjusted["close"].round(4)) == [5.0, 5.0, 6.0]
    assert "raw_close" in adjusted.columns


def test_merge_adjustment_factors_requires_complete_factor_rows() -> None:
    bars = _bars().drop(columns=["adj_factor"])
    factors = _bars().iloc[:2][["date", "symbol", "adj_factor"]]

    with pytest.raises(ValueError, match="Missing adjustment factors"):
        merge_adjustment_factors(bars, factors)


def test_load_adjustment_factors_rejects_invalid_factor(tmp_path) -> None:
    factors_path = tmp_path / "adjustment_factors.csv"
    pd.DataFrame(
        {
            "date": ["2024-01-01"],
            "symbol": ["000001.SZ"],
            "adj_factor": [0.0],
        }
    ).to_csv(factors_path, index=False)

    with pytest.raises(ValueError, match="must be positive"):
        load_adjustment_factors(factors_path)


def test_coerce_daily_bars_preserves_industry_and_sector_columns() -> None:
    bars = _bars().assign(industry="Bank", sector="Financials")

    coerced = coerce_daily_bar_types(bars)

    assert "industry" in coerced.columns
    assert "sector" in coerced.columns
    assert coerced["industry"].tolist() == ["Bank", "Bank", "Bank"]


def _bars() -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-01", periods=3)
    return pd.DataFrame(
        {
            "date": dates,
            "symbol": ["000001.SZ"] * 3,
            "open": [10.0, 5.0, 6.0],
            "high": [10.5, 5.2, 6.2],
            "low": [9.8, 4.8, 5.8],
            "close": [10.0, 5.0, 6.0],
            "volume": [1_000_000] * 3,
            "adj_factor": [1.0, 2.0, 2.0],
        }
    )
