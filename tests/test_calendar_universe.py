from __future__ import annotations

import pandas as pd

from ashare_research.data.calendar import infer_trading_calendar, load_trading_calendar
from ashare_research.data.universe import load_universe_snapshot, universe_from_bars


def test_calendar_load_and_infer(tmp_path) -> None:
    calendar_path = tmp_path / "calendar.csv"
    pd.DataFrame({"date": ["2024-01-03", "2024-01-02", "2024-01-02"]}).to_csv(
        calendar_path,
        index=False,
    )
    loaded = load_trading_calendar(calendar_path)
    inferred = infer_trading_calendar(
        pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-03", "2024-01-02"]),
                "symbol": ["000001.SZ", "600000.SH"],
            }
        )
    )

    assert list(loaded.strftime("%Y-%m-%d")) == ["2024-01-02", "2024-01-03"]
    assert list(inferred.strftime("%Y-%m-%d")) == ["2024-01-02", "2024-01-03"]


def test_universe_load_and_infer(tmp_path) -> None:
    universe_path = tmp_path / "universe.csv"
    pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-02", "2024-01-02"],
            "symbol": ["000001.SZ", "000001.SZ", "600000.SH"],
        }
    ).to_csv(universe_path, index=False)

    loaded = load_universe_snapshot(universe_path)
    inferred = universe_from_bars(loaded)

    assert len(loaded) == 2
    assert len(inferred) == 2
    assert list(loaded["symbol"]) == ["000001.SZ", "600000.SH"]
