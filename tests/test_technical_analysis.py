from __future__ import annotations

import pandas as pd

from ashare_research.analysis.technical import build_symbol_technical_analysis_report
from ashare_research.config import TechnicalAnalysisConfig


def test_build_symbol_technical_analysis_report_scores_symbols() -> None:
    dates = pd.bdate_range("2024-01-01", periods=280)
    strong_close = [50 + index * 0.5 for index in range(len(dates))]
    weak_close = [120 - index * 0.2 for index in range(len(dates))]

    strong = pd.DataFrame(
        {
            "date": dates,
            "symbol": ["300059.SZ"] * len(dates),
            "close": strong_close,
            "volume": [3_000_000 + index * 10_000 for index in range(len(dates))],
            "amount": [(3_000_000 + index * 10_000) * strong_close[index] for index in range(len(dates))],
        }
    )
    weak = pd.DataFrame(
        {
            "date": dates,
            "symbol": ["603589.SH"] * len(dates),
            "close": weak_close,
            "volume": [5_000_000 - index * 5_000 for index in range(len(dates))],
            "amount": [max(1_000_000, (5_000_000 - index * 5_000) * weak_close[index]) for index in range(len(dates))],
        }
    )
    bars = pd.concat([strong, weak], ignore_index=True)
    benchmark_returns = pd.DataFrame(
        {
            "date": dates,
            "benchmark_return": [0.0005] * len(dates),
        }
    )

    report = build_symbol_technical_analysis_report(
        bars,
        TechnicalAnalysisConfig(symbols=("300059.SZ", "603589.SH")),
        benchmark_returns=benchmark_returns,
    )

    assert list(report["symbol"]) == ["300059.SZ", "603589.SH"]
    assert report.loc[report["symbol"] == "300059.SZ", "decision"].iloc[0] == "buy"
    assert report.loc[report["symbol"] == "603589.SH", "decision"].iloc[0] == "sell"
    assert report.loc[report["symbol"] == "300059.SZ", "total_score"].iloc[0] > report.loc[
        report["symbol"] == "603589.SH", "total_score"
    ].iloc[0]


def test_build_symbol_technical_analysis_report_rejects_missing_symbols() -> None:
    bars = pd.DataFrame(
        {
            "date": pd.bdate_range("2024-01-01", periods=5),
            "symbol": ["300059.SZ"] * 5,
            "close": [10, 10.2, 10.4, 10.6, 10.8],
            "volume": [1_000_000] * 5,
            "amount": [10_000_000] * 5,
        }
    )

    try:
        build_symbol_technical_analysis_report(
            bars,
            TechnicalAnalysisConfig(symbols=("603986.SH",)),
        )
    except ValueError as exc:
        assert "symbols not present in bars" in str(exc)
    else:
        raise AssertionError("Expected missing symbol validation to fail.")
