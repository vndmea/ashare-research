from __future__ import annotations

import argparse

from ashare_research.config import load_config
from ashare_research.experiments.sweep import run_parameter_sweep, write_parameter_sweep_summary
from ashare_research.pipeline.run import run_research, run_research_and_write_reports


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
    args = parser.parse_args()

    config = load_config(args.config)
    if args.sweep_fast and args.sweep_slow:
        fast_windows = _parse_int_list(args.sweep_fast)
        slow_windows = _parse_int_list(args.sweep_slow)
        summary, _ = run_parameter_sweep(
            config,
            fast_windows=fast_windows,
            slow_windows=slow_windows,
        )
        output_dir = args.output_dir or config.report.output_dir
        summary_path = write_parameter_sweep_summary(summary, f"{output_dir}/parameter_sweep.csv")
        print(f"parameter_sweep_report: {summary_path}")
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


def _parse_int_list(text: str) -> list[int]:
    return [int(item.strip()) for item in text.split(",") if item.strip()]
