"""Database operations for realtime price updater."""

from __future__ import annotations

import datetime as dt
import math

import psycopg
from psycopg_pool import ConnectionPool

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
            INSERT INTO config (key, value) VALUES ('is_trading_date', 'true')
            ON CONFLICT (key) DO NOTHING
        """)
        conn.execute("""
            ALTER TABLE stocks ADD COLUMN IF NOT EXISTS market_type VARCHAR(4)
        """)
        conn.commit()


def is_trading_date(database_url: str) -> bool:
    pool = get_pool(database_url)
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT value FROM config WHERE key = 'is_trading_date'"
        ).fetchone()
    if row is None:
        return False
    return row[0].lower() == "true"


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


def upsert_prices(
    database_url: str,
    trade_date: dt.date,
    rows: list[dict],
) -> int:
    """Upsert price data into stock_daily_raw.

    Each row dict: {symbol, name, open, high, low, close}.
    Returns number of rows upserted.
    """
    if not rows:
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

    params = []
    for r in rows:
        params.append((
            r["symbol"],
            trade_date,
            r.get("name"),
            _safe(r.get("open")),
            _safe(r.get("high")),
            _safe(r.get("low")),
            _safe(r.get("close")),
        ))

    with pool.connection() as conn:
        ensure_partition(conn, trade_date)
        with conn.cursor() as cur:
            cur.executemany(sql, params)
        conn.commit()

    return len(params)
