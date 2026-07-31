# Backlog / 待辦與規劃紀錄

本資料夾存放**與產品說明無關**的待辦與規劃紀錄，例如：

- 待實作功能或方案紀錄（先記錄做法，暫不寫程式）
- 優化計畫與實作狀態追蹤（已實作 / 未實作）
- 重構或技術債清單

**說明文件**（API 文檔、使用教學、流程說明等）請放在 `docs/`。

**新增待辦文件的必要結構**（Abstract、步驟拆分、進度追蹤表、狀態標記）見 [`CLAUDE.md` §3 Backlog 管理](../CLAUDE.md#3-backlog-管理)。

**項目完成後的處理方式**:本資料夾只放「尚未實作」的規劃，項目一旦實作完成即**整份移出**——若內容仍有長期參考價值（例如架構說明），改放進 `docs/` 並視需要重寫成正式文件；若只是實作過程的規劃筆記，直接刪除。完成後記得同步移除下方索引表對應那一列。

---

## 項目清單

> 優先級與完成狀態見 [index.md](index.md)（單一索引表，新增／完成項目時務必同步）。

| 檔案 | 說明 |
|------|------|
| [index.md](index.md) | **本資料夾的索引表**：所有待辦事項的優先級與完成狀態 |
| [broker_trading_no_data_handling.md](broker_trading_no_data_handling.md) | 券商分點 No Data 處理 |
| [finmind-pipeline-optimization.md](finmind-pipeline-optimization.md) | FinMind 爬蟲／清洗／儲存流程優化計畫 |
| [LONG成本模型口徑收斂.md](LONG成本模型口徑收斂.md) | `StockPositionManager` 的 LONG 分支收斂至 `StockCostModel`，消除多空兩套費用口徑並存 |
| [PostgreSQL遷移計畫.md](PostgreSQL遷移計畫.md) | AlphaEdge 由 SQLite3 遷移到 PostgreSQL 的分階段實作計畫 |
| [回測引擎當沖執行順序重構.md](回測引擎當沖執行順序重構.md) | 當沖／日內策略之開倉、平倉順序與執行模型政策化（對齊業界 bar policy / event loop） |
| [回測滑價與執行係數.md](回測滑價與執行係數.md) | 不大改 `core` 架構下新增滑價等係數：係數存放、`StockUtils` 調價、`Backtester` 掛點與文件 |
| [回測權益曲線改用逐日權益.md](回測權益曲線改用逐日權益.md) | 報表圖表改吃 `snapshot_daily_equity` 的逐日權益，修正 MDD 被低估 |
| [台股新聞情緒溫度計篩選工具.md](台股新聞情緒溫度計篩選工具.md) | 每日爬取台股財經新聞，萃取個股利多/利空情緒並生成可篩選的溫度計指標 |
| [台期貨ETL與回測架構規劃.md](台期貨ETL與回測架構規劃.md) | 台期貨平行模組擴充：ETL、保證金/換月/日曆、回測與策略分支（不動既有台股） |
| [美股ETL與回測架構規劃.md](美股ETL與回測架構規劃.md) | 美股平行模組擴充：市場分層、provider 抽象、回測核心拆分 |
| [放空回測框架建置.md](放空回測框架建置.md) | 補齊 `StockPositionManager`/`StockUtils` 的 SHORT 開平倉記帳與損益公式，讓回測引擎能真正跑放空策略（通用框架，非單一策略綁定） |
| [放空框架Phase5延伸.md](放空框架Phase5延伸.md) | 放空框架 Phase 5 延伸：融券餘額 ETL／券源檢核、停券日與股利補償、融資槓桿、同標的雙向持倉 |
| [放空策略_外資大賣強勢股當沖.md](放空策略_外資大賣強勢股當沖.md) | 外資大賣+強勢股隔日開盤放空、尾盤回補策略；依賴放空回測框架建置完成後才能實測 |
