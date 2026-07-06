from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from io import StringIO
from time import sleep
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd

GUIDEBEE_BASE_URL = "https://raw.githubusercontent.com/guidebee/china-stock-data/main/data/price"
GUIDEBEE_SOURCE_COLUMNS = ["symbol", "date", "open", "close", "high", "low", "volume", "amount"]
GUIDEBEE_OUTPUT_COLUMNS = ["date", "symbol", "open", "high", "low", "close", "volume", "amount"]
GUIDEBEE_A_SHARE_B_SHARE_PREFIXES = ("200", "900")


def build_guidebee_daily_url(
    trading_date: str | pd.Timestamp,
    base_url: str = GUIDEBEE_BASE_URL,
) -> str:
    """Build a raw GitHub URL for a single trading day."""
    normalized = pd.Timestamp(trading_date).date()
    return (
        f"{base_url}/{normalized:%Y/%m}/stock_price_{normalized:%Y_%m_%d}.csv"
    )


def download_guidebee_daily_bars(
    start_date: str | pd.Timestamp,
    end_date: str | pd.Timestamp,
    *,
    include_b_shares: bool = False,
    base_url: str = GUIDEBEE_BASE_URL,
    max_workers: int = 8,
    timeout: float = 30.0,
    retries: int = 3,
) -> pd.DataFrame:
    """Download Guidebee daily stock data and normalize it for this project.

    The downloader walks a weekday calendar between `start_date` and `end_date`, skips
    non-trading days that return 404, and returns a single normalized DataFrame.
    """
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    if end < start:
        raise ValueError("end_date must be on or after start_date")
    if max_workers <= 0:
        raise ValueError("max_workers must be positive")
    if retries <= 0:
        raise ValueError("retries must be positive")

    candidate_dates = list(pd.bdate_range(start, end))
    if not candidate_dates:
        return _empty_guidebee_frame()

    frames: list[pd.DataFrame] = []
    if max_workers == 1:
        for trading_date in candidate_dates:
            frame = fetch_guidebee_daily_bars(
                trading_date,
                include_b_shares=include_b_shares,
                base_url=base_url,
                timeout=timeout,
                retries=retries,
            )
            if frame is not None and not frame.empty:
                frames.append(frame)
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    fetch_guidebee_daily_bars,
                    trading_date,
                    include_b_shares=include_b_shares,
                    base_url=base_url,
                    timeout=timeout,
                    retries=retries,
                ): trading_date
                for trading_date in candidate_dates
            }
            for future in as_completed(futures):
                frame = future.result()
                if frame is not None and not frame.empty:
                    frames.append(frame)

    if not frames:
        return _empty_guidebee_frame()

    bars = pd.concat(frames, ignore_index=True)
    bars = bars.drop_duplicates(["date", "symbol"]).sort_values(["date", "symbol"]).reset_index(
        drop=True
    )
    return bars[GUIDEBEE_OUTPUT_COLUMNS]


def fetch_guidebee_daily_bars(
    trading_date: str | pd.Timestamp,
    *,
    include_b_shares: bool = False,
    base_url: str = GUIDEBEE_BASE_URL,
    timeout: float = 30.0,
    retries: int = 3,
) -> pd.DataFrame | None:
    """Fetch one Guidebee daily CSV and normalize its rows."""
    url = build_guidebee_daily_url(trading_date, base_url=base_url)
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})

    for attempt in range(1, retries + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                text = response.read().decode("utf-8-sig")
            raw = pd.read_csv(StringIO(text), header=None, names=GUIDEBEE_SOURCE_COLUMNS)
            return normalize_guidebee_daily_bars(raw, include_b_shares=include_b_shares)
        except HTTPError as exc:
            if exc.code == 404:
                return None
            if exc.code in {429, 500, 502, 503, 504} and attempt < retries:
                sleep(0.5 * attempt)
                continue
            raise
        except URLError:
            if attempt < retries:
                sleep(0.5 * attempt)
                continue
            raise

    return None


def normalize_guidebee_daily_bars(
    raw_bars: pd.DataFrame,
    *,
    include_b_shares: bool = False,
) -> pd.DataFrame:
    """Convert Guidebee rows into the project's daily bar contract."""
    missing = set(GUIDEBEE_SOURCE_COLUMNS).difference(raw_bars.columns)
    if missing:
        raise ValueError(f"Guidebee data is missing required columns: {sorted(missing)}")

    bars = raw_bars.copy()
    bars["date"] = pd.to_datetime(bars["date"], errors="raise")
    bars["symbol"] = bars["symbol"].map(_normalize_guidebee_symbol)
    bars["amount"] = pd.to_numeric(bars["amount"], errors="raise")
    for column in ["open", "close", "high", "low"]:
        bars[column] = pd.to_numeric(bars[column], errors="raise")
    bars["volume"] = pd.to_numeric(bars["volume"], errors="raise").astype("int64")

    if not include_b_shares:
        bars = bars[~bars["symbol"].str[:3].isin(GUIDEBEE_A_SHARE_B_SHARE_PREFIXES)]

    bars = bars[GUIDEBEE_OUTPUT_COLUMNS]
    bars = bars.drop_duplicates(["date", "symbol"]).sort_values(["date", "symbol"]).reset_index(
        drop=True
    )
    return bars


def _normalize_guidebee_symbol(symbol: str) -> str:
    text = str(symbol).strip()
    if len(text) != 8:
        raise ValueError(f"Unexpected Guidebee symbol format: {symbol}")

    prefix = text[:2].lower()
    code = text[2:]
    if not code.isdigit():
        raise ValueError(f"Unexpected Guidebee symbol code: {symbol}")

    suffix_map = {"sh": "SH", "sz": "SZ", "bj": "BJ"}
    if prefix not in suffix_map:
        raise ValueError(f"Unexpected Guidebee symbol prefix: {symbol}")

    return f"{code}.{suffix_map[prefix]}"


def _empty_guidebee_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=GUIDEBEE_OUTPUT_COLUMNS)
