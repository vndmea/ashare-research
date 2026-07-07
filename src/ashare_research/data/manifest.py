from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


def build_data_manifest(
    *,
    source_name: str,
    bars: pd.DataFrame,
    benchmark: pd.DataFrame | None = None,
    trading_calendar: pd.DataFrame | None = None,
    universe: pd.DataFrame | None = None,
    adjustment_factors: pd.DataFrame | None = None,
    source_details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bar_dates = pd.to_datetime(bars["date"], errors="raise") if not bars.empty else pd.Series(dtype="datetime64[ns]")
    dataset_counts = {
        "daily_bars_rows": int(len(bars)),
        "benchmark_rows": 0 if benchmark is None else int(len(benchmark)),
        "trading_calendar_rows": 0 if trading_calendar is None else int(len(trading_calendar)),
        "universe_rows": 0 if universe is None else int(len(universe)),
        "adjustment_factor_rows": 0 if adjustment_factors is None else int(len(adjustment_factors)),
    }
    return {
        "schema_version": "v1",
        "source_name": source_name,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "date_range": {
            "start_date": None if bars.empty else pd.Timestamp(bar_dates.min()).date().isoformat(),
            "end_date": None if bars.empty else pd.Timestamp(bar_dates.max()).date().isoformat(),
        },
        "symbol_count": 0 if bars.empty else int(bars["symbol"].nunique()),
        "dataset_counts": dataset_counts,
        "fields": {
            "daily_bars": list(bars.columns),
            "benchmark": [] if benchmark is None else list(benchmark.columns),
            "trading_calendar": [] if trading_calendar is None else list(trading_calendar.columns),
            "universe": [] if universe is None else list(universe.columns),
            "adjustment_factors": [] if adjustment_factors is None else list(adjustment_factors.columns),
        },
        "source_details": source_details or {},
    }


def write_data_manifest(
    manifest: dict[str, Any],
    output_path: str | Path,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=True, indent=2), encoding="utf-8")
    return path


def load_data_manifest(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
