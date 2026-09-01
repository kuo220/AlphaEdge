"""
報價轉換器：把各市場資料 API 的查詢結果轉成回測吃的 `BaseQuote`

實作依市場分在子目錄（`tw/`），此處保留舊的匯入路徑不變——
`from core.adapters import StockQuoteAdapter` 仍可用。
"""

from .tw.futures_quote_adapter import FuturesQuoteAdapter
from .tw.stock_quote_adapter import StockQuoteAdapter

__all__ = ["FuturesQuoteAdapter", "StockQuoteAdapter"]
