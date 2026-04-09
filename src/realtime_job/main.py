"""Main entry point for realtime stock price updater."""

from __future__ import annotations

import datetime as dt
import os
import sys
import time

from .db import close_pool, get_enabled_stocks, init_schema, is_trading_date, upsert_prices
from .sources import fetch_prices


def main() -> None:
    from dotenv import load_dotenv

    load_dotenv()

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        print("ERROR: DATABASE_URL 未設定", file=sys.stderr)
        sys.exit(1)

    t0 = time.monotonic()

    try:
        init_schema(database_url)

        if not is_trading_date(database_url):
            print("非交易日，跳過")
            return

        enabled = get_enabled_stocks(database_url)
        if not enabled:
            print("無啟用的股票")
            return

        # Filter out stocks without market_type
        stocks_with_market = [(s, n, m) for s, n, m in enabled if m]
        skipped = len(enabled) - len(stocks_with_market)
        if skipped:
            print(f"WARNING: {skipped} 支股票缺少 market_type，已跳過")

        if not stocks_with_market:
            print("無可查詢的股票（皆缺少 market_type）")
            return

        print(f"查詢 {len(stocks_with_market)} 支股票...")

        today = dt.date.today()
        rows, data_date = fetch_prices(stocks_with_market)

        if data_date and data_date != today:
            print(f"日期不匹配 (yfinance={data_date}, today={today})，跳過")
            return

        if rows:
            count = upsert_prices(database_url, today, rows)
            elapsed = time.monotonic() - t0
            print(f"完成: {count} 支股票價格已更新 ({elapsed:.1f}s)")
        else:
            print("無資料可更新")

    finally:
        close_pool()
