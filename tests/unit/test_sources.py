"""Unit tests for sources helpers."""

import math

from realtime_job.sources import _safe_float


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
