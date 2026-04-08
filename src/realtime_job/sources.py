"""Data sources for realtime stock prices."""

from __future__ import annotations

import datetime as dt
import re
import time

import requests

TWSE_MIS_URL = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
TPEX_QUOTES_URL = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"

# TWSE realtime API batch size and delay
_TWSE_BATCH_SIZE = 20
_TWSE_BATCH_DELAY = 0.3


def _parse_roc_date(value: str) -> dt.date | None:
    """Parse ROC date string (e.g. '1150408') to dt.date."""
    text = value.strip()
    if len(text) == 7 and text.isdigit():
        year = int(text[:3]) + 1911
        month = int(text[3:5])
        day = int(text[5:7])
        try:
            return dt.date(year, month, day)
        except ValueError:
            return None
    return None


def _clean_number(value: str) -> float | None:
    """Parse numeric string, stripping commas. Returns None for invalid values."""
    if not value or value.strip() in ("", "-", "--", "---"):
        return None
    text = value.strip().replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def fetch_tpex_quotes(session: requests.Session) -> tuple[list[dict], dt.date | None]:
    """Fetch all TPEX stock quotes from OpenAPI.

    Returns (list of {symbol, name, open, high, low, close}, data_date).
    """
    resp = session.get(TPEX_QUOTES_URL, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    if not isinstance(payload, list) or not payload:
        return [], None

    data_date = _parse_roc_date(payload[0].get("Date", ""))

    results = []
    for item in payload:
        symbol = item.get("SecuritiesCompanyCode", "").strip()
        if not symbol or not re.match(r"^\d{4,6}$", symbol):
            continue

        close_val = _clean_number(item.get("Close", ""))
        if close_val is None:
            continue

        results.append({
            "symbol": symbol,
            "name": item.get("CompanyName", "").strip(),
            "open": _clean_number(item.get("Open", "")),
            "high": _clean_number(item.get("High", "")),
            "low": _clean_number(item.get("Low", "")),
            "close": close_val,
        })

    return results, data_date


def fetch_twse_realtime(
    session: requests.Session,
    symbols: list[str],
) -> tuple[list[dict], dt.date | None]:
    """Fetch realtime prices from TWSE MIS API for given symbols.

    Returns (list of {symbol, name, open, high, low, close}, data_date).
    Queries in batches of 20 with short delays between batches.
    """
    if not symbols:
        return [], None

    results = []
    data_date = None

    for i in range(0, len(symbols), _TWSE_BATCH_SIZE):
        batch = symbols[i : i + _TWSE_BATCH_SIZE]
        ex_ch = "|".join(f"tse_{s}.tw" for s in batch)

        if i > 0:
            time.sleep(_TWSE_BATCH_DELAY)

        resp = session.get(TWSE_MIS_URL, params={"ex_ch": ex_ch}, timeout=15)
        resp.raise_for_status()
        payload = resp.json()

        for item in payload.get("msgArray", []):
            symbol = item.get("c", "").strip()
            if not symbol:
                continue

            # z = last trade price, "-" means no trade yet
            z = item.get("z", "-")
            if z == "-":
                continue

            close_val = _clean_number(z)
            if close_val is None:
                continue

            if data_date is None:
                d = item.get("d", "")
                if d and len(d) == 8:
                    try:
                        data_date = dt.date(int(d[:4]), int(d[4:6]), int(d[6:8]))
                    except ValueError:
                        pass

            results.append({
                "symbol": symbol,
                "name": item.get("n", "").strip(),
                "open": _clean_number(item.get("o", "")),
                "high": _clean_number(item.get("h", "")),
                "low": _clean_number(item.get("l", "")),
                "close": close_val,
            })

    return results, data_date
