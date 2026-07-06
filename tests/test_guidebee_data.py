from __future__ import annotations

import pandas as pd

from ashare_research.data import guidebee


def test_build_guidebee_daily_url() -> None:
    url = guidebee.build_guidebee_daily_url("2026-03-11")

    assert url == (
        "https://raw.githubusercontent.com/guidebee/china-stock-data/main/data/price/"
        "2026/03/stock_price_2026_03_11.csv"
    )


def test_normalize_guidebee_daily_bars_filters_b_shares() -> None:
    raw = pd.DataFrame(
        [
            ["sh600000", "2026-03-11", 9.97, 10.06, 10.08, 9.85, 52840837, 526976400.46],
            ["sz000001", "2026-03-11", 10.82, 10.85, 10.91, 10.76, 104882300, 1137291048.5],
            ["sh900901", "2026-03-11", 1.2, 1.21, 1.22, 1.18, 1000, 1200.0],
        ],
        columns=guidebee.GUIDEBEE_SOURCE_COLUMNS,
    )

    normalized = guidebee.normalize_guidebee_daily_bars(raw)

    assert list(normalized["symbol"]) == ["000001.SZ", "600000.SH"]
    assert list(normalized.columns) == guidebee.GUIDEBEE_OUTPUT_COLUMNS
    assert str(normalized["date"].dtype).startswith("datetime64")


def test_download_guidebee_daily_bars_aggregates(monkeypatch) -> None:
    raw = pd.DataFrame(
        [
            ["sh600000", "2026-03-11", 9.97, 10.06, 10.08, 9.85, 52840837, 526976400.46],
            ["sz000001", "2026-03-12", 10.82, 10.85, 10.91, 10.76, 104882300, 1137291048.5],
        ],
        columns=guidebee.GUIDEBEE_SOURCE_COLUMNS,
    )
    day1 = guidebee.normalize_guidebee_daily_bars(raw.iloc[[0]])
    day2 = guidebee.normalize_guidebee_daily_bars(raw.iloc[[1]])

    def fake_fetch(trading_date, **kwargs):
        date_text = pd.Timestamp(trading_date).strftime("%Y-%m-%d")
        if date_text == "2026-03-11":
            return day1
        if date_text == "2026-03-12":
            return day2
        return None

    monkeypatch.setattr(guidebee, "fetch_guidebee_daily_bars", fake_fetch)

    bars = guidebee.download_guidebee_daily_bars(
        "2026-03-11",
        "2026-03-12",
        max_workers=1,
    )

    assert len(bars) == 2
    assert list(bars["symbol"]) == ["600000.SH", "000001.SZ"]
