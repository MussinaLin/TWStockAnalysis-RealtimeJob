"""Main entry point for realtime stock price updater."""

from __future__ import annotations

import datetime as dt
import os
import sys
import time

import requests

from .db import close_pool, get_enabled_stocks, init_config_table, is_trading_date, upsert_prices
from .sources import fetch_tpex_quotes, fetch_twse_realtime


def main() -> None:
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        print("ERROR: DATABASE_URL 未設定", file=sys.stderr)
        sys.exit(1)

    t0 = time.monotonic()

    try:
        # Ensure config table exists
        init_config_table(database_url)

        # Check if today is a trading date
        if not is_trading_date(database_url):
            print("非交易日，跳過")
            return

        # Get enabled stocks
        enabled = get_enabled_stocks(database_url)
        if not enabled:
            print("無啟用的股票")
            return

        enabled_symbols = {s for s, _ in enabled}
        print(f"啟用股票: {len(enabled_symbols)} 支")

        session = requests.Session()
        session.headers["User-Agent"] = "TWStockRealtimeJob/0.1"

        today = dt.date.today()
        all_rows: list[dict] = []

        # 1. Fetch TPEX quotes (all OTC stocks at once)
        tpex_rows, tpex_date = fetch_tpex_quotes(session)
        tpex_symbols_found: set[str] = set()

        if tpex_date and tpex_date == today:
            for row in tpex_rows:
                if row["symbol"] in enabled_symbols:
                    all_rows.append(row)
                    tpex_symbols_found.add(row["symbol"])
            print(f"TPEX: {len(tpex_symbols_found)} 支命中")
        else:
            print(f"TPEX: 日期不匹配 (API={tpex_date}, today={today})，跳過")

        # 2. Remaining symbols → TWSE realtime API
        twse_symbols = sorted(enabled_symbols - tpex_symbols_found)
        if twse_symbols:
            twse_rows, twse_date = fetch_twse_realtime(session, twse_symbols)

            if twse_date and twse_date == today:
                all_rows.extend(twse_rows)
                print(f"TWSE: {len(twse_rows)} 支命中")
            else:
                print(f"TWSE: 日期不匹配 (API={twse_date}, today={today})，跳過")

        # 3. Upsert to DB
        if all_rows:
            count = upsert_prices(database_url, today, all_rows)
            elapsed = time.monotonic() - t0
            print(f"完成: {count} 支股票價格已更新 ({elapsed:.1f}s)")
        else:
            print("無資料可更新")

    finally:
        close_pool()
