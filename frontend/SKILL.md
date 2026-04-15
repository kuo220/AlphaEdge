---
name: frontend
description: >-
  Builds and maintains the AlphaEdge Streamlit viewer under frontend/ for
  read-only backtest reports (CSV, PNG, logs) from trader/backtest/results.
  Use when the user mentions frontend, Streamlit, backtest dashboard, report
  viewer, or UI for backtest results.
---

# AlphaEdge Streamlit 回測前端（frontend）

## 目標

在專案根目錄的 `frontend/` 以 **Streamlit** 提供唯讀介面：選擇策略結果資料夾，呈現 `trading_report.csv`、標準圖檔與可選 log。不修改 `trader/` 核心回測邏輯。

## 資料來源（固定對齊文件）

- 結果根目錄預設：`trader/backtest/results/<StrategyName>/`（與 `README.md` / `README_zh.md` 一致）。
- 常見產物檔名（若不存在則 UI 顯示提示，勿崩潰）：
  - `trading_report.csv`
  - `balance_curve.png`
  - `balance_and_benchmark_curve.png`
  - `balance_mdd.png`
  - `everyday_profit.png`
- CSV 編碼可能為 UTF-8-SIG（與 `FileEncoding.UTF8_SIG` 產出對齊）；讀取時需處理編碼。
- 可透過環境變數覆寫結果根路徑（例如 `ALPHAEDGE_BACKTEST_RESULTS`），預設為專案內相對路徑。

## 建議目錄結構

```
frontend/
├── README.md              # 安裝、streamlit run、環境變數
├── requirements.txt       # streamlit、pandas 等（與 docs/requirements.txt 分離或註明合併方式）
├── .streamlit/config.toml # 可選
├── app.py                 # 入口：set_page_config、側欄選 run、Tabs
├── config.py              # 結果根路徑、預期檔名常數
├── services/report_loader.py
└── components/            # kpi / tables / charts 等可重用區塊
```

## 實作原則

1. **唯讀**：預設不寫入 `trader/backtest/results`。
2. **解耦**：`frontend` 不依賴 `trader` 套件匯入亦可運作；僅讀檔與路徑即可。
3. **版面**：`layout="wide"`；側欄選策略子資料夾；主區用 Tabs：總覽、明細表、圖表、下載（可選）。
4. **圖表**：先以 `st.image` 顯示 PNG；日後若要互動圖再評估 Plotly 或呼叫 reporter（另開議題）。
5. **變更範圍**：僅改 `frontend/` 與必要根目錄說明；不順手重構 `trader/`。

## 工作流程檢查

- [ ] 側欄能列出 `trader/backtest/results` 下子資料夾並選取
- [ ] `trading_report.csv` 可顯示（含中文欄位）
- [ ] 各 PNG 存在則顯示，缺檔有提示
- [ ] `frontend/README.md` 含啟動指令與環境變數說明

## 啟動（寫入 README 時用）

從專案根目錄：`streamlit run frontend/app.py`（路徑依實際檔案調整）。
