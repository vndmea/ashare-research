from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from time import sleep

import pandas as pd

from ashare_research.data.manifest import build_data_manifest, write_data_manifest

BAOSTOCK_SOURCE_COLUMNS = [
    "date",
    "symbol",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
]
BAOSTOCK_OUTPUT_COLUMNS = BAOSTOCK_SOURCE_COLUMNS
BAOSTOCK_DAILY_FIELDS = ",".join(
    ["date", "code", "open", "high", "low", "close", "volume", "amount"]
)
BAOSTOCK_BENCHMARK_FIELDS = ",".join(["date", "code", "close"])
DEFAULT_BENCHMARK_SYMBOL = "000300.SH"


@dataclass(frozen=True)
class BaostockDownloadResult:
    bars: pd.DataFrame
    benchmark: pd.DataFrame | None
    trading_calendar: pd.DataFrame
    universe: pd.DataFrame
    manifest_path: Path | None = None


def download_baostock_daily_bars(
    start_date: str | pd.Timestamp,
    end_date: str | pd.Timestamp,
    *,
    symbols: list[str] | None = None,
    max_workers: int = 4,
    retries: int = 3,
) -> pd.DataFrame:
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    if end < start:
        raise ValueError("end_date must be on or after start_date")
    if max_workers <= 0:
        raise ValueError("max_workers must be positive")
    if retries <= 0:
        raise ValueError("retries must be positive")

    target_symbols = symbols if symbols is not None else list_all_a_share_symbols()
    if not target_symbols:
        return _empty_baostock_frame()

    frames: list[pd.DataFrame] = []
    if max_workers == 1:
        for symbol in target_symbols:
            frame = fetch_baostock_daily_bars(symbol, start, end, retries=retries)
            if frame is not None and not frame.empty:
                frames.append(frame)
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(fetch_baostock_daily_bars, symbol, start, end, retries=retries): symbol
                for symbol in target_symbols
            }
            for future in as_completed(futures):
                frame = future.result()
                if frame is not None and not frame.empty:
                    frames.append(frame)

    if not frames:
        return _empty_baostock_frame()

    bars = pd.concat(frames, ignore_index=True)
    bars = bars.drop_duplicates(["date", "symbol"]).sort_values(["date", "symbol"]).reset_index(
        drop=True
    )
    return bars[BAOSTOCK_OUTPUT_COLUMNS]


def fetch_baostock_daily_bars(
    symbol: str,
    start_date: str | pd.Timestamp,
    end_date: str | pd.Timestamp,
    *,
    retries: int = 3,
) -> pd.DataFrame | None:
    code = _to_baostock_symbol(symbol)
    start = pd.Timestamp(start_date).date().isoformat()
    end = pd.Timestamp(end_date).date().isoformat()

    with _baostock_session():
        import baostock as bs

        for attempt in range(1, retries + 1):
            rs = bs.query_history_k_data_plus(
                code,
                BAOSTOCK_DAILY_FIELDS,
                start_date=start,
                end_date=end,
                frequency="d",
                adjustflag="3",
            )
            if rs.error_code != "0":
                if attempt < retries:
                    sleep(0.5 * attempt)
                    continue
                raise RuntimeError(f"baostock query failed for {code}: {rs.error_msg}")

            data = []
            while rs.next():
                data.append(rs.get_row_data())
            if not data:
                return None
            frame = pd.DataFrame(data, columns=rs.fields)
            return normalize_baostock_daily_bars(frame)

    return None


def list_all_a_share_symbols(*, trading_date: str | None = None) -> list[str]:
    with _baostock_session():
        import baostock as bs

        rs = bs.query_stock_basic()
        if rs.error_code != "0":
            raise RuntimeError(f"baostock query_stock_basic failed: {rs.error_msg}")

        symbols: list[str] = []
        while rs.next():
            row = rs.get_row_data()
            code = row[0]
            stock_type = row[4] if len(row) > 4 else ""
            if stock_type != "1":
                continue
            if _is_a_share_equity(code):
                symbols.append(_normalize_baostock_symbol(code))
        return sorted(set(symbols))


def build_baostock_download_bundle(
    start_date: str | pd.Timestamp,
    end_date: str | pd.Timestamp,
    *,
    symbols: list[str] | None = None,
    benchmark_symbol: str | None = DEFAULT_BENCHMARK_SYMBOL,
    max_workers: int = 4,
    retries: int = 3,
) -> BaostockDownloadResult:
    bars = download_baostock_daily_bars(
        start_date,
        end_date,
        symbols=symbols,
        max_workers=max_workers,
        retries=retries,
    )
    benchmark = (
        fetch_baostock_benchmark_bars(benchmark_symbol, start_date, end_date, retries=retries)
        if benchmark_symbol
        else None
    )
    trading_calendar = bars[["date"]].drop_duplicates().sort_values("date").reset_index(drop=True)
    universe = bars[["date", "symbol"]].drop_duplicates().sort_values(["date", "symbol"]).reset_index(
        drop=True
    )
    return BaostockDownloadResult(
        bars=bars,
        benchmark=benchmark,
        trading_calendar=trading_calendar,
        universe=universe,
    )


def write_baostock_download_bundle(
    bundle: BaostockDownloadResult,
    *,
    output: str | Path,
    benchmark_output: str | Path | None,
    calendar_output: str | Path,
    universe_output: str | Path,
    manifest_output: str | Path,
    source_details: dict[str, object] | None = None,
) -> BaostockDownloadResult:
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bundle.bars.to_csv(output_path, index=False, date_format="%Y-%m-%d")

    benchmark_path: Path | None = None
    if benchmark_output is not None and bundle.benchmark is not None and not bundle.benchmark.empty:
        benchmark_path = Path(benchmark_output)
        benchmark_path.parent.mkdir(parents=True, exist_ok=True)
        bundle.benchmark.to_csv(benchmark_path, index=False, date_format="%Y-%m-%d")

    calendar_path = Path(calendar_output)
    calendar_path.parent.mkdir(parents=True, exist_ok=True)
    bundle.trading_calendar.to_csv(calendar_path, index=False, date_format="%Y-%m-%d")

    universe_path = Path(universe_output)
    universe_path.parent.mkdir(parents=True, exist_ok=True)
    bundle.universe.to_csv(universe_path, index=False, date_format="%Y-%m-%d")

    manifest = build_data_manifest(
        source_name="baostock",
        bars=bundle.bars,
        benchmark=bundle.benchmark,
        trading_calendar=bundle.trading_calendar,
        universe=bundle.universe,
        source_details=source_details or {},
    )
    manifest_path = write_data_manifest(manifest, manifest_output)
    return BaostockDownloadResult(
        bars=bundle.bars,
        benchmark=bundle.benchmark,
        trading_calendar=bundle.trading_calendar,
        universe=bundle.universe,
        manifest_path=manifest_path,
    )


def normalize_baostock_daily_bars(raw_bars: pd.DataFrame) -> pd.DataFrame:
    normalized = raw_bars.rename(columns={"code": "symbol"}).copy()
    missing = set(BAOSTOCK_SOURCE_COLUMNS).difference(normalized.columns)
    if missing:
        raise ValueError(f"Baostock data is missing required columns: {sorted(missing)}")

    bars = normalized.copy()
    bars["date"] = pd.to_datetime(bars["date"], errors="raise")
    bars["symbol"] = bars["symbol"].map(_from_baostock_symbol)
    for column in ["open", "high", "low", "close", "amount"]:
        bars[column] = pd.to_numeric(bars[column], errors="raise")
    bars["volume"] = pd.to_numeric(bars["volume"], errors="raise").astype("int64")
    bars = bars[BAOSTOCK_OUTPUT_COLUMNS]
    bars = bars.drop_duplicates(["date", "symbol"]).sort_values(["date", "symbol"]).reset_index(
        drop=True
    )
    return bars


def fetch_baostock_benchmark_bars(
    symbol: str,
    start_date: str | pd.Timestamp,
    end_date: str | pd.Timestamp,
    *,
    retries: int = 3,
) -> pd.DataFrame | None:
    code = _to_baostock_symbol(symbol)
    start = pd.Timestamp(start_date).date().isoformat()
    end = pd.Timestamp(end_date).date().isoformat()

    with _baostock_session():
        import baostock as bs

        for attempt in range(1, retries + 1):
            rs = bs.query_history_k_data_plus(
                code,
                BAOSTOCK_BENCHMARK_FIELDS,
                start_date=start,
                end_date=end,
                frequency="d",
                adjustflag="3",
            )
            if rs.error_code != "0":
                if attempt < retries:
                    sleep(0.5 * attempt)
                    continue
                raise RuntimeError(f"baostock benchmark query failed for {code}: {rs.error_msg}")
            data = []
            while rs.next():
                data.append(rs.get_row_data())
            if not data:
                return None
            return normalize_baostock_benchmark_bars(pd.DataFrame(data, columns=rs.fields))
    return None


def normalize_baostock_benchmark_bars(raw_bars: pd.DataFrame) -> pd.DataFrame:
    normalized = raw_bars.rename(columns={"code": "symbol"}).copy()
    required = {"date", "symbol", "close"}
    missing = required.difference(normalized.columns)
    if missing:
        raise ValueError(f"Baostock benchmark data is missing required columns: {sorted(missing)}")
    benchmark = normalized.copy()
    benchmark["date"] = pd.to_datetime(benchmark["date"], errors="raise")
    benchmark["symbol"] = benchmark["symbol"].map(_from_baostock_symbol)
    benchmark["close"] = pd.to_numeric(benchmark["close"], errors="raise")
    benchmark = benchmark[["date", "symbol", "close"]]
    benchmark = benchmark.drop_duplicates(["date"]).sort_values("date").reset_index(drop=True)
    return benchmark


def _to_baostock_symbol(symbol: str) -> str:
    text = str(symbol).strip()
    if "." in text:
        left, right = text.split(".", maxsplit=1)
        left = left.strip()
        right = right.strip()
        if left.isdigit() and right.upper() in {"SH", "SZ", "BJ"}:
            return f"{right.lower()}.{left}"
        if left.lower() in {"sh", "sz", "bj"} and right.isdigit():
            return f"{left.lower()}.{right}"
    else:
        if text.isdigit():
            raise ValueError(f"Cannot infer exchange for symbol without suffix: {symbol}")
    raise ValueError(f"Unexpected Baostock symbol format: {symbol}")


def _from_baostock_symbol(symbol: str) -> str:
    text = str(symbol).strip()
    if "." in text:
        left, right = text.split(".", maxsplit=1)
        left = left.strip()
        right = right.strip()
        if left.lower() in {"sh", "sz", "bj"} and right.isdigit():
            return f"{right}.{left.upper()}"
        if left.isdigit() and right.upper() in {"SH", "SZ", "BJ"}:
            return f"{left}.{right.upper()}"
    raise ValueError(f"Unexpected Baostock symbol format: {symbol}")


def normalize_baostock_symbol(symbol: str) -> str:
    """Normalize a symbol from either project or baostock style into project style."""
    text = str(symbol).strip()
    if "." not in text:
        raise ValueError(f"Unexpected symbol format: {symbol}")
    left, right = text.split(".", maxsplit=1)
    if left.isdigit() and right.upper() in {"SH", "SZ", "BJ"}:
        return f"{left}.{right.upper()}"
    if left.lower() in {"sh", "sz", "bj"} and right.isdigit():
        return f"{right}.{left.upper()}"
    raise ValueError(f"Unexpected symbol format: {symbol}")


def _is_a_share_equity(code: str) -> bool:
    normalized = str(code).strip().lower()
    return normalized.startswith("sh.6") or normalized.startswith("sz.0") or normalized.startswith(
        "sz.3"
    )


@contextmanager
def _baostock_session():
    import baostock as bs

    login_result = bs.login()
    if login_result.error_code != "0":
        raise RuntimeError(f"baostock login failed: {login_result.error_msg}")
    try:
        yield
    finally:
        bs.logout()


def _empty_baostock_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=BAOSTOCK_OUTPUT_COLUMNS)
