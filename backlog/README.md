# Backlog / 待辦與規劃紀錄

本資料夾存放**與產品說明無關**的待辦與規劃紀錄，例如：

- 待實作功能或方案紀錄（先記錄做法，暫不寫程式）
- 優化計畫與實作狀態追蹤（已實作 / 未實作）
- 重構或技術債清單

**說明文件**（API 文檔、使用教學、流程說明等）請放在 `docs/`。

---

## 項目清單

| 檔案 | 說明 |
|------|------|
| [broker_trading_index_and_lock_fix.md](broker_trading_index_and_lock_fix.md) | 券商分點表索引 (securities_trader_id, stock_id, date) 與 metadata 更新前 commit 避免 SQLite 鎖競爭 |
| [broker_trading_no_data_handling.md](broker_trading_no_data_handling.md) | 券商分點 No Data 處理 |
| [finmind-pipeline-optimization.md](finmind-pipeline-optimization.md) | FinMind 爬蟲／清洗／儲存流程優化計畫 |
