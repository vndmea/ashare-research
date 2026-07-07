from __future__ import annotations

import pandas as pd

from ashare_research.data.baostock import normalize_baostock_daily_bars


def test_normalize_baostock_daily_bars() -> None:
    raw = pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-03"],
            "symbol": ["sh.600000", "sz.000001"],
            "open": ["10.0", "10.5"],
            "high": ["10.2", "10.8"],
            "low": ["9.8", "10.1"],
            "close": ["10.1", "10.6"],
            "volume": ["1000000", "1100000"],
            "amount": ["10100000", "11660000"],
        }
    )

    bars = normalize_baostock_daily_bars(raw)

    assert list(bars.columns) == [
        "date",
        "symbol",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
    ]
    assert bars.loc[0, "symbol"] == "600000.SH"
    assert bars.loc[1, "symbol"] == "000001.SZ"
    assert bars.loc[0, "volume"] == 1_000_000
