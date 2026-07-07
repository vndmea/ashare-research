from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd

from ashare_research.config import ResearchConfig, StrategyConfig
from ashare_research.pipeline.run import ResearchRun, run_research


@dataclass(frozen=True)
class ExperimentArtifactPaths:
    summary: Path
    manifest: Path
    config_snapshot: Path


def run_parameter_sweep(
    config: ResearchConfig,
    *,
    fast_windows: list[int] | None = None,
    slow_windows: list[int] | None = None,
    parameter_grid: dict[str, list[Any]] | None = None,
) -> tuple[pd.DataFrame, list[ResearchRun]]:
    if parameter_grid is None:
        parameter_grid = _legacy_grid(fast_windows=fast_windows, slow_windows=slow_windows)

    parameter_names = list(parameter_grid)
    parameter_values = [parameter_grid[name] for name in parameter_names]

    runs: list[ResearchRun] = []
    rows: list[dict[str, Any]] = []
    for values in product(*parameter_values):
        candidate = dict(zip(parameter_names, values, strict=False))
        run_config = replace(
            config,
            strategy=StrategyConfig(
                name=config.strategy.name,
                parameters=config.strategy.resolved_parameters(candidate),
            ),
        )
        if not _is_valid_strategy_parameter_set(run_config.strategy):
            continue

        run = run_research(run_config)
        runs.append(run)
        metrics = run.backtest.metrics.to_dict()
        rows.append(
            {
                "run_id": _build_experiment_run_id(run_config.strategy),
                "strategy_name": run_config.strategy.name,
                **run_config.strategy.parameters,
                **metrics,
            }
        )

    return pd.DataFrame(rows), runs


def write_parameter_sweep_summary(
    summary: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(path, index=False)
    return path


def write_parameter_sweep_artifacts(
    summary: pd.DataFrame,
    config: ResearchConfig,
    output_dir: str | Path,
) -> ExperimentArtifactPaths:
    report_dir = Path(output_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    summary_path = write_parameter_sweep_summary(summary, report_dir / "parameter_sweep.csv")
    manifest_path = report_dir / "parameter_sweep_manifest.json"
    config_snapshot_path = report_dir / "config_snapshot.json"
    config_snapshot = _research_config_to_dict(config)
    config_snapshot_path.write_text(
        json.dumps(config_snapshot, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )

    manifest = {
        "experiment_id": f"sweep-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "strategy_name": config.strategy.name,
        "strategy_base_parameters": config.strategy.parameters,
        "run_count": int(len(summary)),
        "output_files": {
            "summary": str(summary_path),
            "config_snapshot": str(config_snapshot_path),
        },
        "config_snapshot": config_snapshot,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    return ExperimentArtifactPaths(
        summary=summary_path,
        manifest=manifest_path,
        config_snapshot=config_snapshot_path,
    )


def _legacy_grid(
    *,
    fast_windows: list[int] | None,
    slow_windows: list[int] | None,
) -> dict[str, list[Any]]:
    if fast_windows is None or slow_windows is None:
        raise ValueError("Either parameter_grid or both fast_windows and slow_windows must be provided")
    return {
        "fast_window": fast_windows,
        "slow_window": slow_windows,
    }


def _is_valid_strategy_parameter_set(strategy: StrategyConfig) -> bool:
    if strategy.name == "moving_average_crossover":
        return strategy.fast_window < strategy.slow_window
    return True


def _build_experiment_run_id(strategy: StrategyConfig) -> str:
    parts = [strategy.name]
    for key in sorted(strategy.parameters):
        parts.append(f"{key}-{strategy.parameters[key]}")
    return "__".join(parts)


def _research_config_to_dict(config: ResearchConfig) -> dict[str, Any]:
    return {
        "data": asdict(config.data),
        "backtest": asdict(config.backtest),
        "strategy": {
            "name": config.strategy.name,
            "parameters": config.strategy.parameters,
        },
        "report": asdict(config.report),
    }
