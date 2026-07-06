from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from ashare_research.analysis.metrics import PerformanceMetrics

ROLLING_WINDOWS = (20, 60)


@dataclass(frozen=True)
class ReportPaths:
    summary: Path
    equity_curve: Path
    drawdowns: Path
    rolling_metrics: Path
    monthly_returns: Path
    industry_exposure: Path
    positions: Path


def build_drawdown_report(equity_curve: pd.DataFrame) -> pd.DataFrame:
    """Build a daily drawdown report from the equity curve."""
    columns = ["date", "equity", "peak_equity", "drawdown", "is_new_high", "underwater_days"]
    if equity_curve.empty:
        return pd.DataFrame(columns=columns)

    drawdowns = equity_curve[["date", "equity"]].copy()
    drawdowns["peak_equity"] = drawdowns["equity"].cummax()
    drawdowns["drawdown"] = drawdowns["equity"].div(drawdowns["peak_equity"]).sub(1.0)
    drawdowns["is_new_high"] = drawdowns["equity"].eq(drawdowns["peak_equity"])
    reset_groups = drawdowns["is_new_high"].cumsum()
    drawdowns["underwater_days"] = (
        (~drawdowns["is_new_high"]).astype(int).groupby(reset_groups).cumsum()
    )
    return drawdowns


def build_rolling_metrics(
    equity_curve: pd.DataFrame,
    benchmark_returns: pd.DataFrame | None = None,
    windows: tuple[int, ...] = ROLLING_WINDOWS,
) -> pd.DataFrame:
    """Build rolling-window strategy diagnostics."""
    columns = ["date"]
    for window in windows:
        columns.extend(
            [
                f"rolling_{window}d_return",
                f"rolling_{window}d_volatility",
                f"rolling_{window}d_sharpe",
            ]
        )
        if benchmark_returns is not None and not benchmark_returns.empty:
            columns.append(f"rolling_{window}d_excess_return")
    if equity_curve.empty:
        return pd.DataFrame(columns=columns)

    rolling = equity_curve[["date", "net_return"]].copy()
    benchmark = None
    if benchmark_returns is not None and not benchmark_returns.empty:
        benchmark = benchmark_returns[["date", "benchmark_return"]].copy()
        rolling = rolling.merge(benchmark, on="date", how="left")

    for window in windows:
        rolling[f"rolling_{window}d_return"] = _rolling_compound_return(
            rolling["net_return"],
            window,
        )
        rolling[f"rolling_{window}d_volatility"] = (
            rolling["net_return"].rolling(window).std(ddof=0) * np.sqrt(252)
        )
        rolling[f"rolling_{window}d_sharpe"] = _rolling_sharpe(
            rolling["net_return"],
            rolling[f"rolling_{window}d_volatility"],
            window,
        )
        if benchmark is not None:
            rolling[f"rolling_{window}d_excess_return"] = rolling[
                f"rolling_{window}d_return"
            ] - _rolling_compound_return(rolling["benchmark_return"], window)

    ordered_columns = [column for column in columns if column in rolling.columns]
    return rolling[ordered_columns]


def build_monthly_returns(
    equity_curve: pd.DataFrame,
    benchmark_returns: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build strategy and benchmark monthly return tables."""
    if equity_curve.empty:
        columns = ["month", "strategy_return"]
        if benchmark_returns is not None and not benchmark_returns.empty:
            columns.extend(["benchmark_return", "excess_return"])
        return pd.DataFrame(columns=columns)

    strategy = equity_curve[["date", "net_return"]].copy()
    strategy["month"] = strategy["date"].dt.to_period("M").astype(str)
    monthly = strategy.groupby("month", as_index=False).agg(
        strategy_return=("net_return", lambda series: (1.0 + series).prod() - 1.0)
    )

    if benchmark_returns is None or benchmark_returns.empty:
        return monthly

    benchmark = benchmark_returns[["date", "benchmark_return"]].copy()
    benchmark["month"] = benchmark["date"].dt.to_period("M").astype(str)
    benchmark_monthly = benchmark.groupby("month", as_index=False).agg(
        benchmark_return=("benchmark_return", lambda series: (1.0 + series).prod() - 1.0)
    )
    monthly = monthly.merge(benchmark_monthly, on="month", how="left")
    monthly["excess_return"] = monthly["strategy_return"] - monthly["benchmark_return"]
    return monthly


def build_industry_exposure_report(
    positions: pd.DataFrame,
    bars: pd.DataFrame,
) -> pd.DataFrame:
    """Build daily industry or sector exposure from position weights."""
    if positions.empty:
        return pd.DataFrame(columns=["date", "group_name", "exposure"])

    group_column = _group_column(bars)
    if group_column is None:
        return pd.DataFrame(columns=["date", "group_name", "exposure"])

    exposure = positions.merge(
        bars[["date", "symbol", group_column]].drop_duplicates(),
        on=["date", "symbol"],
        how="left",
    )
    exposure["group_name"] = exposure[group_column].fillna("").replace("", "Unclassified")
    report = exposure.groupby(["date", "group_name"], as_index=False).agg(exposure=("weight", "sum"))
    return report.sort_values(["date", "exposure", "group_name"], ascending=[True, False, True]).reset_index(drop=True)


def write_research_report(
    output_dir: str | Path,
    equity_curve: pd.DataFrame,
    positions: pd.DataFrame,
    metrics: PerformanceMetrics,
    bars: pd.DataFrame | None = None,
    benchmark_returns: pd.DataFrame | None = None,
) -> ReportPaths:
    """Write summary, equity, drawdown, rolling, monthly, exposure, and position CSV reports."""
    report_dir = Path(output_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    summary_path = report_dir / "summary.csv"
    equity_curve_path = report_dir / "equity_curve.csv"
    drawdowns_path = report_dir / "drawdowns.csv"
    rolling_metrics_path = report_dir / "rolling_metrics.csv"
    monthly_returns_path = report_dir / "monthly_returns.csv"
    industry_exposure_path = report_dir / "industry_exposure.csv"
    positions_path = report_dir / "positions.csv"

    pd.DataFrame([metrics.to_dict()]).to_csv(summary_path, index=False)
    _equity_curve_with_benchmark(equity_curve, benchmark_returns).to_csv(
        equity_curve_path,
        index=False,
    )
    build_drawdown_report(equity_curve).to_csv(drawdowns_path, index=False)
    build_rolling_metrics(equity_curve, benchmark_returns).to_csv(
        rolling_metrics_path,
        index=False,
    )
    build_monthly_returns(equity_curve, benchmark_returns).to_csv(monthly_returns_path, index=False)
    build_industry_exposure_report(positions, bars if bars is not None else pd.DataFrame()).to_csv(
        industry_exposure_path,
        index=False,
    )
    positions.to_csv(positions_path, index=False)

    return ReportPaths(
        summary=summary_path,
        equity_curve=equity_curve_path,
        drawdowns=drawdowns_path,
        rolling_metrics=rolling_metrics_path,
        monthly_returns=monthly_returns_path,
        industry_exposure=industry_exposure_path,
        positions=positions_path,
    )


def _equity_curve_with_benchmark(
    equity_curve: pd.DataFrame,
    benchmark_returns: pd.DataFrame | None,
) -> pd.DataFrame:
    if benchmark_returns is None or benchmark_returns.empty:
        return equity_curve
    return equity_curve.merge(benchmark_returns, on="date", how="left")


def _rolling_compound_return(series: pd.Series, window: int) -> pd.Series:
    return series.fillna(0.0).rolling(window).apply(lambda values: np.prod(1.0 + values) - 1.0, raw=True)


def _rolling_sharpe(
    returns: pd.Series,
    volatility: pd.Series,
    window: int,
) -> pd.Series:
    annualized_mean = returns.fillna(0.0).rolling(window).mean() * 252
    sharpe = annualized_mean.div(volatility.replace(0.0, np.nan))
    return sharpe.replace([np.inf, -np.inf], np.nan)


def _group_column(bars: pd.DataFrame) -> str | None:
    for column in ["industry", "sector"]:
        if column in bars.columns:
            return column
    return None
