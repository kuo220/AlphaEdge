---
description: 在 AlphaEdge 專案中開發／撰寫／新增交易策略時使用。當使用者提到「開發策略」、「寫一個策略」、「新增策略」、「策略邏輯」、「策略回測」，或要在 core/strategies/stock/ 底下新增/修改繼承 BaseStockStrategy 的策略類別時觸發，不需要使用者明講「去讀 README」。
when_to_use: 使用者想要新增一支新策略、修改既有策略的開倉/平倉/停損邏輯、詢問策略要怎麼寫、詢問策略參數/資料 API 怎麼用、或要用 run.py --strategy 執行回測時。
---

# AlphaEdge 策略開發（SDD）

`core/strategies/README.md` 是本專案策略開發的**唯一權威文件**，完整定義了 SDD（策略開發文件）流程：目錄結構、`BaseStockStrategy` 的六個必實作方法（`setup_account`、`setup_apis`、`check_open_signal`、`check_close_signal`、`check_stop_loss_signal`、`calculate_position_size`）、策略參數表、資料 API（`StockPriceAPI`/`StockTickAPI`/`StockChipAPI`/`MonthlyRevenueReportAPI`/`FinancialStatementAPI`）用法、自動載入規則與回測執行方式。

## 執行步驟

1. **一律先完整讀取 `core/strategies/README.md`**（不要只憑記憶或猜測），再開始撰寫或修改策略程式碼。
2. 新策略檔案放在 `core/strategies/stock/`，繼承 `BaseStockStrategy`，類別名稱即為 `python run.py --strategy <ClassName>` 使用的識別名稱。
3. 依 README 的方法簽章與範例實作全部必要方法；不要自創介面或跳過任一必實作方法。
4. 若使用者的需求涉及尚未在 README 涵蓋的資料源或功能（例如期貨），先確認是否該複用既有台股 API/管理器慣例，或需要參考 `backlog/` 下的其他架構規劃文件（如台期貨相關規劃）。
5. 完成後提醒使用者可用 `python run.py --strategy <ClassName>` 執行回測，結果會落在 `core/backtest/results/<ClassName>/`。

不要向使用者要求先手動貼上 README 內容——這份文件的讀取是本 skill 的第一步，自動完成。
