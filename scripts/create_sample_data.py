from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from ashare_research.data.manifest import build_data_manifest, write_data_manifest


def main() -> None:
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2020-01-01", "2022-12-31")
    symbols = ["000001.SZ", "000002.SZ", "600000.SH", "600519.SH", "300750.SZ"]

    rows = []
    for symbol_index, symbol in enumerate(symbols):
        close = 10.0 + symbol_index * 5.0
        for date in dates:
            daily_return = rng.normal(0.0004, 0.018)
            open_price = close * (1.0 + rng.normal(0.0, 0.004))
            close = max(1.0, close * (1.0 + daily_return))
            high = max(open_price, close) * (1.0 + rng.uniform(0.0, 0.012))
            low = min(open_price, close) * (1.0 - rng.uniform(0.0, 0.012))
            volume = int(rng.integers(500_000, 8_000_000))
            rows.append(
                {
                    "date": date.date().isoformat(),
                    "symbol": symbol,
                    "open": round(open_price, 4),
                    "high": round(high, 4),
                    "low": round(low, 4),
                    "close": round(close, 4),
                    "volume": volume,
                    "amount": round(close * volume, 4),
                    "adj_factor": 1.0,
                    "is_suspended": False,
                    "limit_up": False,
                    "limit_down": False,
                    "tradable": True,
                    "st_status": "",
                }
            )

    bars_frame = pd.DataFrame(rows)
    output_path = Path("data/raw/daily_bars.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bars_frame.to_csv(output_path, index=False)

    adjustment_factor_path = Path("data/raw/adjustment_factors.csv")
    adjustment_factors = bars_frame[["date", "symbol", "adj_factor"]].copy()
    adjustment_factors.to_csv(
        adjustment_factor_path,
        index=False,
    )

    trading_calendar_path = Path("data/raw/trading_calendar.csv")
    trading_calendar = pd.DataFrame({"date": dates.date.astype(str)})
    trading_calendar.to_csv(trading_calendar_path, index=False)

    universe_rows = [
        {"date": date.date().isoformat(), "symbol": symbol}
        for date in dates
        for symbol in symbols
    ]
    universe_path = Path("data/raw/universe.csv")
    universe = pd.DataFrame(universe_rows)
    universe.to_csv(universe_path, index=False)

    benchmark_rows = []
    benchmark_close = 4000.0
    for date in dates:
        daily_return = rng.normal(0.0002, 0.012)
        benchmark_close = max(1000.0, benchmark_close * (1.0 + daily_return))
        benchmark_rows.append(
            {
                "date": date.date().isoformat(),
                "symbol": "000300.SH",
                "close": round(benchmark_close, 4),
            }
        )

    benchmark_path = Path("data/raw/benchmark.csv")
    benchmark = pd.DataFrame(benchmark_rows)
    benchmark.to_csv(benchmark_path, index=False)
    manifest_path = write_data_manifest(
        build_data_manifest(
            source_name="sample_data",
            bars=bars_frame,
            benchmark=benchmark,
            trading_calendar=trading_calendar,
            universe=universe,
            adjustment_factors=adjustment_factors,
            source_details={
                "generator": "scripts/create_sample_data.py",
                "random_seed": 42,
            },
        ),
        Path("data/raw/dataset_manifest.json"),
    )
    print(f"Wrote {len(rows)} daily bar rows to {output_path}")
    print(f"Wrote {len(rows)} adjustment factor rows to {adjustment_factor_path}")
    print(f"Wrote {len(dates)} trading calendar rows to {trading_calendar_path}")
    print(f"Wrote {len(universe_rows)} universe rows to {universe_path}")
    print(f"Wrote {len(benchmark_rows)} benchmark rows to {benchmark_path}")
    print(f"Wrote dataset manifest to {manifest_path}")


if __name__ == "__main__":
    main()
