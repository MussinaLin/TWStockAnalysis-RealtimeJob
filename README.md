# TWStockAnalysis-RealtimeJob

盤中即時股票價格更新 Job，輔助 [TWStockAnalysis](../TWStockAnalysis) 專案。

TWStockAnalysis 為 daily job（每天收盤後執行一次），本專案以 cron job 方式每分鐘執行，將盤中即時價格寫入 `stock_daily_raw` table，讓資料在盤中也能保持最新。

## 執行流程

1. 查詢 `config` table 的 `is_trading_date`，非交易日直接結束
2. 查詢 `stocks` table 中 `enabled=TRUE` 的股票清單
3. 從 TPEX OpenAPI 取得所有上櫃股票即時報價（一次全拿）
4. 剩餘上市股票從 TWSE 即時 API 分批取得報價（每批 20 支）
5. 將 open, high, low, current price（寫入 close 欄位）upsert 到 `stock_daily_raw` table
6. 結束

## 資料來源

| 市場 | API | 說明 |
|------|-----|------|
| TPEX 上櫃 | `tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes` | OpenAPI，一次回傳所有上櫃股票 OHLCV |
| TWSE 上市 | `mis.twse.com.tw/stock/api/getStockInfo.jsp` | 即時報價，分批查詢 |

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
