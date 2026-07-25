# strategy_lab 目錄規範（Claude Code）

> 本檔案對齊 `.cursor/rules/strategy-lab-layout.mdc`（globs: `strategy_lab/**`, alwaysApply: false）。
> Claude Code 沒有 glob 條件規則機制，改用「目錄專屬 CLAUDE.md」達到同等效果：只有在 `strategy_lab/` 底下讀寫檔案時才會載入本規則。

`strategy_lab/` 是 R&D 工作區。四大分類為**大分類**，每個研究主題用**一個 `snake_case` 子資料夾**區分。

## 分類決策

| 工作性質                       | 放置位置                 |
| ------------------------------ | ------------------------ |
| 未驗證假設、文獻筆記、失敗結論 | `ideas/<topic>/`         |
| EDA、IC、特徵探索、非完整策略  | `data_analysis/<topic>/` |
| 探索性 Jupyter、快速視覺化     | `notebooks/<topic>/`     |
| 完整策略研究、可重現 pipeline  | `strategies/<topic>/`    |

同一主題跨分類時，**資料夾名稱保持一致**（例如 `ideas/momentum_breakout/` 與 `data_analysis/momentum_breakout/`）。

## 硬性規則

- 新檔案必須落在 `<category>/<topic>/` 內，**禁止**在 `strategy_lab/` 頂層直接新增 script / notebook / md。
- 主題資料夾命名：`snake_case`，語意清楚（例：`tech_new_high_continuation`、`tsmc_overnight_signal`）。
- 研究產出（圖表、CSV）放對應主題的 `output/`；Word/PDF 報告放 `reports/`。
- 優先複用 `core/api/` 與 `core/utils/`，不在 lab 內重複實作資料讀取、手續費、交易日邏輯。
- 成熟策略最終搬到 `core/strategies/stock/`，用 `run.py --strategy <Name>` 跑正式回測。

詳細說明、API 用法、工作流 → [`strategy_lab/README.md`](README.md)
