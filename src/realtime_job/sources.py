"""Data source for realtime stock prices via yfinance."""

from __future__ import annotations

import datetime as dt
import math

import yfinance as yf


def _safe_float(val) -> float | None:
    """Convert to float, returning None for NaN/Inf."""
    if val is None:
        return None
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def fetch_prices(
    stocks: list[tuple[str, str, str]],
) -> tuple[list[dict], dt.date | None]:
    """Fetch OHLCV for given stocks via yfinance.

    Args:
        stocks: list of (symbol, name, market_type) where market_type is 'twse' or 'tpex'.

    Returns:
        (list of {symbol, name, open, high, low, close}, data_date).
    """
    if not stocks:
        return [], None

    # Build yfinance symbols: 2330 -> 2330.TW, 8299 -> 8299.TWO
    suffix_map = {"twse": ".TW", "tpex": ".TWO"}
    yf_to_stock: dict[str, tuple[str, str]] = {}  # yf_symbol -> (symbol, name)
    for symbol, name, market_type in stocks:
        suffix = suffix_map.get(market_type, "")
        if not suffix:
            continue
        yf_sym = f"{symbol}{suffix}"
        yf_to_stock[yf_sym] = (symbol, name)

    if not yf_to_stock:
        return [], None

    yf_symbols = list(yf_to_stock.keys())
    data = yf.download(
        yf_symbols,
        period="1d",
        interval="1d",
        progress=False,
        auto_adjust=False,
        multi_level_index=True,
    )

    if data.empty:
        return [], None

    data_date = data.index[0].date() if len(data.index) > 0 else None

    results = []
    for yf_sym, (symbol, name) in yf_to_stock.items():
        if yf_sym not in data["Close"].columns:
            continue
        row_close = _safe_float(data["Close"][yf_sym].iloc[0])
        row_open = _safe_float(data["Open"][yf_sym].iloc[0])
        row_high = _safe_float(data["High"][yf_sym].iloc[0])
        row_low = _safe_float(data["Low"][yf_sym].iloc[0])

        if row_close is None:
            continue

        results.append({
            "symbol": symbol,
            "name": name,
            "open": row_open,
            "high": row_high,
            "low": row_low,
            "close": row_close,
        })

    return results, data_date
