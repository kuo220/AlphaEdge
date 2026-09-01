"""
台灣市場的資料 API（股票 ＋ 期貨）

**目錄只承載「市場」一條軸，商品類別由檔名承載**（`stock_price_api.py` vs
`futures_price_api.py`），與 `core/pipeline/tw/` 一致——每層目錄只放一條軸，
`tw_stock/`／`tw_futures/` 會把兩條軸壓成單一目錄名。理由見
`docs/dev/naming-axes.md`。

**刻意不做套件層 eager import**：`core.api.tw.stock_tick_api` 會相依 DolphinDB
（選用相依），在此 re-export 會讓沒裝的環境一 import `core.api.tw` 就壞掉。
呼叫端一律使用完整模組路徑。
"""
