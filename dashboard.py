from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from ashare_research.config import load_config
from ashare_research.pipeline.run import run_research_and_write_reports

APP_TITLE = "A股研究看板"
DEFAULT_CONFIG_PATH = "configs/backtest.yaml"
DEFAULT_INITIAL_CASH = 1_000_000.0
CONFIG_SECTION_LABELS = {
    "data": "数据",
    "backtest": "回测",
    "strategy": "策略",
    "report": "报告",
}
CONFIG_FIELD_LABELS = {
    "daily_bar_path": "日线数据路径",
    "benchmark_path": "基准数据路径",
    "trading_calendar_path": "交易日历路径",
    "universe_path": "股票池路径",
    "adjustment_factor_path": "复权因子路径",
    "price_adjustment": "价格复权方式",
    "start_date": "开始日期",
    "end_date": "结束日期",
    "initial_cash": "初始资金",
    "commission_rate": "佣金费率",
    "stamp_tax_rate": "印花税率",
    "max_names": "最大持仓数",
    "position_sizing_method": "仓位分配方式",
    "rebalance_frequency": "调仓频率",
    "min_holding_days": "最短持有天数",
    "exclude_suspended": "排除停牌",
    "exclude_st": "排除ST",
    "block_limit_up_buys": "禁止涨停买入",
    "block_limit_down_sells": "禁止跌停卖出",
    "min_amount": "最小成交额",
    "name": "策略名称",
    "fast_window": "快线窗口",
    "slow_window": "慢线窗口",
    "output_dir": "输出目录",
}
CONFIG_VALUE_LABELS = {
    "none": "不复权",
    "forward": "前复权",
    "backward": "后复权",
    "equal_weight": "等权重",
    "daily": "每日",
    "weekly": "每周",
    "monthly": "每月",
    "moving_average_crossover": "均线交叉",
}
FILE_LABELS = {
    "summary": "汇总指标",
    "equity_curve": "净值曲线",
    "drawdowns": "回撤报告",
    "rolling_metrics": "滚动指标",
    "monthly_returns": "月度收益",
    "industry_exposure": "行业暴露",
    "positions": "持仓明细",
}
COLUMN_LABELS = {
    "date": "日期",
    "month": "月份",
    "symbol": "证券代码",
    "weight": "权重",
    "group_name": "分组名称",
    "exposure": "暴露",
    "equity": "账户权益",
    "peak_equity": "净值峰值",
    "drawdown": "回撤",
    "is_new_high": "是否新高",
    "underwater_days": "水下天数",
    "gross_return": "毛收益",
    "turnover": "换手率",
    "sell_turnover": "卖出换手率",
    "gross_exposure": "总暴露",
    "cash_weight": "现金仓位",
    "cost": "交易成本",
    "tax": "印花税",
    "net_return": "净收益",
    "benchmark_return": "基准收益",
    "strategy_return": "策略收益",
    "excess_return": "超额收益",
    "strategy_index": "策略净值指数",
    "benchmark_index": "基准净值指数",
    "is_rebalance_day": "是否调仓日",
    "name": "文件名称",
    "path": "文件路径",
}


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide", initial_sidebar_state="expanded")
    _apply_app_chrome_overrides()
    st.title(APP_TITLE)
    st.caption("运行示例研究流程，并查看生成的分析报告。")

    with st.sidebar:
        st.header("控制面板")
        config_path = st.text_input("配置文件", DEFAULT_CONFIG_PATH)
        config = _read_config(config_path)
        default_report_dir = config.report.output_dir if config is not None else "reports/example_run"
        report_dir = st.text_input("报告目录", default_report_dir)
        run_clicked = st.button("运行示例回测", type="primary", use_container_width=True)
        st.divider()
        st.subheader("配置预览")
        if config is not None:
            st.json(_config_to_dict(config), expanded=False)
        else:
            st.info("未加载配置。")

    if run_clicked:
        with st.spinner("正在运行回测并写入报告..."):
            report_dir = _run_example_backtest(config_path, report_dir)
        st.success(f"报告已写入 {report_dir}")

    report = _load_report_bundle(report_dir)
    if report is None:
        _render_empty_state(report_dir)
        return

    _render_metrics(report["summary"])

    tab_equity, tab_risk, tab_monthly, tab_positions, tab_exposure, tab_files = st.tabs(
        ["净值", "风险", "月度", "持仓", "暴露", "文件"]
    )

    with tab_equity:
        _render_equity_section(report["equity_curve"], report["drawdowns"], config)

    with tab_risk:
        _render_risk_section(report["drawdowns"], report["rolling_metrics"])

    with tab_monthly:
        _render_monthly_section(report["monthly_returns"])

    with tab_positions:
        _render_positions_section(report["positions"])

    with tab_exposure:
        _render_exposure_section(report["industry_exposure"])

    with tab_files:
        _render_files_section(report["paths"])


def _run_example_backtest(config_path: str, output_dir: str) -> str:
    config = _read_config(config_path)
    if config is None:
        raise FileNotFoundError(f"未找到配置文件：{config_path}")

    run_research_and_write_reports(config, output_dir)
    return output_dir


def _load_report_bundle(output_dir: str) -> dict[str, Any] | None:
    report_dir = Path(output_dir)
    summary_path = report_dir / "summary.csv"
    equity_path = report_dir / "equity_curve.csv"
    drawdowns_path = report_dir / "drawdowns.csv"
    rolling_metrics_path = report_dir / "rolling_metrics.csv"
    monthly_path = report_dir / "monthly_returns.csv"
    industry_exposure_path = report_dir / "industry_exposure.csv"
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
    industry_exposure = (
        pd.read_csv(industry_exposure_path, parse_dates=["date"])
        if industry_exposure_path.exists()
        else pd.DataFrame()
    )
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
        "industry_exposure": industry_exposure,
        "positions": positions,
        "paths": {
            "summary": summary_path,
            "equity_curve": equity_path,
            "drawdowns": drawdowns_path,
            "rolling_metrics": rolling_metrics_path,
            "monthly_returns": monthly_path,
            "industry_exposure": industry_exposure_path,
            "positions": positions_path,
        },
    }


def _read_config(config_path: str):
    try:
        return load_config(config_path)
    except FileNotFoundError:
        return None


def _render_empty_state(report_dir: str) -> None:
    st.info(f"在 `{report_dir}` 下未找到报告。")
    st.write(
        "请从侧边栏运行示例回测，或将看板指向一个已有的报告目录。"
    )


def _render_metrics(summary: pd.DataFrame) -> None:
    if summary.empty:
        return

    metrics = summary.iloc[0].to_dict()
    rows = [
        [
            ("总收益", _format_pct(metrics.get("total_return"))),
            ("年化收益", _format_pct(metrics.get("annual_return"))),
            ("年化波动", _format_pct(metrics.get("annual_volatility"))),
            ("夏普比率", _format_number(metrics.get("sharpe_ratio"))),
        ],
        [
            ("最大回撤", _format_pct(metrics.get("max_drawdown"))),
            ("胜率", _format_pct(metrics.get("win_rate"))),
            ("平均换手", _format_pct(metrics.get("average_turnover"))),
            ("信息比率", _format_number(metrics.get("information_ratio"))),
        ],
        [
            ("基准收益", _format_pct(metrics.get("benchmark_total_return"))),
            ("基准年化", _format_pct(metrics.get("benchmark_annual_return"))),
            ("超额年化", _format_pct(metrics.get("excess_annual_return"))),
            ("交易日数", _format_integer(metrics.get("trading_days"))),
        ],
        [
            ("平均总暴露", _format_pct(metrics.get("average_gross_exposure"))),
            ("平均现金仓位", _format_pct(metrics.get("average_cash_weight"))),
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
    config: Any,
) -> None:
    initial_cash = config.backtest.initial_cash if config is not None else DEFAULT_INITIAL_CASH
    chart = equity_curve.copy()
    chart["strategy_index"] = chart["equity"] / chart["equity"].iloc[0] * 100.0

    if "benchmark_return" in chart.columns and chart["benchmark_return"].notna().any():
        benchmark_index = (1.0 + chart["benchmark_return"].fillna(0.0)).cumprod()
        chart["benchmark_index"] = benchmark_index / benchmark_index.iloc[0] * 100.0

    st.subheader("净值曲线")
    index_columns = [
        column for column in ["strategy_index", "benchmark_index"] if column in chart.columns
    ]
    equity_chart = _with_chart_index(chart, "date")[index_columns].rename(columns=_display_label)
    st.line_chart(equity_chart)

    exposure_columns = [
        column for column in ["gross_exposure", "cash_weight"] if column in chart.columns
    ]
    if exposure_columns:
        st.subheader("仓位暴露")
        exposure_chart = _with_chart_index(chart, "date")[exposure_columns].rename(columns=_display_label)
        st.line_chart(exposure_chart)

    if "is_rebalance_day" in chart.columns:
        st.subheader("调仓节奏")
        rebalance_chart = _with_chart_index(chart, "date")[["is_rebalance_day"]].rename(columns=_display_label)
        st.bar_chart(rebalance_chart)

    if not drawdowns.empty:
        st.subheader("回撤")
        drawdown_chart = _with_chart_index(drawdowns, "date")[["drawdown"]].rename(columns=_display_label)
        st.line_chart(drawdown_chart)

    ending_equity = float(equity_curve["equity"].iloc[-1])
    st.caption(
        f"初始资金：{_format_currency(initial_cash)} | "
        f"期末净值：{_format_currency(ending_equity)}"
    )


def _render_risk_section(drawdowns: pd.DataFrame, rolling_metrics: pd.DataFrame) -> None:
    if drawdowns.empty and rolling_metrics.empty:
        st.info("暂无风险诊断数据。")
        return

    if not drawdowns.empty:
        st.subheader("回撤诊断")
        stats = st.columns(3)
        stats[0].metric("最深回撤", _format_pct(drawdowns["drawdown"].min()))
        stats[1].metric("最长水下期", _format_integer(drawdowns["underwater_days"].max()))
        stats[2].metric(
            "当前水下天数",
            _format_integer(drawdowns["underwater_days"].iloc[-1]),
        )
        st.dataframe(_localize_dataframe(drawdowns.tail(20)), use_container_width=True, hide_index=True)

    if rolling_metrics.empty:
        return

    st.subheader("滚动诊断")
    chart_columns = [
        column
        for column in rolling_metrics.columns
        if column.startswith("rolling_") and rolling_metrics[column].notna().any()
    ]
    if chart_columns:
        chart = _with_chart_index(rolling_metrics, "date")[chart_columns].rename(columns=_display_label)
        st.line_chart(chart)
    st.dataframe(_localize_dataframe(rolling_metrics.tail(60)), use_container_width=True, hide_index=True)


def _render_monthly_section(monthly_returns: pd.DataFrame) -> None:
    if monthly_returns.empty:
        st.info("暂无月度收益数据。")
        return

    st.subheader("月度收益")
    chart_columns = [
        column
        for column in ["strategy_return", "benchmark_return", "excess_return"]
        if column in monthly_returns.columns
    ]
    if chart_columns:
        chart = _with_chart_index(monthly_returns, "month")[chart_columns].rename(columns=_display_label)
        st.bar_chart(chart)

    st.dataframe(_localize_dataframe(monthly_returns), use_container_width=True, hide_index=True)


def _render_positions_section(positions: pd.DataFrame) -> None:
    if positions.empty:
        st.info("暂无持仓数据。")
        return

    latest_date = positions["date"].max()
    latest_positions = positions.loc[positions["date"] == latest_date].sort_values(
        "weight",
        ascending=False,
    )
    st.subheader(f"最新持仓：{latest_date:%Y-%m-%d}")
    st.dataframe(_localize_dataframe(latest_positions), use_container_width=True, hide_index=True)


def _render_exposure_section(industry_exposure: pd.DataFrame) -> None:
    if industry_exposure.empty:
        st.info("暂无行业或板块暴露数据。")
        return

    latest_date = industry_exposure["date"].max()
    latest_exposure = industry_exposure.loc[industry_exposure["date"] == latest_date].copy()
    latest_exposure = latest_exposure.sort_values("exposure", ascending=False)
    st.subheader(f"最新暴露：{latest_date:%Y-%m-%d}")
    chart = _with_chart_index(latest_exposure, "group_name")[["exposure"]].rename(columns=_display_label)
    st.bar_chart(chart)
    st.dataframe(_localize_dataframe(latest_exposure), use_container_width=True, hide_index=True)


def _render_files_section(paths: dict[str, Path]) -> None:
    st.subheader("报告文件")
    file_rows = [{"name": FILE_LABELS.get(key, key), "path": str(value)} for key, value in paths.items()]
    st.dataframe(_localize_dataframe(pd.DataFrame(file_rows)), use_container_width=True, hide_index=True)


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


def _config_to_dict(config: Any) -> dict[str, Any]:
    return {
        CONFIG_SECTION_LABELS["data"]: _localize_config_section(config.data.__dict__),
        CONFIG_SECTION_LABELS["backtest"]: _localize_config_section(config.backtest.__dict__),
        CONFIG_SECTION_LABELS["strategy"]: _localize_config_section(config.strategy.__dict__),
        CONFIG_SECTION_LABELS["report"]: _localize_config_section(config.report.__dict__),
    }


def _localize_config_section(section: dict[str, Any]) -> dict[str, Any]:
    return {
        CONFIG_FIELD_LABELS.get(key, key): _localize_config_value(value)
        for key, value in section.items()
    }


def _localize_config_value(value: Any) -> Any:
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, str):
        return CONFIG_VALUE_LABELS.get(value, value)
    return value


def _localize_dataframe(frame: pd.DataFrame) -> pd.DataFrame:
    localized = frame.copy()
    localized.rename(columns=_display_label, inplace=True)
    return localized


def _display_label(column: str) -> str:
    if column in COLUMN_LABELS:
        return COLUMN_LABELS[column]
    if column.startswith("rolling_") and column.endswith("_return"):
        window = column.removeprefix("rolling_").removesuffix("_return")
        return f"滚动{window}收益"
    if column.startswith("rolling_") and column.endswith("_volatility"):
        window = column.removeprefix("rolling_").removesuffix("_volatility")
        return f"滚动{window}波动"
    return column


def _with_chart_index(frame: pd.DataFrame, index_column: str) -> pd.DataFrame:
    chart = frame.copy()
    if index_column not in chart.columns:
        return chart

    series = chart[index_column]
    if pd.api.types.is_datetime64_any_dtype(series):
        chart[index_column] = series.dt.strftime("%Y-%m-%d")
    else:
        chart[index_column] = series.astype(str)
    return chart.set_index(index_column)


def _apply_app_chrome_overrides() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stHeaderActionElements"] {
            display: none !important;
        }
        [data-testid="stToolbar"] {
            display: none !important;
        }
        [data-testid="stToolbarActions"] {
            display: none !important;
        }
        [data-testid="stAppDeployButton"] {
            display: none !important;
        }
        .stAppDeployButton {
            display: none !important;
        }
        #MainMenu {
            visibility: hidden;
        }
        footer {
            visibility: hidden;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
