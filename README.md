# TWStockAnalysis-RealtimeJob

盤中即時股票價格更新 Job，輔助 [TWStockAnalysis](../TWStockAnalysis) 專案。

TWStockAnalysis 為 daily job（每天收盤後執行一次），本專案以 cron job 方式每分鐘執行，將盤中即時價格寫入 `stock_daily_raw` table，讓資料在盤中也能保持最新。

## 執行流程

1. 查詢 `config` table 的 `is_trading_date`，非交易日直接結束
2. 查詢 `stocks` table 中 `enabled=TRUE` 且有 `market_type` 的股票清單
3. 透過 yfinance 一次取得所有股票的 OHLCV（上市 `.TW`、上櫃 `.TWO`）
4. 將 open, high, low, current price（寫入 close 欄位）upsert 到 `stock_daily_raw` table
5. 結束

## 資料來源

| 來源 | 說明 |
|------|------|
| [yfinance](https://pypi.org/project/yfinance/) | Yahoo Finance API wrapper，支援台股上市 (`.TW`) 及上櫃 (`.TWO`) |

## DB 異動

### 新增 `config` table

程式首次執行時自動建立：

```sql
CREATE TABLE IF NOT EXISTS config (
    key          VARCHAR(50)  PRIMARY KEY,
    value        TEXT         NOT NULL,
    created_time TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_time TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
```

預設 `is_trading_date = 'true'`，非交易日需手動（或透過其他機制）設為 `'false'`。

### 新增 `stocks.market_type` 欄位

程式首次執行時自動加欄位：

```sql
ALTER TABLE stocks ADD COLUMN IF NOT EXISTS market_type VARCHAR(4);
-- 值為 'twse'（上市）或 'tpex'（上櫃）
```

首次部署後需執行一次性回填腳本：

```bash
DATABASE_URL=postgresql://... python scripts/backfill_market_type.py
```

此腳本透過 yfinance 自動偵測每支股票屬於上市或上櫃，並寫入 `market_type`。

### 寫入 `stock_daily_raw` table

使用 `ON CONFLICT DO UPDATE` upsert，只更新以下欄位：
- `name`, `open`, `high`, `low`, `close`

不會覆蓋 daily job 寫入的法人買賣超、融資融券等欄位。

## 環境變數

| 變數 | 必填 | 說明 |
|------|------|------|
| `DATABASE_URL` | 是 | PostgreSQL 連線字串 |

## 本地執行

```bash
pip install -e .
DATABASE_URL=postgresql://... python -m realtime_job
```

## Railway 部署

1. 連結此 repo 到 Railway
2. 設定環境變數 `DATABASE_URL`
3. 設定 Cron Schedule: `* * * * *`（每分鐘執行）
4. Railway 會自動使用 Dockerfile 建置
