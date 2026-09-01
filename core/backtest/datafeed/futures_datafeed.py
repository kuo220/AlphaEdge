import datetime
import sqlite3
from typing import Dict, List, Optional

from loguru import logger

from core.adapters.futures_quote_adapter import FuturesQuoteAdapter
from core.api.futures_margin_api import FuturesMarginAPI
from core.api.futures_price_api import FuturesPriceAPI
from core.backtest.datafeed.base import BaseDataFeed
from core.backtest.datafeed.futures_calendar import FuturesCalendar
from core.config import TW_FUTURES_DB_PATH
from core.managers.futures.position_manager import FuturesMarginConfig
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

    # 日曆往回測結束日之後多取的曆日數：末段契約的最後交易日可能落在區間外
    CALENDAR_LOOKAHEAD_DAYS: int = 45

    def __init__(self, margin_config: Optional[FuturesMarginConfig] = None):
        # 單次回測共用一條 SQLite 連線：行情與保證金查的是同一個 DB 檔
        self.conn: Optional[sqlite3.Connection] = None

        # 本次回測的保證金設定；`setup()` 會把建好的 API 注入其中，
        # 讓策略層與部位管理層**共用同一個查表來源**（見 `inject_margin_api()`）
        self.margin_config: Optional[FuturesMarginConfig] = margin_config

        self.futures_price: Optional[FuturesPriceAPI] = None  # 期貨日行情
        self.margin: Optional[FuturesMarginAPI] = None  # 保證金歷史

        # 本次回測的商品與時段（由策略宣告）
        self.products: List[str] = []
        self.session: FuturesSession = FuturesSession.DAY

        # 回測區間與期貨交易日曆（整場只建一次）
        self.start_date: Optional[datetime.date] = None
        self.end_date: Optional[datetime.date] = None
        self.calendar: Optional[FuturesCalendar] = None

    def setup(self, strategy: BaseStrategy) -> None:
        """建立資料 API 並記下策略宣告的商品與時段"""

        self.conn = sqlite3.connect(TW_FUTURES_DB_PATH)

        self.futures_price = FuturesPriceAPI(conn=self.conn)
        self.margin = FuturesMarginAPI(conn=self.conn)

        self.products = list(getattr(strategy, "products", []) or [])
        self.session = getattr(strategy, "session", FuturesSession.DAY)
        self.start_date = strategy.start_date
        self.end_date = strategy.end_date

        self.calendar = self.build_calendar()
        self.inject_margin_api()

        if not self.products:
            logger.warning(
                "[Futures DataFeed] 策略未宣告 products，將載入當日所有商品的報價"
            )

    def inject_margin_api(self) -> None:
        """
        - Description:
            把本 feed 建立的 `FuturesMarginAPI` 注入保證金設定

            **保證金設定是策略層與部位管理層共用的同一個物件**（由 factory 建立
            並回寫給策略），故只要在此注入一次，兩邊算出來的每口保證金就一定一致。
            兩處不一致的後果是「策略算得出口數、部位管理層卻開不進去」，
            而且不會有任何錯誤訊息。

            `use_api=False`（比率近似）時不注入——那是使用者明確表態要降級，
            此時發出警告，避免有人以為自己在跑查表模式。
        """

        if self.margin_config is None:
            return

        if not self.margin_config.use_api:
            logger.warning(
                f"[Futures DataFeed] 保證金採比率近似"
                f"（契約價值 × {self.margin_config.initial_margin_ratio:.0%}），"
                f"跨年份誤差實測 +143% ~ −38%，僅適合跑通流程"
            )
            return

        if self.margin_config.api is None:
            self.margin_config.api = self.margin

        self.check_margin_coverage()

    def check_margin_coverage(self) -> None:
        """
        - Description:
            回測起始日早於保證金資料涵蓋範圍時**在開跑前就講清楚**

            查表模式查不到保證金會直接 raise（那是刻意的，見 `FuturesMarginConfig`），
            但那會發生在迴圈跑到第一筆開倉訊號的時候——使用者看到的是跑了一半
            才中斷。保證金資料只回溯到 2020-03（更早的公告附件是掃描影像，
            見 `backlog/台期貨保證金ETL.md` S6），本檢查在 `setup()` 就把
            「這段期間查不到」說明白，並指出可用的替代做法。
        """

        if self.margin_config is None or self.start_date is None:
            return

        for product in self.products:
            covered: Optional[Dict[str, str]] = (
                self.margin_config.api.get_covered_date_range(product)
            )
            if covered is None:
                logger.warning(
                    f"[Futures DataFeed] {product} 在保證金表內沒有任何資料，"
                    f"開倉時會中止。改用 `FuturesMarginConfig.ratio()` 可跑通流程"
                )
                continue

            if str(self.start_date) < covered["earliest"]:
                logger.warning(
                    f"[Futures DataFeed] 回測起始日 {self.start_date} 早於 {product} "
                    f"的保證金涵蓋範圍（{covered['earliest']} 起），該段一開倉就會中止。"
                    f"要回測更早的期間請明確改用 `FuturesMarginConfig.ratio()`"
                    f"（比率近似，誤差見 backlog/台期貨保證金ETL.md S5）"
                )

    def is_market_open(self, date: datetime.date) -> bool:
        """
        期貨開盤日判定：交給 `FuturesCalendar`（判準是「當日表內有行情」）

        **不沿用股票 calendar**：期貨的休市日與現貨不完全相同，且最後交易日
        遇休市要順延到**期貨自己**的下一個開盤日。日曆整場只建一次
        （回測期間資料表不會變動）。
        """

        if self.futures_price is None:
            return False

        if self.calendar is None:
            self.calendar = self.build_calendar()

        return self.calendar.is_trading_day(date)

    def build_calendar(self) -> FuturesCalendar:
        """
        - Description:
            建立本次回測的期貨交易日曆

            **以策略宣告的第一個商品為準**：不同商品的掛牌期間不同，用「任一商品
            有資料」會把該策略根本不交易的商品的交易日也算進來。

            **結束日往後多取 `CALENDAR_LOOKAHEAD_DAYS` 天**：落在回測末段的契約，
            其最後交易日可能在 `end_date` 之後，只取回測區間本身會讓
            `get_last_trading_date()` 因為「日曆涵蓋不到」而失準（換月規則會用到）。
        - Return:
            - FuturesCalendar
        """

        if self.start_date is None or self.end_date is None:
            return FuturesCalendar()

        product: Optional[str] = self.products[0] if self.products else None
        return FuturesCalendar.from_api(
            self.futures_price,
            self.start_date,
            self.end_date + datetime.timedelta(days=self.CALENDAR_LOOKAHEAD_DAYS),
            product=product,
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
