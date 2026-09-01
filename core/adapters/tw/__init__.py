"""
台灣市場的報價轉換器（股票 ＋ 期貨）

目錄只承載「市場」一條軸，商品類別由檔名承載（見 `docs/dev/naming-axes.md`）。
"""

from .futures_quote_adapter import FuturesQuoteAdapter
from .stock_quote_adapter import StockQuoteAdapter

__all__ = ["FuturesQuoteAdapter", "StockQuoteAdapter"]
