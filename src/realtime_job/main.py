"""Main entry point for realtime stock price updater."""

from __future__ import annotations

import datetime as dt
import logging
import os
import sys
import time

from .db import close_pool, get_enabled_stocks, init_schema, is_trading_date, upsert_prices
from .sources import fetch_prices

logger = logging.getLogger("realtime_job")


def main() -> None:
    from dotenv import load_dotenv

    load_dotenv()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        logger.error("DATABASE_URL 未設定")
        sys.exit(1)

    t0 = time.monotonic()
    logger.info("開始執行 realtime job")

    try:
        logger.info("初始化 schema...")
        init_schema(database_url)
        logger.info("schema 初始化完成 (%.1fs)", time.monotonic() - t0)

        if not is_trading_date(database_url):
            logger.info("非交易日，跳過")
            return

        logger.info("查詢啟用的股票清單...")
        enabled = get_enabled_stocks(database_url)
        if not enabled:
            logger.info("無啟用的股票")
            return
        logger.info("共 %d 支啟用的股票", len(enabled))

        # Filter out stocks without market_type
        stocks_with_market = [(s, n, m) for s, n, m in enabled if m]
        skipped = len(enabled) - len(stocks_with_market)
        if skipped:
            logger.warning("%d 支股票缺少 market_type，已跳過", skipped)

        if not stocks_with_market:
            logger.info("無可查詢的股票（皆缺少 market_type）")
            return

        logger.info("開始從 yfinance 抓取 %d 支股票報價...", len(stocks_with_market))

        today = dt.date.today()
        t1 = time.monotonic()
        rows, data_date = fetch_prices(stocks_with_market)
        logger.info("yfinance 抓取完成: %d 筆資料 (%.1fs)", len(rows), time.monotonic() - t1)

        if data_date and data_date != today:
            logger.warning("日期不匹配 (yfinance=%s, today=%s)，跳過", data_date, today)
            return

        if rows:
            logger.info("寫入資料庫...")
            t2 = time.monotonic()
            count = upsert_prices(database_url, today, rows)
            logger.info("資料庫寫入完成: %d 筆 (%.1fs)", count, time.monotonic() - t2)
            elapsed = time.monotonic() - t0
            logger.info("全部完成: %d 支股票價格已更新，總耗時 %.1fs", count, elapsed)
        else:
            logger.info("無資料可更新")

    finally:
        close_pool()
