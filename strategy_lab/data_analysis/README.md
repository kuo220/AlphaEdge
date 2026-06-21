# data_analysis — 純資料分析

放「**不是完整策略**、但有助於形成策略想法」的研究腳本。

## 適合放這裡的東西

- 標的之**統計描述**（平均報酬、波動、季節性、極值）
- **特徵探索**：相關性、IC（Information Coefficient）、PCA、聚類
- **市場結構**：流動性、成交量分布、漲跌停頻率
- **跨資產關聯**：股／債／匯率／VIX 之共動性
- **資料品質檢查**：缺值、複權差異、來源比對

## 與 `strategies/` 的差別

| 維度 | `data_analysis/` | `strategies/` |
|------|------------------|---------------|
| 目的 | 「我想了解 / 我想假設」 | 「我要驗證 / 我要回測」 |
| 產出 | 統計表、相關圖、特徵清單 | 績效曲線、Sharpe、回撤、訊號規則 |
| 結構 | 主題子資料夾 + 分析腳本 | 完整資料夾（pipeline + reports + output） |

## 建議結構

每一個分析主題一個 `snake_case` 子資料夾（與 `ideas/`、`notebooks/`、`strategies/` 命名對齊）：

```
data_analysis/
├── README.md
├── __init__.py
└── tech_new_high_continuation/     ← 範例
    ├── run.py                      # 入口腳本
    ├── analysis.py                 # 主要分析邏輯
    └── output/                     # 圖表、CSV
```

- 每份腳本上方寫清楚：**研究問題、資料來源、結論**。
- 結論若驅動了某個策略，請在 commit message / README 中互相連結對應的 `ideas/<topic>/` 或 `strategies/<topic>/`。

執行範例：

```bash
.venv/bin/python strategy_lab/data_analysis/tech_new_high_continuation/run.py
```
