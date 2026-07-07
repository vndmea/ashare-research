from __future__ import annotations

import pandas as pd

from ashare_research.analysis.reports import (
    build_drawdown_report,
    build_industry_exposure_report,
    build_monthly_returns,
    build_rolling_metrics,
    write_research_report,
)
from ashare_research.analysis.attribution import build_strategy_attribution_report
from ashare_research.backtest.engine import run_close_to_close_backtest
from ashare_research.risk.position_sizing import (
    build_target_positions,
    equal_weight_positions,
    signal_weight_positions,
)
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
    assert "is_rebalance_day" in result.equity_curve.columns
    assert result.equity_curve["is_rebalance_day"].isin([0.0, 1.0]).all()
    assert "signal_strength" in signals.columns
    assert signals["signal_strength"].ge(0.0).all()


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
            "date": [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-01")],
            "symbol": ["000001.SZ", "600000.SH"],
            "weight": [0.4, 0.6],
        }
    )
    bars = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-01")],
            "symbol": ["000001.SZ", "600000.SH"],
            "industry": ["Bank", "Broker"],
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
    industry_exposure = build_industry_exposure_report(positions, bars)
    strategy_attribution = build_strategy_attribution_report(positions, bars, equity_curve)
    paths = write_research_report(
        tmp_path,
        equity_curve,
        positions,
        result.metrics,
        bars=bars,
        benchmark_returns=benchmark_returns,
    )

    assert not monthly_returns.empty
    assert not drawdowns.empty
    assert not rolling_metrics.empty
    assert not industry_exposure.empty
    assert not strategy_attribution.empty
    assert "rolling_2d_return" in rolling_metrics.columns
    assert industry_exposure["group_name"].tolist() == ["Broker", "Bank"]
    assert "source" in strategy_attribution.columns
    assert drawdowns["drawdown"].min() <= 0.0
    assert paths.summary.exists()
    assert paths.equity_curve.exists()
    assert paths.drawdowns.exists()
    assert paths.rolling_metrics.exists()
    assert paths.monthly_returns.exists()
    assert paths.industry_exposure.exists()
    assert paths.strategy_attribution.exists()
    assert paths.positions.exists()


def test_equal_weight_positions_prefers_stronger_signals() -> None:
    signals = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-02")] * 3,
            "symbol": ["000001.SZ", "600000.SH", "000002.SZ"],
            "signal": [1.0, 1.0, 1.0],
            "signal_strength": [0.01, 0.03, 0.02],
        }
    )

    positions = equal_weight_positions(signals, max_names=2)

    assert list(positions["symbol"]) == ["000002.SZ", "600000.SH"]
    assert positions["weight"].tolist() == [0.5, 0.5]


def test_signal_weight_positions_use_signal_strength() -> None:
    signals = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-02")] * 3,
            "symbol": ["000001.SZ", "600000.SH", "000002.SZ"],
            "signal": [1.0, 1.0, 1.0],
            "signal_strength": [0.01, 0.03, 0.02],
        }
    )

    positions = signal_weight_positions(signals, max_names=2)

    assert list(positions["symbol"]) == ["000002.SZ", "600000.SH"]
    assert positions["weight"].round(4).tolist() == [0.4, 0.6]


def test_build_target_positions_supports_signal_weight() -> None:
    signals = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-02")] * 2,
            "symbol": ["000001.SZ", "600000.SH"],
            "signal": [1.0, 1.0],
            "signal_strength": [0.02, 0.08],
        }
    )

    positions = build_target_positions(signals, max_names=2, method="signal_weight")

    assert positions["weight"].round(4).tolist() == [0.2, 0.8]


def test_backtest_supports_signal_weight_position_sizing() -> None:
    dates = pd.bdate_range("2024-01-01", periods=4)
    bars = pd.DataFrame(
        {
            "date": list(dates) * 2,
            "symbol": ["000001.SZ"] * len(dates) + ["600000.SH"] * len(dates),
            "open": [10.0, 10.2, 10.4, 10.6] + [20.0, 20.4, 20.8, 21.2],
            "high": [10.1, 10.3, 10.5, 10.7] + [20.1, 20.5, 20.9, 21.3],
            "low": [9.9, 10.1, 10.3, 10.5] + [19.9, 20.3, 20.7, 21.1],
            "close": [10.0, 10.2, 10.4, 10.6] + [20.0, 20.4, 20.8, 21.2],
            "volume": [1_000_000] * len(dates) * 2,
        }
    )
    signals = pd.DataFrame(
        {
            "date": list(dates) * 2,
            "symbol": ["000001.SZ"] * len(dates) + ["600000.SH"] * len(dates),
            "signal": [1.0] * len(dates) * 2,
            "signal_strength": [0.02] * len(dates) + [0.08] * len(dates),
        }
    )

    result = run_close_to_close_backtest(
        bars,
        signals,
        max_names=2,
        position_sizing_method="signal_weight",
    )

    first_day = result.positions[result.positions["date"] == dates[0]].sort_values("symbol")
    assert first_day["weight"].round(4).tolist() == [0.2, 0.8]
