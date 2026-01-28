# AlphaEdge API 文檔

歡迎使用 AlphaEdge 交易框架 API 文檔！

## 關於 AlphaEdge

**AlphaEdge** 是一個專為回測交易策略、生成回測報告以及透過 [Shioaji API](https://sinotrade.github.io/zh_TW/) 進行實盤交易而設計的交易框架。它支援**股票、期貨和選擇權**的回測和交易（目前僅實作了股票交易）。

## 文檔結構

### 📚 API 參考

- **[資料 API](api/overview.md)**: 查詢各種市場資料的 API
  - `StockPriceAPI`: 日線價格資料
  - `StockTickAPI`: 逐筆成交資料
  - `StockChipAPI`: 三大法人籌碼資料
  - `MonthlyRevenueReportAPI`: 月營收資料
  - `FinancialStatementAPI`: 財報資料

- **[策略 API](api/strategy/base_stock_strategy.md)**: 開發交易策略的基礎類別
  - `BaseStockStrategy`: 股票策略基礎類別

### 🚀 快速開始

如果您是第一次使用 AlphaEdge，建議從以下內容開始：

1. [快速開始指南](getting-started.md) - 了解如何安裝和基本使用
2. [基本使用範例](examples/basic.md) - 查看簡單的使用範例
3. [策略開發指南](examples/strategy.md) - 學習如何開發自己的策略

### 📖 使用範例

我們提供了豐富的使用範例，幫助您快速上手：

- [基本使用](examples/basic.md) - 基本的 API 使用方式
- [策略開發](examples/strategy.md) - 如何開發和測試策略
- [資料查詢](examples/data_query.md) - 各種資料查詢的範例

### 💡 最佳實踐

查看我們的[最佳實踐指南](best-practices.md)，了解如何更有效地使用 AlphaEdge。

### ❓ 常見問題

遇到問題了嗎？查看[常見問題](faq.md)頁面，或參考 [README](../README.md) 獲取更多資訊。

### 📊 資料更新

了解資料更新流程和狀態：
- [券商分點統計更新流程](broker_trading_update_flow.md) - 詳細的 FinMind 券商分點統計更新流程說明
- [資料庫更新](../README.md#資料庫更新) - 所有資料類型的更新說明

## 相關資源

- [專案 README](../README.md)
- [架構分析報告](../ARCHITECTURE_REVIEW.md)
- [策略開發指南](../trader/strategies/README.md)

## 貢獻

歡迎提交 Issue 或 Pull Request 來改進文檔！
