from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from ashare_research.config import load_config
from ashare_research.experiments.sweep import (
    run_parameter_sweep,
    write_parameter_sweep_artifacts,
)
from ashare_research.data.baostock import (
    build_baostock_download_bundle,
    write_baostock_download_bundle,
)
from ashare_research.pipeline.run import (
    load_research_inputs,
    run_research,
    run_research_and_write_reports,
    run_symbol_technical_analysis_and_write_reports,
    summarize_research_inputs,
)


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
    parser.add_argument(
        "--sweep-fast",
        default=None,
        help="Comma-separated fast windows for parameter sweep.",
    )
    parser.add_argument(
        "--sweep-slow",
        default=None,
        help="Comma-separated slow windows for parameter sweep.",
    )
    parser.add_argument(
        "--sweep-parameter",
        action="append",
        default=None,
        help="Generic parameter grid item like lookback_window=10,20,40. Can be repeated.",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    if args.sweep_parameter or (args.sweep_fast and args.sweep_slow):
        parameter_grid = (
            _parse_parameter_grid(args.sweep_parameter)
            if args.sweep_parameter
            else None
        )
        fast_windows = _parse_int_list(args.sweep_fast) if args.sweep_fast else None
        slow_windows = _parse_int_list(args.sweep_slow) if args.sweep_slow else None
        summary, _ = run_parameter_sweep(
            config,
            fast_windows=fast_windows,
            slow_windows=slow_windows,
            parameter_grid=parameter_grid,
        )
        output_dir = args.output_dir or config.report.output_dir
        artifacts = write_parameter_sweep_artifacts(summary, config, output_dir)
        print(f"parameter_sweep_report: {artifacts.summary}")
        print(f"parameter_sweep_manifest: {artifacts.manifest}")
        print(f"parameter_sweep_config_snapshot: {artifacts.config_snapshot}")
        return

    output_dir = args.output_dir or config.report.output_dir
    if output_dir:
        research = run_research_and_write_reports(config, output_dir)
    else:
        research = None
        run = run_research(config)

    result = research.run.backtest if research is not None else run.backtest
    summary = result.metrics.to_dict()
    for key, value in summary.items():
        print(f"{key}: {value:.4f}" if isinstance(value, float) else f"{key}: {value}")

    if research is not None:
        report_paths = research.reports
        print(f"summary_report: {report_paths.summary}")
        print(f"equity_curve_report: {report_paths.equity_curve}")
        print(f"monthly_returns_report: {report_paths.monthly_returns}")
        print(f"industry_exposure_report: {report_paths.industry_exposure}")
        print(f"strategy_attribution_report: {report_paths.strategy_attribution}")
        print(f"positions_report: {report_paths.positions}")
        print(f"execution_diagnostics_report: {report_paths.execution_diagnostics}")
        print(f"trade_ledger_report: {report_paths.trade_ledger}")


def validate_data() -> None:
    parser = argparse.ArgumentParser(
        description="Validate normalized A-share research data inputs."
    )
    parser.add_argument(
        "--config",
        default="configs/backtest.yaml",
        help="Path to the YAML config file.",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    summary = summarize_research_inputs(load_research_inputs(config))
    print("validation_status: ok")
    print(f"bar_rows: {summary.bar_rows}")
    print(f"symbol_count: {summary.symbol_count}")
    print(f"start_date: {summary.start_date}")
    print(f"end_date: {summary.end_date}")
    print(f"benchmark_rows: {summary.benchmark_rows}")
    print(f"trading_calendar_days: {summary.trading_calendar_days}")
    print(f"universe_rows: {summary.universe_rows}")
    manifest_path = Path(config.data.daily_bar_path).resolve().parent / "dataset_manifest.json"
    if manifest_path.exists():
        print(f"data_manifest: {manifest_path}")


def bootstrap_baostock() -> None:
    parser = argparse.ArgumentParser(
        description="Download Baostock data, validate inputs, and run a backtest."
    )
    parser.add_argument(
        "--config",
        default="configs/baostock.yaml",
        help="Path to the YAML config file.",
    )
    parser.add_argument(
        "--start-date",
        required=True,
        help="Start date in YYYY-MM-DD format for the download range.",
    )
    parser.add_argument(
        "--end-date",
        required=True,
        help="End date in YYYY-MM-DD format for the download range.",
    )
    parser.add_argument(
        "--symbols",
        default=None,
        help="Optional comma-separated Baostock or project-format symbols.",
    )
    parser.add_argument(
        "--benchmark-symbol",
        default="000300.SH",
        help="Optional benchmark symbol to download alongside bars, default is 000300.SH.",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Number of parallel download workers.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Number of retries per symbol.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional directory for CSV report outputs.",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    bundle = build_baostock_download_bundle(
        args.start_date,
        args.end_date,
        symbols=_parse_symbol_list(args.symbols),
        benchmark_symbol=args.benchmark_symbol or None,
        max_workers=args.max_workers,
        retries=args.retries,
    )
    download_paths = _baostock_download_paths(config)
    manifest_source_details = {
        "downloader": "ashare-bootstrap-baostock",
        "provider": "baostock",
        "start_date": args.start_date,
        "end_date": args.end_date,
        "max_workers": int(args.max_workers),
        "retries": int(args.retries),
        "symbols": _parse_symbol_list(args.symbols) or [],
        "benchmark_symbol": args.benchmark_symbol or None,
    }
    write_baostock_download_bundle(
        bundle,
        output=download_paths["daily_bar_path"],
        benchmark_output=download_paths["benchmark_path"],
        calendar_output=download_paths["trading_calendar_path"],
        universe_output=download_paths["universe_path"],
        manifest_output=download_paths["manifest_path"],
        source_details=manifest_source_details,
    )
    print(f"downloaded_rows: {len(bundle.bars)}")
    print(f"downloaded_symbols: {bundle.bars['symbol'].nunique()}")
    print(f"download_start_date: {args.start_date}")
    print(f"download_end_date: {args.end_date}")
    print(f"daily_bar_path: {download_paths['daily_bar_path']}")
    if download_paths["benchmark_path"] is not None and bundle.benchmark is not None:
        print(f"benchmark_path: {download_paths['benchmark_path']}")
    print(f"trading_calendar_path: {download_paths['trading_calendar_path']}")
    print(f"universe_path: {download_paths['universe_path']}")
    print(f"data_manifest: {download_paths['manifest_path']}")

    runtime_config = _bootstrap_runtime_config(config)
    summary = summarize_research_inputs(load_research_inputs(runtime_config))
    print("validation_status: ok")
    print(f"bar_rows: {summary.bar_rows}")
    print(f"symbol_count: {summary.symbol_count}")
    print(f"start_date: {summary.start_date}")
    print(f"end_date: {summary.end_date}")
    print(f"benchmark_rows: {summary.benchmark_rows}")
    print(f"trading_calendar_days: {summary.trading_calendar_days}")
    print(f"universe_rows: {summary.universe_rows}")

    output_dir = args.output_dir or runtime_config.report.output_dir
    research = run_research_and_write_reports(runtime_config, output_dir)
    result = research.run.backtest
    summary_metrics = result.metrics.to_dict()
    for key, value in summary_metrics.items():
        print(f"{key}: {value:.4f}" if isinstance(value, float) else f"{key}: {value}")
    report_paths = research.reports
    print(f"summary_report: {report_paths.summary}")
    print(f"equity_curve_report: {report_paths.equity_curve}")
    print(f"monthly_returns_report: {report_paths.monthly_returns}")
    print(f"industry_exposure_report: {report_paths.industry_exposure}")
    print(f"strategy_attribution_report: {report_paths.strategy_attribution}")
    print(f"positions_report: {report_paths.positions}")
    print(f"execution_diagnostics_report: {report_paths.execution_diagnostics}")
    print(f"trade_ledger_report: {report_paths.trade_ledger}")


def analyze_symbols() -> None:
    parser = argparse.ArgumentParser(
        description="Run single-stock technical analysis and write a formal report."
    )
    parser.add_argument(
        "--config",
        default="configs/symbol_analysis.yaml",
        help="Path to the YAML config file.",
    )
    parser.add_argument(
        "--symbols",
        default=None,
        help="Optional comma-separated symbol override in project or baostock format.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional directory for the symbol technical analysis report.",
    )
    args = parser.parse_args()
    _dispatch_analyze_symbols(args)


def main() -> None:
    parser = argparse.ArgumentParser(prog="ashare")
    subparsers = parser.add_subparsers(dest="command", required=True)

    backtest_parser = subparsers.add_parser("run-backtest", help="Run the example backtest.")
    backtest_parser.add_argument("--config", default="configs/backtest.yaml")
    backtest_parser.add_argument("--output-dir", default=None)
    backtest_parser.add_argument("--sweep-fast", default=None)
    backtest_parser.add_argument("--sweep-slow", default=None)
    backtest_parser.add_argument("--sweep-parameter", action="append", default=None)
    backtest_parser.set_defaults(handler=_dispatch_run_backtest)

    validate_parser = subparsers.add_parser("validate-data", help="Validate research inputs.")
    validate_parser.add_argument("--config", default="configs/backtest.yaml")
    validate_parser.set_defaults(handler=_dispatch_validate_data)

    bootstrap_parser = subparsers.add_parser(
        "bootstrap-baostock",
        help="Download Baostock data, validate inputs, and run a backtest.",
    )
    bootstrap_parser.add_argument("--config", default="configs/baostock.yaml")
    bootstrap_parser.add_argument("--start-date", required=True)
    bootstrap_parser.add_argument("--end-date", required=True)
    bootstrap_parser.add_argument("--symbols", default=None)
    bootstrap_parser.add_argument("--benchmark-symbol", default="000300.SH")
    bootstrap_parser.add_argument("--max-workers", type=int, default=4)
    bootstrap_parser.add_argument("--retries", type=int, default=3)
    bootstrap_parser.add_argument("--output-dir", default=None)
    bootstrap_parser.set_defaults(handler=_dispatch_bootstrap_baostock)

    analyze_parser = subparsers.add_parser(
        "analyze-symbols",
        help="Run single-stock technical analysis and export the report.",
    )
    analyze_parser.add_argument("--config", default="configs/symbol_analysis.yaml")
    analyze_parser.add_argument("--symbols", default=None)
    analyze_parser.add_argument("--output-dir", default=None)
    analyze_parser.set_defaults(handler=_dispatch_analyze_symbols)

    args = parser.parse_args()
    args.handler(args)


def _dispatch_run_backtest(args) -> None:
    config = load_config(args.config)
    if args.sweep_parameter or (args.sweep_fast and args.sweep_slow):
        parameter_grid = (
            _parse_parameter_grid(args.sweep_parameter)
            if args.sweep_parameter
            else None
        )
        fast_windows = _parse_int_list(args.sweep_fast) if args.sweep_fast else None
        slow_windows = _parse_int_list(args.sweep_slow) if args.sweep_slow else None
        summary, _ = run_parameter_sweep(
            config,
            fast_windows=fast_windows,
            slow_windows=slow_windows,
            parameter_grid=parameter_grid,
        )
        output_dir = args.output_dir or config.report.output_dir
        artifacts = write_parameter_sweep_artifacts(summary, config, output_dir)
        print(f"parameter_sweep_report: {artifacts.summary}")
        print(f"parameter_sweep_manifest: {artifacts.manifest}")
        print(f"parameter_sweep_config_snapshot: {artifacts.config_snapshot}")
        return

    output_dir = args.output_dir or config.report.output_dir
    if output_dir:
        research = run_research_and_write_reports(config, output_dir)
    else:
        research = None
        run = run_research(config)

    result = research.run.backtest if research is not None else run.backtest
    summary = result.metrics.to_dict()
    for key, value in summary.items():
        print(f"{key}: {value:.4f}" if isinstance(value, float) else f"{key}: {value}")

    if research is not None:
        report_paths = research.reports
        print(f"summary_report: {report_paths.summary}")
        print(f"equity_curve_report: {report_paths.equity_curve}")
        print(f"monthly_returns_report: {report_paths.monthly_returns}")
        print(f"industry_exposure_report: {report_paths.industry_exposure}")
        print(f"strategy_attribution_report: {report_paths.strategy_attribution}")
        print(f"positions_report: {report_paths.positions}")
        print(f"execution_diagnostics_report: {report_paths.execution_diagnostics}")
        print(f"trade_ledger_report: {report_paths.trade_ledger}")


def _dispatch_validate_data(args) -> None:
    config = load_config(args.config)
    summary = summarize_research_inputs(load_research_inputs(config))
    print("validation_status: ok")
    print(f"bar_rows: {summary.bar_rows}")
    print(f"symbol_count: {summary.symbol_count}")
    print(f"start_date: {summary.start_date}")
    print(f"end_date: {summary.end_date}")
    print(f"benchmark_rows: {summary.benchmark_rows}")
    print(f"trading_calendar_days: {summary.trading_calendar_days}")
    print(f"universe_rows: {summary.universe_rows}")
    manifest_path = Path(config.data.daily_bar_path).resolve().parent / "dataset_manifest.json"
    if manifest_path.exists():
        print(f"data_manifest: {manifest_path}")


def _dispatch_bootstrap_baostock(args) -> None:
    config = load_config(args.config)
    bundle = build_baostock_download_bundle(
        args.start_date,
        args.end_date,
        symbols=_parse_symbol_list(args.symbols),
        benchmark_symbol=args.benchmark_symbol or None,
        max_workers=args.max_workers,
        retries=args.retries,
    )
    download_paths = _baostock_download_paths(config)
    manifest_source_details = {
        "downloader": "ashare-bootstrap-baostock",
        "provider": "baostock",
        "start_date": args.start_date,
        "end_date": args.end_date,
        "max_workers": int(args.max_workers),
        "retries": int(args.retries),
        "symbols": _parse_symbol_list(args.symbols) or [],
        "benchmark_symbol": args.benchmark_symbol or None,
    }
    write_baostock_download_bundle(
        bundle,
        output=download_paths["daily_bar_path"],
        benchmark_output=download_paths["benchmark_path"],
        calendar_output=download_paths["trading_calendar_path"],
        universe_output=download_paths["universe_path"],
        manifest_output=download_paths["manifest_path"],
        source_details=manifest_source_details,
    )
    print(f"downloaded_rows: {len(bundle.bars)}")
    print(f"downloaded_symbols: {bundle.bars['symbol'].nunique()}")
    print(f"download_start_date: {args.start_date}")
    print(f"download_end_date: {args.end_date}")
    print(f"daily_bar_path: {download_paths['daily_bar_path']}")
    if download_paths["benchmark_path"] is not None and bundle.benchmark is not None:
        print(f"benchmark_path: {download_paths['benchmark_path']}")
    print(f"trading_calendar_path: {download_paths['trading_calendar_path']}")
    print(f"universe_path: {download_paths['universe_path']}")
    print(f"data_manifest: {download_paths['manifest_path']}")

    runtime_config = _bootstrap_runtime_config(config)
    summary = summarize_research_inputs(load_research_inputs(runtime_config))
    print("validation_status: ok")
    print(f"bar_rows: {summary.bar_rows}")
    print(f"symbol_count: {summary.symbol_count}")
    print(f"start_date: {summary.start_date}")
    print(f"end_date: {summary.end_date}")
    print(f"benchmark_rows: {summary.benchmark_rows}")
    print(f"trading_calendar_days: {summary.trading_calendar_days}")
    print(f"universe_rows: {summary.universe_rows}")

    output_dir = args.output_dir or runtime_config.report.output_dir
    research = run_research_and_write_reports(runtime_config, output_dir)
    result = research.run.backtest
    summary_metrics = result.metrics.to_dict()
    for key, value in summary_metrics.items():
        print(f"{key}: {value:.4f}" if isinstance(value, float) else f"{key}: {value}")
    report_paths = research.reports
    print(f"summary_report: {report_paths.summary}")
    print(f"equity_curve_report: {report_paths.equity_curve}")
    print(f"monthly_returns_report: {report_paths.monthly_returns}")
    print(f"industry_exposure_report: {report_paths.industry_exposure}")
    print(f"strategy_attribution_report: {report_paths.strategy_attribution}")
    print(f"positions_report: {report_paths.positions}")
    print(f"execution_diagnostics_report: {report_paths.execution_diagnostics}")
    print(f"trade_ledger_report: {report_paths.trade_ledger}")


def _dispatch_analyze_symbols(args) -> None:
    config = load_config(args.config)
    symbols = _parse_symbol_list(args.symbols)
    output_dir = args.output_dir or config.report.output_dir
    analysis = run_symbol_technical_analysis_and_write_reports(
        config,
        output_dir,
        symbols=tuple(symbols) if symbols is not None else None,
    )
    print(f"symbol_count: {len(analysis.run.summary)}")
    print(f"symbol_technical_analysis_report: {analysis.reports.summary}")
    print(analysis.run.summary.to_string(index=False))


def _parse_int_list(text: str) -> list[int]:
    return [int(item.strip()) for item in text.split(",") if item.strip()]


def _parse_symbol_list(text: str | None) -> list[str] | None:
    if not text:
        return None
    values = [item.strip() for item in text.split(",") if item.strip()]
    return values or None


def _parse_parameter_grid(items: list[str]) -> dict[str, list[object]]:
    grid: dict[str, list[object]] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Invalid sweep parameter format: {item}")
        key, raw_values = item.split("=", maxsplit=1)
        values = [part.strip() for part in raw_values.split(",") if part.strip()]
        if not values:
            raise ValueError(f"Sweep parameter has no values: {item}")
        grid[key.strip()] = [_coerce_cli_value(value) for value in values]
    return grid


def _coerce_cli_value(value: str) -> object:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _baostock_download_paths(config) -> dict[str, Path]:
    daily_bar_path = Path(config.data.daily_bar_path)
    base_dir = daily_bar_path.parent
    benchmark_path = (
        Path(config.data.benchmark_path)
        if config.data.benchmark_path
        else base_dir / "benchmark.csv"
    )
    trading_calendar_path = (
        Path(config.data.trading_calendar_path)
        if config.data.trading_calendar_path
        else base_dir / "trading_calendar.csv"
    )
    universe_path = (
        Path(config.data.universe_path) if config.data.universe_path else base_dir / "universe.csv"
    )
    manifest_path = base_dir / "dataset_manifest.json"
    return {
        "daily_bar_path": daily_bar_path,
        "benchmark_path": benchmark_path,
        "trading_calendar_path": trading_calendar_path,
        "universe_path": universe_path,
        "manifest_path": manifest_path,
    }


def _bootstrap_runtime_config(config):
    benchmark_path = Path(config.data.benchmark_path) if config.data.benchmark_path else None
    if benchmark_path is not None and not benchmark_path.exists():
        benchmark_path = None
    return replace(
        config,
        data=replace(config.data, benchmark_path=str(benchmark_path) if benchmark_path else None),
    )


if __name__ == "__main__":
    main()
