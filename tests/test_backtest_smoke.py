from __future__ import annotations

import pandas as pd

from ashare_research.analysis.reports import (
    build_drawdown_report,
    build_monthly_returns,
    build_rolling_metrics,
    write_research_report,
)
from ashare_research.backtest.engine import run_close_to_close_backtest
from ashare_research.strategies.moving_average import moving_average_crossover_signals


def test_moving_average_backtest_smoke() -> None:
    dates = pd.bdate_range("2024-01-01", periods=80)
    bars = pd.DataFrame(
        {
            "date": list(dates) * 2,
            "symbol": ["000001.SZ"] * len(dates) + ["600000.SH"] * len(dates),
            "open": [10.0 + index * 0.1 for index in range(len(dates))] * 2,
            "high": [10.2 + index * 0.1 for index in range(len(dates))] * 2,
            "low": [9.8 + index * 0.1 for index in range(len(dates))] * 2,
            "close": [10.0 + index * 0.1 for index in range(len(dates))] * 2,
            "volume": [1_000_000] * len(dates) * 2,
        }
    )

    signals = moving_average_crossover_signals(bars, fast_window=5, slow_window=20)
    benchmark_returns = pd.DataFrame(
        {
            "date": dates[:-1],
            "benchmark_return": [0.001] * (len(dates) - 1),
        }
    )
    result = run_close_to_close_backtest(
        bars,
        signals,
        max_names=2,
        benchmark_returns=benchmark_returns,
    )

    assert not result.equity_curve.empty
    assert result.metrics.trading_days > 0
    assert result.equity_curve["equity"].iloc[-1] > 0
    assert result.metrics.average_turnover >= 0.0
    assert result.metrics.benchmark_total_return > 0.0


def test_report_exports(tmp_path) -> None:
    equity_curve = pd.DataFrame(
        {
            "date": pd.bdate_range("2024-01-01", periods=3),
            "net_return": [0.01, -0.005, 0.002],
            "turnover": [1.0, 0.5, 0.0],
            "sell_turnover": [0.0, 0.25, 0.0],
            "equity": [1_010_000.0, 1_004_950.0, 1_006_959.9],
        }
    )
    benchmark_returns = pd.DataFrame(
        {
            "date": pd.bdate_range("2024-01-01", periods=3),
            "benchmark_return": [0.005, -0.001, 0.003],
        }
    )
    positions = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-01")],
            "symbol": ["000001.SZ"],
            "weight": [1.0],
        }
    )
    result = run_close_to_close_backtest(
        pd.DataFrame(
            {
                "date": pd.bdate_range("2024-01-01", periods=3),
                "symbol": ["000001.SZ"] * 3,
                "open": [10.0, 10.1, 10.2],
                "high": [10.1, 10.2, 10.3],
                "low": [9.9, 10.0, 10.1],
                "close": [10.0, 10.1, 10.2],
                "volume": [1_000_000] * 3,
            }
        ),
        pd.DataFrame(
            {
                "date": pd.bdate_range("2024-01-01", periods=3),
                "symbol": ["000001.SZ"] * 3,
                "signal": [1.0, 1.0, 1.0],
            }
        ),
        benchmark_returns=benchmark_returns,
    )
    monthly_returns = build_monthly_returns(equity_curve, benchmark_returns)
    drawdowns = build_drawdown_report(equity_curve)
    rolling_metrics = build_rolling_metrics(equity_curve, benchmark_returns, windows=(2,))
    paths = write_research_report(
        tmp_path,
        equity_curve,
        positions,
        result.metrics,
        benchmark_returns=benchmark_returns,
    )

    assert not monthly_returns.empty
    assert not drawdowns.empty
    assert not rolling_metrics.empty
    assert "rolling_2d_return" in rolling_metrics.columns
    assert drawdowns["drawdown"].min() <= 0.0
    assert paths.summary.exists()
    assert paths.equity_curve.exists()
    assert paths.drawdowns.exists()
    assert paths.rolling_metrics.exists()
    assert paths.monthly_returns.exists()
    assert paths.positions.exists()
