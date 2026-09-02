"""
台灣市場的資料源與市場結構（交易日曆、換月規則）

目錄只承載「市場」一條軸，商品類別由檔名承載（見 `docs/dev/naming-axes.md`）。

**刻意不做套件層 eager import**：這些模組相依 `core.api` 與 `core.adapters`，
在此 re-export 會觸發循環 import（與 `core/backtest/datafeed/__init__.py`
同一個理由）。呼叫端一律使用完整模組路徑。
"""
