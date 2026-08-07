import datetime
from typing import List, Optional

from core.adapters import StockQuoteAdapter
from core.api.financial_statement_api import FinancialStatementAPI
from core.api.monthly_revenue_report_api import MonthlyRevenueReportAPI
from core.api.stock_chip_api import StockChipAPI
from core.api.stock_price_api import StockPriceAPI
from core.api.stock_tick_api import StockTickAPI
from core.backtest.datafeed.base import BaseDataFeed
from core.models import StockQuote
from core.strategies.base import BaseStrategy
from core.utils import Scale
from core.utils.market_calendar import MarketCalendar

"""TwStockDataFeed: 台股資料源（五個資料 API ＋ 報價轉換 ＋ 交易日判定）"""


class TwStockDataFeed(BaseDataFeed):
    """台股資料源：SQLite 的日 K 與籌碼、DolphinDB 的 Tick"""

    def __init__(self):
        self.tick: Optional[StockTickAPI] = None  # Ticks data
        self.chip: Optional[StockChipAPI] = None  # Chips data
        self.price: Optional[StockPriceAPI] = None  # Price data
        self.mrr: Optional[MonthlyRevenueReportAPI] = (
            None  # Monthly Revenue Report data
        )
        self.fs: Optional[FinancialStatementAPI] = None  # Financial Statement data

    def setup(self, strategy: BaseStrategy) -> None:
        """從資料庫載入資料；Tick 級別才建立 DolphinDB 連線"""

        self.chip = StockChipAPI()
        self.mrr = MonthlyRevenueReportAPI()
        self.fs = FinancialStatementAPI()
        self.price = StockPriceAPI()

        if strategy.scale == Scale.TICK:
            self.tick = StockTickAPI()

    def is_market_open(self, date: datetime.date) -> bool:
        """台股開盤日判定：當日有日 K 資料即視為開盤"""

        return MarketCalendar.check_stock_market_open(api=self.price, date=date)

    def get_quotes(self, date: datetime.date, scale: Scale) -> List[StockQuote]:
        """依級別取得當日報價"""

        if scale == Scale.TICK:
            return StockQuoteAdapter.convert_to_tick_quotes(self.tick, date)

        return StockQuoteAdapter.convert_to_day_quotes(self.price, date)
