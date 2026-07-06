from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


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

    output_path = Path("data/raw/daily_bars.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(output_path, index=False)

    adjustment_factor_path = Path("data/raw/adjustment_factors.csv")
    pd.DataFrame(rows)[["date", "symbol", "adj_factor"]].to_csv(
        adjustment_factor_path,
        index=False,
    )

    trading_calendar_path = Path("data/raw/trading_calendar.csv")
    pd.DataFrame({"date": dates.date.astype(str)}).to_csv(trading_calendar_path, index=False)

    universe_rows = [
        {"date": date.date().isoformat(), "symbol": symbol}
        for date in dates
        for symbol in symbols
    ]
    universe_path = Path("data/raw/universe.csv")
    pd.DataFrame(universe_rows).to_csv(universe_path, index=False)

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
    pd.DataFrame(benchmark_rows).to_csv(benchmark_path, index=False)
    print(f"Wrote {len(rows)} daily bar rows to {output_path}")
    print(f"Wrote {len(rows)} adjustment factor rows to {adjustment_factor_path}")
    print(f"Wrote {len(dates)} trading calendar rows to {trading_calendar_path}")
    print(f"Wrote {len(universe_rows)} universe rows to {universe_path}")
    print(f"Wrote {len(benchmark_rows)} benchmark rows to {benchmark_path}")


if __name__ == "__main__":
    main()
