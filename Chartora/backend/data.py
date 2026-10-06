from pathlib import Path
import pandas as pd
import yfinance as yf

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        raise ValueError("No market data was returned.")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    needed = ["Open", "High", "Low", "Close", "Volume"]
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise ValueError(f"Market data is missing columns: {missing}")

    df = df[needed].copy()
    df = df.dropna()
    df.index = pd.to_datetime(df.index)
    df = df[~df.index.duplicated(keep="last")]
    return df


def download_market_data(symbol: str, period: str, interval: str) -> pd.DataFrame:
    symbol = symbol.strip().upper()

    # Let Yahoo Finance enforce the exact provider availability, but give a clear
    # message for the common intraday limitation.
    if interval in {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"}:
        if period not in {"1d", "5d", "1mo", "3mo", "6mo", "1y"}:
            raise ValueError(
                "For intraday intervals, choose a shorter period such as 1mo, 3mo, 6mo or 1y. "
                "The data provider limits how far back intraday history can be requested."
            )

    df = yf.download(
        symbol,
        period=period,
        interval=interval,
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    return _clean(df)


def cache_path(symbol: str, period: str, interval: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in symbol)
    return DATA_DIR / f"{safe}_{period}_{interval}.csv"


def get_market_data(symbol: str, period: str, interval: str, use_cache: bool = True) -> pd.DataFrame:
    path = cache_path(symbol, period, interval)

    if use_cache and path.exists():
        try:
            cached = pd.read_csv(path, index_col=0, parse_dates=True)
            cached = _clean(cached)
            # Cache is convenient, but refresh daily/intraday data when it is old.
            age_hours = (pd.Timestamp.now(tz="UTC").tz_localize(None) - cached.index[-1].tz_localize(None)).total_seconds() / 3600
            if age_hours < 24 and len(cached) > 300:
                return cached
        except Exception:
            pass

    df = download_market_data(symbol, period, interval)
    df.to_csv(path)
    return df
