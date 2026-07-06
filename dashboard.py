from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from ashare_research.analysis.reports import write_research_report
from ashare_research.backtest.engine import run_close_to_close_backtest
from ashare_research.config import load_config
from ashare_research.data.benchmarks import load_benchmark_returns
from ashare_research.data.calendar import load_trading_calendar
from ashare_research.data.daily_bars import load_daily_bars
from ashare_research.data.universe import load_universe_snapshot
from ashare_research.risk.tradeability import TradeConstraints
from ashare_research.strategies.moving_average import moving_average_crossover_signals

APP_TITLE = "A-share Research Dashboard"
DEFAULT_CONFIG_PATH = "configs/backtest.yaml"
DEFAULT_INITIAL_CASH = 1_000_000.0


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide", initial_sidebar_state="expanded")
    st.title(APP_TITLE)
    st.caption("Run the example research pipeline and inspect the generated reports.")

    with st.sidebar:
        st.header("Controls")
        config_path = st.text_input("Config file", DEFAULT_CONFIG_PATH)
        config = _read_config(config_path)
        default_report_dir = str(config.get("report", {}).get("output_dir", "reports/example_run"))
        report_dir = st.text_input("Report directory", default_report_dir)
        run_clicked = st.button("Run example backtest", type="primary", use_container_width=True)
        st.divider()
        st.subheader("Config preview")
        if config:
            st.json(config, expanded=False)
        else:
            st.info("No config loaded.")

    if run_clicked:
        with st.spinner("Running backtest and writing reports..."):
            report_dir = _run_example_backtest(config_path, report_dir)
        st.success(f"Reports written to {report_dir}")

    report = _load_report_bundle(report_dir)
    if report is None:
        _render_empty_state(report_dir)
        return

    _render_metrics(report["summary"])

    tab_equity, tab_risk, tab_monthly, tab_positions, tab_files = st.tabs(
        ["Equity", "Risk", "Monthly", "Positions", "Files"]
    )

    with tab_equity:
        _render_equity_section(report["equity_curve"], report["drawdowns"], config)

    with tab_risk:
        _render_risk_section(report["drawdowns"], report["rolling_metrics"])

    with tab_monthly:
        _render_monthly_section(report["monthly_returns"])

    with tab_positions:
        _render_positions_section(report["positions"])

    with tab_files:
        _render_files_section(report["paths"])


def _run_example_backtest(config_path: str, output_dir: str) -> str:
    config = _read_config(config_path)
    if not config:
        raise FileNotFoundError(f"Config file not found: {config_path}")

    start_date = config["backtest"].get("start_date")
    end_date = config["backtest"].get("end_date")
    bars = load_daily_bars(
        config["data"]["daily_bar_path"],
        start_date=start_date,
        end_date=end_date,
        price_adjustment=config.get("data", {}).get("price_adjustment", "none"),
        adjustment_factor_path=config.get("data", {}).get("adjustment_factor_path"),
    )
    trading_calendar = _load_optional_calendar(config)
    universe = _load_optional_universe(config)
    benchmark_returns = _load_optional_benchmark(config, start_date=start_date, end_date=end_date)
    signals = moving_average_crossover_signals(
        bars,
        fast_window=int(config["strategy"].get("fast_window", 20)),
        slow_window=int(config["strategy"].get("slow_window", 60)),
    )
    result = run_close_to_close_backtest(
        bars,
        signals,
        initial_cash=float(config["backtest"].get("initial_cash", DEFAULT_INITIAL_CASH)),
        commission_rate=float(config["backtest"].get("commission_rate", 0.0003)),
        stamp_tax_rate=float(config["backtest"].get("stamp_tax_rate", 0.0005)),
        max_names=int(config["backtest"].get("max_names", 20)),
        benchmark_returns=benchmark_returns,
        trading_calendar=trading_calendar,
        universe=universe,
        trade_constraints=_load_trade_constraints(config),
    )
    write_research_report(
        output_dir,
        result.equity_curve,
        result.positions,
        result.metrics,
        benchmark_returns=benchmark_returns,
    )
    return output_dir


def _load_optional_benchmark(
    config: dict[str, Any],
    start_date: str | None,
    end_date: str | None,
) -> pd.DataFrame | None:
    benchmark_path = config.get("data", {}).get("benchmark_path")
    if not benchmark_path:
        return None
    return load_benchmark_returns(benchmark_path, start_date=start_date, end_date=end_date)


def _load_optional_calendar(config: dict[str, Any]) -> pd.DatetimeIndex | None:
    calendar_path = config.get("data", {}).get("trading_calendar_path")
    if not calendar_path or not Path(calendar_path).exists():
        return None
    return load_trading_calendar(calendar_path)


def _load_optional_universe(config: dict[str, Any]) -> pd.DataFrame | None:
    universe_path = config.get("data", {}).get("universe_path")
    if not universe_path or not Path(universe_path).exists():
        return None
    return load_universe_snapshot(universe_path)


def _load_trade_constraints(config: dict[str, Any]) -> TradeConstraints:
    backtest = config.get("backtest", {})
    return TradeConstraints(
        exclude_suspended=bool(backtest.get("exclude_suspended", True)),
        exclude_st=bool(backtest.get("exclude_st", True)),
        block_limit_up_buys=bool(backtest.get("block_limit_up_buys", True)),
        block_limit_down_sells=bool(backtest.get("block_limit_down_sells", True)),
        min_amount=float(backtest.get("min_amount", 0.0)),
    )


def _load_report_bundle(output_dir: str) -> dict[str, Any] | None:
    report_dir = Path(output_dir)
    summary_path = report_dir / "summary.csv"
    equity_path = report_dir / "equity_curve.csv"
    drawdowns_path = report_dir / "drawdowns.csv"
    rolling_metrics_path = report_dir / "rolling_metrics.csv"
    monthly_path = report_dir / "monthly_returns.csv"
    positions_path = report_dir / "positions.csv"

    if not summary_path.exists() or not equity_path.exists():
        return None

    summary = pd.read_csv(summary_path)
    equity_curve = pd.read_csv(equity_path, parse_dates=["date"])
    drawdowns = (
        pd.read_csv(drawdowns_path, parse_dates=["date"]) if drawdowns_path.exists() else pd.DataFrame()
    )
    rolling_metrics = (
        pd.read_csv(rolling_metrics_path, parse_dates=["date"])
        if rolling_metrics_path.exists()
        else pd.DataFrame()
    )
    monthly_returns = pd.read_csv(monthly_path) if monthly_path.exists() else pd.DataFrame()
    positions = (
        pd.read_csv(positions_path, parse_dates=["date"])
        if positions_path.exists()
        else pd.DataFrame()
    )

    return {
        "summary": summary,
        "equity_curve": equity_curve,
        "drawdowns": drawdowns,
        "rolling_metrics": rolling_metrics,
        "monthly_returns": monthly_returns,
        "positions": positions,
        "paths": {
            "summary": summary_path,
            "equity_curve": equity_path,
            "drawdowns": drawdowns_path,
            "rolling_metrics": rolling_metrics_path,
            "monthly_returns": monthly_path,
            "positions": positions_path,
        },
    }


def _read_config(config_path: str) -> dict[str, Any]:
    try:
        return load_config(config_path)
    except FileNotFoundError:
        return {}


def _render_empty_state(report_dir: str) -> None:
    st.info(f"No report found at `{report_dir}`.")
    st.write(
        "Run the example backtest from the sidebar or point the dashboard at an existing "
        "report folder."
    )


def _render_metrics(summary: pd.DataFrame) -> None:
    if summary.empty:
        return

    metrics = summary.iloc[0].to_dict()
    rows = [
        [
            ("Total Return", _format_pct(metrics.get("total_return"))),
            ("Annual Return", _format_pct(metrics.get("annual_return"))),
            ("Annual Volatility", _format_pct(metrics.get("annual_volatility"))),
            ("Sharpe Ratio", _format_number(metrics.get("sharpe_ratio"))),
        ],
        [
            ("Max Drawdown", _format_pct(metrics.get("max_drawdown"))),
            ("Win Rate", _format_pct(metrics.get("win_rate"))),
            ("Average Turnover", _format_pct(metrics.get("average_turnover"))),
            ("Information Ratio", _format_number(metrics.get("information_ratio"))),
        ],
        [
            ("Benchmark Return", _format_pct(metrics.get("benchmark_total_return"))),
            ("Benchmark Annual", _format_pct(metrics.get("benchmark_annual_return"))),
            ("Excess Annual", _format_pct(metrics.get("excess_annual_return"))),
            ("Trading Days", _format_integer(metrics.get("trading_days"))),
        ],
        [
            ("Avg Gross Exposure", _format_pct(metrics.get("average_gross_exposure"))),
            ("Avg Cash Weight", _format_pct(metrics.get("average_cash_weight"))),
            ("", ""),
            ("", ""),
        ],
    ]

    for row in rows:
        columns = st.columns(4)
        for column, (label, value) in zip(columns, row, strict=False):
            column.metric(label, value)


def _render_equity_section(
    equity_curve: pd.DataFrame,
    drawdowns: pd.DataFrame,
    config: dict[str, Any],
) -> None:
    initial_cash = float(config.get("backtest", {}).get("initial_cash", DEFAULT_INITIAL_CASH))
    chart = equity_curve.copy()
    chart["strategy_index"] = chart["equity"] / chart["equity"].iloc[0] * 100.0

    if "benchmark_return" in chart.columns and chart["benchmark_return"].notna().any():
        benchmark_index = (1.0 + chart["benchmark_return"].fillna(0.0)).cumprod()
        chart["benchmark_index"] = benchmark_index / benchmark_index.iloc[0] * 100.0

    st.subheader("Equity Curve")
    index_columns = [
        column for column in ["strategy_index", "benchmark_index"] if column in chart.columns
    ]
    st.line_chart(chart.set_index("date")[index_columns])

    exposure_columns = [
        column for column in ["gross_exposure", "cash_weight"] if column in chart.columns
    ]
    if exposure_columns:
        st.subheader("Exposure")
        st.line_chart(chart.set_index("date")[exposure_columns])

    if not drawdowns.empty:
        st.subheader("Drawdown")
        st.line_chart(drawdowns.set_index("date")["drawdown"])

    ending_equity = float(equity_curve["equity"].iloc[-1])
    st.caption(
        f"Starting cash: {_format_currency(initial_cash)} | "
        f"Ending equity: {_format_currency(ending_equity)}"
    )


def _render_risk_section(drawdowns: pd.DataFrame, rolling_metrics: pd.DataFrame) -> None:
    if drawdowns.empty and rolling_metrics.empty:
        st.info("No risk diagnostics available.")
        return

    if not drawdowns.empty:
        st.subheader("Drawdown Diagnostics")
        stats = st.columns(3)
        stats[0].metric("Worst Drawdown", _format_pct(drawdowns["drawdown"].min()))
        stats[1].metric("Longest Underwater", _format_integer(drawdowns["underwater_days"].max()))
        stats[2].metric(
            "Latest Underwater Days",
            _format_integer(drawdowns["underwater_days"].iloc[-1]),
        )
        st.dataframe(drawdowns.tail(20), use_container_width=True, hide_index=True)

    if rolling_metrics.empty:
        return

    st.subheader("Rolling Diagnostics")
    chart_columns = [
        column
        for column in rolling_metrics.columns
        if column.startswith("rolling_") and rolling_metrics[column].notna().any()
    ]
    if chart_columns:
        st.line_chart(rolling_metrics.set_index("date")[chart_columns])
    st.dataframe(rolling_metrics.tail(60), use_container_width=True, hide_index=True)


def _render_monthly_section(monthly_returns: pd.DataFrame) -> None:
    if monthly_returns.empty:
        st.info("No monthly returns available.")
        return

    st.subheader("Monthly Returns")
    chart_columns = [
        column
        for column in ["strategy_return", "benchmark_return", "excess_return"]
        if column in monthly_returns.columns
    ]
    if chart_columns:
        st.bar_chart(monthly_returns.set_index("month")[chart_columns])

    st.dataframe(monthly_returns, use_container_width=True, hide_index=True)


def _render_positions_section(positions: pd.DataFrame) -> None:
    if positions.empty:
        st.info("No positions available.")
        return

    latest_date = positions["date"].max()
    latest_positions = positions.loc[positions["date"] == latest_date].sort_values(
        "weight",
        ascending=False,
    )
    st.subheader(f"Latest Positions: {latest_date:%Y-%m-%d}")
    st.dataframe(latest_positions, use_container_width=True, hide_index=True)


def _render_files_section(paths: dict[str, Path]) -> None:
    st.subheader("Report Files")
    file_rows = [{"name": key, "path": str(value)} for key, value in paths.items()]
    st.dataframe(pd.DataFrame(file_rows), use_container_width=True, hide_index=True)


def _format_pct(value: Any) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value) * 100:.2f}%"


def _format_number(value: Any) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):.2f}"


def _format_integer(value: Any) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{int(value)}"


def _format_currency(value: Any) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):,.2f}"


if __name__ == "__main__":
    main()
