from __future__ import annotations

import argparse
from pathlib import Path

from ashare_research.analysis.reports import write_research_report
from ashare_research.backtest.engine import run_close_to_close_backtest
from ashare_research.config import load_config
from ashare_research.data.benchmarks import load_benchmark_returns
from ashare_research.data.calendar import load_trading_calendar
from ashare_research.data.daily_bars import load_daily_bars
from ashare_research.data.universe import load_universe_snapshot
from ashare_research.risk.tradeability import TradeConstraints
from ashare_research.strategies.moving_average import moving_average_crossover_signals


def run_backtest() -> None:
    parser = argparse.ArgumentParser(description="Run the example A-share daily backtest.")
    parser.add_argument(
        "--config",
        default="configs/backtest.yaml",
        help="Path to the YAML config file.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional directory for CSV report outputs.",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    start_date = config["backtest"].get("start_date")
    end_date = config["backtest"].get("end_date")
    data_path = Path(config["data"]["daily_bar_path"])
    bars = load_daily_bars(
        data_path,
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
        initial_cash=float(config["backtest"].get("initial_cash", 1_000_000)),
        commission_rate=float(config["backtest"].get("commission_rate", 0.0003)),
        stamp_tax_rate=float(config["backtest"].get("stamp_tax_rate", 0.0005)),
        max_names=int(config["backtest"].get("max_names", 20)),
        position_sizing_method=str(
            config["backtest"].get("position_sizing_method", "equal_weight")
        ),
        rebalance_frequency=str(config["backtest"].get("rebalance_frequency", "daily")),
        min_holding_days=int(config["backtest"].get("min_holding_days", 0)),
        benchmark_returns=benchmark_returns,
        trading_calendar=trading_calendar,
        universe=universe,
        trade_constraints=_load_trade_constraints(config),
    )

    summary = result.metrics.to_dict()
    for key, value in summary.items():
        print(f"{key}: {value:.4f}" if isinstance(value, float) else f"{key}: {value}")

    output_dir = args.output_dir or config.get("report", {}).get("output_dir")
    if output_dir:
        report_paths = write_research_report(
            output_dir,
            result.equity_curve,
            result.positions,
            result.metrics,
            benchmark_returns=benchmark_returns,
        )
        print(f"summary_report: {report_paths.summary}")
        print(f"equity_curve_report: {report_paths.equity_curve}")
        print(f"monthly_returns_report: {report_paths.monthly_returns}")
        print(f"positions_report: {report_paths.positions}")


def _load_optional_benchmark(
    config: dict,
    start_date: str | None,
    end_date: str | None,
):
    benchmark_path = config.get("data", {}).get("benchmark_path")
    if not benchmark_path:
        return None
    return load_benchmark_returns(benchmark_path, start_date=start_date, end_date=end_date)


def _load_optional_calendar(config: dict):
    calendar_path = config.get("data", {}).get("trading_calendar_path")
    if not calendar_path or not Path(calendar_path).exists():
        return None
    return load_trading_calendar(calendar_path)


def _load_optional_universe(config: dict):
    universe_path = config.get("data", {}).get("universe_path")
    if not universe_path or not Path(universe_path).exists():
        return None
    return load_universe_snapshot(universe_path)


def _load_trade_constraints(config: dict) -> TradeConstraints:
    backtest = config.get("backtest", {})
    return TradeConstraints(
        exclude_suspended=bool(backtest.get("exclude_suspended", True)),
        exclude_st=bool(backtest.get("exclude_st", True)),
        block_limit_up_buys=bool(backtest.get("block_limit_up_buys", True)),
        block_limit_down_sells=bool(backtest.get("block_limit_down_sells", True)),
        min_amount=float(backtest.get("min_amount", 0.0)),
    )
