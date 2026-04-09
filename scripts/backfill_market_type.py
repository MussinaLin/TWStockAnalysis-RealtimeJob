"""One-time script: detect market_type (twse/tpex) for all stocks.

Uses TPEX OpenAPI to get the list of all OTC stocks.
Stocks found in the TPEX list -> 'tpex', otherwise -> 'twse'.
Can be re-run safely — only processes stocks with market_type IS NULL.
"""

from __future__ import annotations

import os
import sys

import requests
import urllib3
from psycopg_pool import ConnectionPool


def main() -> None:
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        print("ERROR: DATABASE_URL 未設定", file=sys.stderr)
        sys.exit(1)

    pool = ConnectionPool(database_url, min_size=1, max_size=3)
    pool.wait()

    with pool.connection() as conn:
        conn.execute("ALTER TABLE stocks ADD COLUMN IF NOT EXISTS market_type VARCHAR(4)")
        conn.commit()

    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT symbol FROM stocks WHERE market_type IS NULL ORDER BY symbol"
        ).fetchall()

    symbols = [r[0] for r in rows]
    if not symbols:
        print("所有股票已有 market_type，無需回填")
        pool.close()
        return

    print(f"需回填 {len(symbols)} 支股票的 market_type")

    # Fetch all TPEX (OTC) stock codes from OpenAPI
    print("從 TPEX OpenAPI 取得上櫃股票清單...")
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    resp = requests.get(
        "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes",
        timeout=30,
        verify=False,
    )
    resp.raise_for_status()
    tpex_symbols = {
        item.get("SecuritiesCompanyCode", "").strip()
        for item in resp.json()
        if item.get("SecuritiesCompanyCode", "").strip()
    }
    print(f"TPEX 股票數: {len(tpex_symbols)}")

    # Classify: in TPEX list -> tpex, otherwise -> twse
    results = {}
    for s in symbols:
        results[s] = "tpex" if s in tpex_symbols else "twse"

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                "UPDATE stocks SET market_type = %s WHERE symbol = %s",
                [(mt, sym) for sym, mt in results.items()],
            )
        conn.commit()

    twse_count = sum(1 for v in results.values() if v == "twse")
    tpex_count = sum(1 for v in results.values() if v == "tpex")
    print(f"完成: twse={twse_count}, tpex={tpex_count}")

    pool.close()


if __name__ == "__main__":
    main()
