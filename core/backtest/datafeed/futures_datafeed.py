import datetime
import sqlite3
from typing import List, Optional, Set

from loguru import logger

from core.adapters.futures_quote_adapter import FuturesQuoteAdapter
from core.api.futures_margin_api import FuturesMarginAPI
from core.api.futures_price_api import FuturesPriceAPI
from core.backtest.datafeed.base import BaseDataFeed
from core.config import TW_FUTURES_DB_PATH
from core.models import FuturesQuote
from core.strategies.base import BaseStrategy
from core.utils import FuturesSession, Scale

"""TwFuturesDataFeed: 台期貨資料源（tw_futures.db 的日行情與保證金 ＋ 交易日判定）"""


class TwFuturesDataFeed(BaseDataFeed):
    """
    台期貨資料源

    與 `TwStockDataFeed` 的三個結構差異，每一個都直接影響回測正確性：

    1. **一天不只一個報價**：同一天同一商品有多個到期月在交易，本 feed 一律把
       當日**所有契約**轉出（換月是策略的政策，見 `FuturesQuoteAdapter`）。
    2. **必須指定交易時段**：日盤與夜盤是兩筆獨立行情，而同一契約兩個時段的
       `symbol` 完全相同（`{product}{expiry}`）。兩者混在同一根 bar 傳進引擎，
       `quote_map` 會互相覆蓋、訊號也會被算兩次。故本 feed 只取**策略宣告的那一個
       時段**（`strategy.session`），不提供「兩個都拿」的選項。
    3. **沒有還原價**：期貨沒有除權息，`get_quotes()` 的 `adjusted` 參數一律忽略。

    ⚠️ **交易日判準暫以「表內當日有資料」代替**（與 `StockPriceAPI` 同一種作法）。
    真正的期貨交易日曆（結算日、夜盤跨日、與台股不一致的補班日）屬 Phase2-3。
    """

    def __init__(self):
        # 單次回測共用一條 SQLite 連線：行情與保證金查的是同一個 DB 檔
        self.conn: Optional[sqlite3.Connection] = None

        self.futures_price: Optional[FuturesPriceAPI] = None  # 期貨日行情
        self.margin: Optional[FuturesMarginAPI] = None  # 保證金歷史

        # 本次回測的商品與時段（由策略宣告）
        self.products: List[str] = []
        self.session: FuturesSession = FuturesSession.DAY

        # 回測區間與交易日集合（整場只查一次）
        self.start_date: Optional[datetime.date] = None
        self.end_date: Optional[datetime.date] = None
        self.trading_days: Optional[Set[datetime.date]] = None

    def setup(self, strategy: BaseStrategy) -> None:
        """建立資料 API 並記下策略宣告的商品與時段"""

        self.conn = sqlite3.connect(TW_FUTURES_DB_PATH)

        self.futures_price = FuturesPriceAPI(conn=self.conn)
        self.margin = FuturesMarginAPI(conn=self.conn)

        self.products = list(getattr(strategy, "products", []) or [])
        self.session = getattr(strategy, "session", FuturesSession.DAY)
        self.start_date = strategy.start_date
        self.end_date = strategy.end_date

        if not self.products:
            logger.warning(
                "[Futures DataFeed] 策略未宣告 products，將載入當日所有商品的報價"
            )

    def is_market_open(self, date: datetime.date) -> bool:
        """
        期貨開盤日判定：當日表內有資料即視為開盤

        交易日集合整場只建一次（回測期間資料表不會變動）；
        **不過濾時段**——夜盤成交的那一天同樣是交易日。
        """

        if self.futures_price is None:
            return False

        if self.trading_days is None:
            self.trading_days = self.build_trading_days()

        return date in self.trading_days

    def build_trading_days(self) -> Set[datetime.date]:
        """
        由行情表建立回測區間內的交易日集合

        **以策略宣告的第一個商品為準**：不同商品的掛牌期間不同，用「任一商品有
        資料」會把該策略根本不交易的商品的交易日也算進來。未宣告商品時才退回全表。
        """

        if self.start_date is None or self.end_date is None:
            return set()

        product: Optional[str] = self.products[0] if self.products else None
        return set(
            self.futures_price.get_trading_days(
                self.start_date, self.end_date, product=product
            )
        )

    def get_quotes(
        self,
        date: datetime.date,
        scale: Scale,
        adjusted: bool = False,
    ) -> List[FuturesQuote]:
        """
        - Description:
            取得當日**所有契約**的報價（僅策略宣告的商品與時段）

            `adjusted` 一律忽略：期貨沒有除權息還原的概念。
        - Parameters:
            - date: datetime.date
                交易日
            - scale: Scale
                報價級別；**目前僅支援 DAY**，Tick 屬 Phase5-1
            - adjusted: bool
                期貨不適用，僅為對齊介面
        - Return:
            - List[FuturesQuote]
                當日報價；查無資料時為空 list
        """

        if scale == Scale.TICK:
            logger.warning(
                "[Futures DataFeed] 期貨 Tick 級別回測尚未實作（屬 Phase5-1），本日無報價"
            )
            return []

        quotes: List[FuturesQuote] = []
        # products 為空時以 [None] 跑一輪，代表「不過濾商品」
        for product in self.products or [None]:
            quotes.extend(
                FuturesQuoteAdapter.convert_to_day_quotes(
                    self.futures_price,
                    date,
                    product=product,
                    session=self.session,
                )
            )

        return quotes

    def close(self) -> None:
        """關閉資料連線（回測結束時由引擎呼叫）"""

        for api in (self.futures_price, self.margin):
            if api is not None:
                api.close()

        if self.conn is not None:
            self.conn.close()
            self.conn = None
