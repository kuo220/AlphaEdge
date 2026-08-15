import datetime
import sqlite3
from typing import Dict, List, Optional

from core.adapters import StockQuoteAdapter
from core.api.financial_statement_api import FinancialStatementAPI
from core.api.monthly_revenue_report_api import MonthlyRevenueReportAPI
from core.api.stock_chip_api import StockChipAPI
from core.api.stock_dividend_api import StockDividendAPI
from core.api.stock_price_api import StockPriceAPI
from core.api.stock_tick_api import StockTickAPI
from core.backtest.datafeed.base import BaseDataFeed
from core.config import DB_PATH
from core.models import StockQuote
from core.strategies.base import BaseStrategy
from core.utils import Scale
from core.backtest.datafeed.market_calendar import MarketCalendar

"""TwStockDataFeed: 台股資料源（五個資料 API ＋ 報價轉換 ＋ 交易日判定）"""


class TwStockDataFeed(BaseDataFeed):
    """台股資料源：SQLite 的日 K 與籌碼、DolphinDB 的 Tick"""

    def __init__(self):
        # 單次回測共用一條 SQLite 連線：四個 API 查的是同一個 DB 檔，
        # 各開一條沒有任何好處，只會讓連線數隨 API 數量線性成長
        self.conn: Optional[sqlite3.Connection] = None

        self.tick: Optional[StockTickAPI] = None  # Ticks data
        self.chip: Optional[StockChipAPI] = None  # Chips data
        self.price: Optional[StockPriceAPI] = None  # Price data
        self.dividend: Optional[StockDividendAPI] = None  # Ex-rights/dividend data
        self.mrr: Optional[MonthlyRevenueReportAPI] = (
            None  # Monthly Revenue Report data
        )
        self.fs: Optional[FinancialStatementAPI] = None  # Financial Statement data

    def setup(self, strategy: BaseStrategy) -> None:
        """從資料庫載入資料；Tick 級別才建立 DolphinDB 連線"""

        self.conn = sqlite3.connect(DB_PATH)

        self.chip = StockChipAPI(conn=self.conn)
        self.mrr = MonthlyRevenueReportAPI(conn=self.conn)
        self.fs = FinancialStatementAPI(conn=self.conn)
        self.dividend = StockDividendAPI(conn=self.conn)
        self.price = StockPriceAPI(conn=self.conn, dividend_api=self.dividend)

        if strategy.scale == Scale.TICK:
            self.tick = StockTickAPI()

    def is_market_open(self, date: datetime.date) -> bool:
        """台股開盤日判定：當日有日 K 資料即視為開盤"""

        return MarketCalendar.check_stock_market_open(api=self.price, date=date)

    def get_quotes(
        self,
        date: datetime.date,
        scale: Scale,
        adjusted: bool = False,
    ) -> List[StockQuote]:
        """
        依級別取得當日報價

        tick 不做還原：tick 為當日盤中資料，跨日還原無意義
        （見 `backlog/股價還原與除權息調整.md` 範圍界線）
        """

        if scale == Scale.TICK:
            return StockQuoteAdapter.convert_to_tick_quotes(self.tick, date)

        return StockQuoteAdapter.convert_to_day_quotes(self.price, date, adjusted)

    def get_price_limit_basis(self, date: datetime.date) -> Dict[str, float]:
        """
        除權息日的漲跌停基準：交易所另行公告的開盤競價基準

        非除權息日回傳空 dict，`FillModel` 維持沿用前一交易日收盤。
        `setup()` 未執行時（純記憶體測試會跳過）同樣回傳空 dict，
        此時本來就沒有資料源可查，不是「查不到資料」
        """

        if self.dividend is None:
            return {}

        return self.dividend.get_opening_reference_price_map(date)

    def close(self) -> None:
        """關閉所有資料連線（回測結束時呼叫；原本全專案的 conn 從不 close）"""

        for api in (self.chip, self.mrr, self.fs, self.price, self.dividend, self.tick):
            if api is not None:
                api.close()

        if self.conn is not None:
            self.conn.close()
            self.conn = None
