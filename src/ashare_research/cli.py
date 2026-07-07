from __future__ import annotations

import argparse
from pathlib import Path

from ashare_research.config import load_config
from ashare_research.experiments.sweep import (
    run_parameter_sweep,
    write_parameter_sweep_artifacts,
)
from ashare_research.pipeline.run import (
    load_research_inputs,
    run_research,
    run_research_and_write_reports,
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


def _parse_int_list(text: str) -> list[int]:
    return [int(item.strip()) for item in text.split(",") if item.strip()]


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
