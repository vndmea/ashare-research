from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from ashare_research.data.guidebee import download_guidebee_daily_bars
from ashare_research.data.manifest import build_data_manifest, write_data_manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download Guidebee A-share daily data into the project format."
    )
    parser.add_argument("--start-date", required=True, help="Start date in YYYY-MM-DD format.")
    parser.add_argument("--end-date", required=True, help="End date in YYYY-MM-DD format.")
    parser.add_argument(
        "--output",
        default="data/raw/daily_bars.csv",
        help="Output CSV path for normalized daily bars.",
    )
    parser.add_argument(
        "--calendar-output",
        default="data/raw/trading_calendar.csv",
        help="Output CSV path for inferred trading dates.",
    )
    parser.add_argument(
        "--universe-output",
        default="data/raw/universe.csv",
        help="Output CSV path for inferred date/symbol universe snapshots.",
    )
    parser.add_argument(
        "--manifest-output",
        default="data/raw/dataset_manifest.json",
        help="Output JSON path for dataset manifest.",
    )
    parser.add_argument(
        "--include-b-shares",
        action="store_true",
        help="Keep Shanghai and Shenzhen B-shares in the output.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Number of parallel download workers.",
    )
    args = parser.parse_args()

    bars = download_guidebee_daily_bars(
        args.start_date,
        args.end_date,
        include_b_shares=args.include_b_shares,
        max_workers=args.workers,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bars.to_csv(output_path, index=False, date_format="%Y-%m-%d")

    calendar_path = Path(args.calendar_output)
    calendar_path.parent.mkdir(parents=True, exist_ok=True)
    trading_calendar = bars[["date"]].drop_duplicates().sort_values("date")
    trading_calendar.to_csv(
        calendar_path,
        index=False,
        date_format="%Y-%m-%d",
    )

    universe_path = Path(args.universe_output)
    universe_path.parent.mkdir(parents=True, exist_ok=True)
    universe = bars[["date", "symbol"]].drop_duplicates().sort_values(["date", "symbol"])
    universe.to_csv(
        universe_path,
        index=False,
        date_format="%Y-%m-%d",
    )
    manifest_path = write_data_manifest(
        build_data_manifest(
            source_name="guidebee",
            bars=bars,
            trading_calendar=trading_calendar,
            universe=universe,
            source_details={
                "downloader": "scripts/download_guidebee_data.py",
                "provider": "guidebee/china-stock-data",
                "start_date": pd.Timestamp(args.start_date).date().isoformat(),
                "end_date": pd.Timestamp(args.end_date).date().isoformat(),
                "include_b_shares": bool(args.include_b_shares),
                "workers": int(args.workers),
            },
        ),
        args.manifest_output,
    )

    print(f"Downloaded {len(bars)} rows to {output_path}")
    print(f"Wrote trading calendar to {calendar_path}")
    print(f"Wrote universe snapshot to {universe_path}")
    print(f"Wrote dataset manifest to {manifest_path}")


if __name__ == "__main__":
    main()
