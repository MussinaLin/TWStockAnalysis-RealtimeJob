"""Database operations for realtime price updater."""

from __future__ import annotations

import datetime as dt
import logging
import math

import psycopg
from psycopg_pool import ConnectionPool

logger = logging.getLogger("realtime_job")

_pool: ConnectionPool | None = None
_partition_years: set[int] = set()


def get_pool(database_url: str) -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(database_url, min_size=1, max_size=3)
        _pool.wait()
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def ensure_partition(conn: psycopg.Connection, trade_date: dt.date) -> None:
    """Create yearly partition for stock_daily_raw if missing."""
    year = trade_date.year
    if year in _partition_years:
        return

    start = f"{year}-01-01"
    end = f"{year + 1}-01-01"
    part_name = f"stock_daily_raw_{year}"
    conn.execute(
        f"CREATE TABLE IF NOT EXISTS {part_name} PARTITION OF stock_daily_raw"
        f" FOR VALUES FROM ('{start}') TO ('{end}')"
    )
    logger.info("確認 partition %s 存在", part_name)
    _partition_years.add(year)


def init_schema(database_url: str) -> None:
    """Create config table and add market_type column if not exists."""
    pool = get_pool(database_url)
    with pool.connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key          VARCHAR(50)  PRIMARY KEY,
                value        TEXT         NOT NULL,
                created_time TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
                updated_time TIMESTAMPTZ  NOT NULL DEFAULT NOW()
            )
        """)
        conn.execute("""
            ALTER TABLE stocks ADD COLUMN IF NOT EXISTS market_type VARCHAR(4)
        """)
        conn.commit()


def _parse_trading_day(value: str | None) -> bool:
    """解析 config.is_trading_day 的值。

    fail-open：讀不到（None）或無法辨識的值一律視為 True 照常執行，
    開關只是輔助，缺了不能影響盤中更新。
    """
    if value is None:
        logger.warning("config 表查無 is_trading_day，視為交易日照常執行")
        return True

    normalized = value.strip().lower()
    if normalized in ("false", "0", "no"):
        return False
    if normalized in ("true", "1", "yes"):
        return True

    logger.warning("config.is_trading_day 值無法辨識（%r），視為交易日照常執行", value)
    return True


def is_trading_day(database_url: str) -> bool:
    """讀取 config.is_trading_day；讀取失敗同樣 fail-open 視為交易日。"""
    try:
        pool = get_pool(database_url)
        with pool.connection() as conn:
            row = conn.execute(
                "SELECT value FROM config WHERE key = 'is_trading_day'"
            ).fetchone()
    except psycopg.Error as exc:
        logger.warning("讀取 config.is_trading_day 失敗（%s），視為交易日照常執行", exc)
        return True
    return _parse_trading_day(row[0] if row else None)


def get_enabled_stocks(database_url: str) -> list[tuple[str, str, str | None]]:
    """Return list of (symbol, name, market_type) for enabled stocks."""
    pool = get_pool(database_url)
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT symbol, name, market_type"
            " FROM stocks WHERE enabled = TRUE ORDER BY symbol"
        ).fetchall()
    return [(r[0], r[1], r[2]) for r in rows]


def _safe(val):
    if val is None:
        return None
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    return val


def _build_params(
    trade_date: dt.date,
    rows: list[dict],
) -> tuple[list[tuple], int]:
    """Build INSERT params, dropping rows whose OHLC is not fully populated.

    Defense-in-depth: even if upstream lets a NaN/None through, no row with a
    missing open/high/low/close is ever written. Returns (params, skipped).
    """
    params: list[tuple] = []
    skipped = 0
    for r in rows:
        o = _safe(r.get("open"))
        h = _safe(r.get("high"))
        low = _safe(r.get("low"))
        c = _safe(r.get("close"))
        if None in (o, h, low, c):
            skipped += 1
            continue
        params.append((r["symbol"], trade_date, r.get("name"), o, h, low, c))
    return params, skipped


def upsert_prices(
    database_url: str,
    trade_date: dt.date,
    rows: list[dict],
) -> int:
    """Upsert price data into stock_daily_raw.

    Each row dict: {symbol, name, open, high, low, close}.
    Rows with any missing OHLC value are skipped (never written as NULL).
    Returns number of rows upserted.
    """
    if not rows:
        return 0

    params, skipped = _build_params(trade_date, rows)
    if skipped:
        logger.warning("upsert: %d 筆因 OHLC 含 None 跳過，不寫入", skipped)
    if not params:
        return 0

    pool = get_pool(database_url)
    sql = """
        INSERT INTO stock_daily_raw (symbol, trade_date, name, open, high, low, close)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (symbol, trade_date) DO UPDATE SET
            name  = COALESCE(NULLIF(EXCLUDED.name, ''), stock_daily_raw.name),
            open  = COALESCE(EXCLUDED.open, stock_daily_raw.open),
            high  = COALESCE(EXCLUDED.high, stock_daily_raw.high),
            low   = COALESCE(EXCLUDED.low, stock_daily_raw.low),
            close = COALESCE(EXCLUDED.close, stock_daily_raw.close)
    """

    with pool.connection() as conn:
        ensure_partition(conn, trade_date)
        with conn.cursor() as cur:
            cur.executemany(sql, params)
        conn.commit()

    return len(params)
