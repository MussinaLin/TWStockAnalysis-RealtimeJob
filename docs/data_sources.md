# Data Sources

本專案使用的外部資料來源與對應的 fetch function。

## yfinance（盤中報價）

- **用途**：realtime job 主要資料源，一次抓取所有啟用股票的當日 OHLCV
- **Function**：`fetch_prices()` — `src/realtime_job/sources.py`
- **呼叫方式**：`yf.download(symbols, period="1d", interval="1d", auto_adjust=False, multi_level_index=True)`
- **Symbol 對應**：依 `stocks.market_type` 加後綴 — `twse` → `2330.TW`、`tpex` → `8299.TWO`；缺 `market_type` 的股票直接跳過

### 行為注意事項

- **多檔下載的 index 是各檔日期的聯集**：停牌或當日無成交的個股，其最後一根日 K 會停在舊日期，導致回傳的 DataFrame 多出舊日期列。`fetch_prices()` 一律取 **`index.max()`（最新日期）那一列**作為資料來源與 `data_date`；在最新列無資料的個股為 NaN，由 OHLC 完整性檢查跳過該檔，不影響其他股票。
- **OHLC 任一缺值（None / NaN）即跳過該檔**，避免 NULL 寫入 `stock_daily_raw`。

## TPEX OpenAPI（market_type 回填）

- **用途**：一次性回填腳本，判斷股票屬於上市（twse）或上櫃（tpex）
- **Script**：`scripts/backfill_market_type.py`
- **Endpoint**：`https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes`
- **邏輯**：取得全部上櫃股票代碼清單，在清單內 → `tpex`，否則 → `twse`
