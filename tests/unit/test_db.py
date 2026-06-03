"""Unit tests for db helpers."""

import datetime as dt

from realtime_job.db import _build_params, _safe

TRADE_DATE = dt.date(2026, 6, 3)


def _row(**kw):
    base = {
        "symbol": "2330",
        "name": "台積電",
        "open": 1000.0,
        "high": 1010.0,
        "low": 990.0,
        "close": 1005.0,
    }
    base.update(kw)
    return base


def test_safe_none():
    assert _safe(None) is None


def test_safe_nan_inf():
    assert _safe(float("nan")) is None
    assert _safe(float("inf")) is None


def test_safe_passthrough():
    assert _safe(12.3) == 12.3
    assert _safe(0.0) == 0.0


def test_build_params_complete_row_kept():
    params, skipped = _build_params(TRADE_DATE, [_row()])
    assert skipped == 0
    assert params == [("2330", TRADE_DATE, "台積電", 1000.0, 1010.0, 990.0, 1005.0)]


def test_build_params_skips_row_with_none_field():
    params, skipped = _build_params(TRADE_DATE, [_row(open=None)])
    assert params == []
    assert skipped == 1


def test_build_params_skips_row_with_nan_field():
    params, skipped = _build_params(TRADE_DATE, [_row(high=float("nan"))])
    assert params == []
    assert skipped == 1


def test_build_params_close_zero_not_skipped():
    # 0.0 is a valid value, not "missing".
    params, skipped = _build_params(TRADE_DATE, [_row(close=0.0)])
    assert skipped == 0
    assert params[0][6] == 0.0


def test_build_params_mixed():
    rows = [_row(symbol="2330"), _row(symbol="0050", low=None), _row(symbol="2317")]
    params, skipped = _build_params(TRADE_DATE, rows)
    assert skipped == 1
    assert [p[0] for p in params] == ["2330", "2317"]


def test_build_params_empty():
    assert _build_params(TRADE_DATE, []) == ([], 0)
