"""Unit tests for sources helpers."""

import datetime as dt
import math

import pandas as pd

from realtime_job.sources import _safe_float, fetch_prices


def test_safe_float_none():
    assert _safe_float(None) is None


def test_safe_float_nan():
    assert _safe_float(float("nan")) is None


def test_safe_float_inf():
    assert _safe_float(float("inf")) is None
    assert _safe_float(float("-inf")) is None


def test_safe_float_zero_preserved():
    # 0.0 is falsy but valid — must NOT be treated as missing.
    assert _safe_float(0.0) == 0.0


def test_safe_float_normal():
    assert _safe_float(123.45) == 123.45
    assert _safe_float("67.8") == 67.8


def test_safe_float_invalid_string():
    assert _safe_float("abc") is None


def test_safe_float_nan_via_math():
    assert math.isnan(float("nan"))  # sanity: ensure our nan input is real nan


def _yf_frame_with_stale_symbol() -> pd.DataFrame:
    """模擬 yf.download 多檔回傳：3665 停牌、最後一根停在 06-09，2330 有 06-10 資料。

    多檔下載時 index 是各檔日期的聯集，停牌檔會讓 index 多出舊日期那一列。
    """
    idx = pd.DatetimeIndex(
        [pd.Timestamp("2026-06-09"), pd.Timestamp("2026-06-10")], name="Date"
    )
    cols = pd.MultiIndex.from_product(
        [["Open", "High", "Low", "Close"], ["2330.TW", "3665.TW"]],
        names=["Price", "Ticker"],
    )
    df = pd.DataFrame(float("nan"), index=idx, columns=cols)
    for field, val in [
        ("Open", 2120.0),
        ("High", 2180.0),
        ("Low", 2090.0),
        ("Close", 2155.0),
    ]:
        df.loc["2026-06-09", (field, "3665.TW")] = val
    for field, val in [
        ("Open", 1000.0),
        ("High", 1010.0),
        ("Low", 995.0),
        ("Close", 1005.0),
    ]:
        df.loc["2026-06-10", (field, "2330.TW")] = val
    return df


def test_fetch_prices_uses_latest_date_when_one_symbol_stale(monkeypatch):
    monkeypatch.setattr(
        "realtime_job.sources.yf.download",
        lambda *args, **kwargs: _yf_frame_with_stale_symbol(),
    )

    rows, data_date = fetch_prices(
        [("2330", "台積電", "twse"), ("3665", "貿聯-KY", "twse")]
    )

    assert data_date == dt.date(2026, 6, 10)
    assert [r["symbol"] for r in rows] == ["2330"]
    assert rows[0]["open"] == 1000.0
    assert rows[0]["high"] == 1010.0
    assert rows[0]["low"] == 995.0
    assert rows[0]["close"] == 1005.0
