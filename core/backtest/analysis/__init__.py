"""analysis package: 績效指標與風險調整後報酬"""

# 刻意不在此 eager import StockBacktestAnalyzer（與 `core/backtest/__init__.py`
# 同一個作法）：analyzer 相依 pandas／numpy／loguru 與 `core.api.tw.stock_price_api`，
# 後者再拉進 shioaji 與 sqlite3——實測整條鏈 1,164 個模組、431 ms。
#
# 而 `risk_metrics.py` 是**只相依 math 與 typing 的純函式**，前端要與 reporter
# 共用同一份公式就得 import 它；套件層一 eager import，前端就得把整個後端
# 連同 shioaji 一起裝進映像。呼叫端一律用完整路徑
# `from core.backtest.analysis.analyzer import StockBacktestAnalyzer`
# （現有呼叫端本來就都是這樣寫）。
