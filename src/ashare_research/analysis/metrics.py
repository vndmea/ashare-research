from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True)
class PerformanceMetrics:
    total_return: float
    annual_return: float
    annual_volatility: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    average_turnover: float
    benchmark_total_return: float
    benchmark_annual_return: float
    excess_annual_return: float
    information_ratio: float
    average_gross_exposure: float
    average_cash_weight: float
    trading_days: int

    def to_dict(self) -> dict[str, float | int]:
        return asdict(self)


def calculate_metrics(
    equity_curve: pd.DataFrame,
    initial_cash: float,
    benchmark_returns: pd.DataFrame | None = None,
) -> PerformanceMetrics:
    if equity_curve.empty:
        return PerformanceMetrics(
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0,
        )

    returns = equity_curve["net_return"].fillna(0.0)
    ending_equity = float(equity_curve["equity"].iloc[-1])
    total_return = ending_equity / initial_cash - 1.0
    trading_days = len(equity_curve)
    annual_return = _annualize_return(total_return, trading_days)
    annual_volatility = float(returns.std(ddof=0) * np.sqrt(TRADING_DAYS_PER_YEAR))
    sharpe_ratio = annual_return / annual_volatility if annual_volatility > 0 else 0.0
    drawdown = equity_curve["equity"].div(equity_curve["equity"].cummax()).sub(1.0)
    max_drawdown = float(drawdown.min())
    win_rate = float((returns > 0.0).mean())
    average_turnover = _average_turnover(equity_curve)
    average_gross_exposure = _average_gross_exposure(equity_curve)
    average_cash_weight = _average_cash_weight(equity_curve)
    benchmark_stats = _benchmark_stats(equity_curve, benchmark_returns)

    return PerformanceMetrics(
        total_return=float(total_return),
        annual_return=float(annual_return),
        annual_volatility=annual_volatility,
        sharpe_ratio=float(sharpe_ratio),
        max_drawdown=max_drawdown,
        win_rate=win_rate,
        average_turnover=average_turnover,
        benchmark_total_return=benchmark_stats["benchmark_total_return"],
        benchmark_annual_return=benchmark_stats["benchmark_annual_return"],
        excess_annual_return=benchmark_stats["excess_annual_return"],
        information_ratio=benchmark_stats["information_ratio"],
        average_gross_exposure=average_gross_exposure,
        average_cash_weight=average_cash_weight,
        trading_days=trading_days,
    )


def _annualize_return(total_return: float, trading_days: int) -> float:
    if trading_days <= 0:
        return 0.0
    if total_return <= -1.0:
        return -1.0
    return float((1.0 + total_return) ** (TRADING_DAYS_PER_YEAR / trading_days) - 1.0)


def _average_turnover(equity_curve: pd.DataFrame) -> float:
    if "turnover" not in equity_curve:
        return 0.0
    return float(equity_curve["turnover"].fillna(0.0).mean())


def _average_gross_exposure(equity_curve: pd.DataFrame) -> float:
    if "gross_exposure" not in equity_curve:
        return 0.0
    return float(equity_curve["gross_exposure"].fillna(0.0).mean())


def _average_cash_weight(equity_curve: pd.DataFrame) -> float:
    if "cash_weight" not in equity_curve:
        return 0.0
    return float(equity_curve["cash_weight"].fillna(0.0).mean())


def _benchmark_stats(
    equity_curve: pd.DataFrame,
    benchmark_returns: pd.DataFrame | None,
) -> dict[str, float]:
    empty_stats = {
        "benchmark_total_return": 0.0,
        "benchmark_annual_return": 0.0,
        "excess_annual_return": 0.0,
        "information_ratio": 0.0,
    }
    if benchmark_returns is None or benchmark_returns.empty:
        return empty_stats

    aligned = equity_curve[["date", "net_return"]].merge(
        benchmark_returns[["date", "benchmark_return"]],
        on="date",
        how="inner",
    )
    if aligned.empty:
        return empty_stats

    strategy_total_return = float((1.0 + aligned["net_return"]).prod() - 1.0)
    benchmark_total_return = float((1.0 + aligned["benchmark_return"]).prod() - 1.0)
    strategy_annual_return = _annualize_return(strategy_total_return, len(aligned))
    benchmark_annual_return = _annualize_return(benchmark_total_return, len(aligned))
    excess_returns = aligned["net_return"] - aligned["benchmark_return"]
    tracking_error = float(excess_returns.std(ddof=0) * np.sqrt(TRADING_DAYS_PER_YEAR))
    information_ratio = (
        float(excess_returns.mean() * TRADING_DAYS_PER_YEAR / tracking_error)
        if tracking_error > 0.0
        else 0.0
    )

    return {
        "benchmark_total_return": benchmark_total_return,
        "benchmark_annual_return": benchmark_annual_return,
        "excess_annual_return": strategy_annual_return - benchmark_annual_return,
        "information_ratio": information_ratio,
    }
