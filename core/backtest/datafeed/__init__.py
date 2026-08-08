"""datafeed package: 資料載入、報價轉換與交易日判定

**刻意不做套件層 eager import**：`tw_stock_datafeed` 會相依 `core.adapters`
與 `core.api`，一旦在此 re-export，任何被 `core.api` 相依的模組（例如
`core.utils.instrument` 取用 `market_calendar`）都會觸發循環 import。
與 `core/backtest/__init__.py`、`core/strategies/__init__.py` 同一慣例，
呼叫端一律使用完整模組路徑（見 docs/backtest/multi-market-engine.md §6.4）。
"""
