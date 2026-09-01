import datetime
from typing import List, Optional

from loguru import logger

from core.backtest.datafeed.base import BaseDataFeed
from core.models import FuturesAccount, FuturesOrder, FuturesQuote
from core.strategies.futures import BaseFuturesStrategy
from core.utils import Action, PositionType, Scale


class MomentumFuturesStrategy(BaseFuturesStrategy):
    """
    台指期動能策略（日線，示範用）

    買進條件（全部滿足）：
    - 標的為 `products` 指定的商品（預設 TX），取**近月**契約
    - 當日收盤相對前一交易日收盤漲幅 ≥ 門檻（預設 1%）
    - 目前無未平倉部位

    賣出條件：
    - 已有部位且「報價日」≥ 開倉日 + 持有天數門檻（預設 1 個曆日）

    停損條件：
    - 未實作（一律不回傳停損單）

    **這支策略的用途是驗證期貨的介面能跑通，不是可用的交易邏輯**——
    門檻是隨手取的，也沒有處理結算日與換月。要當真實策略用之前至少需要：
    Phase2-3 的期貨交易日曆、Phase2-4 的換月規則、Phase2-1 的成本模型。
    """

    DEFAULT_PRODUCTS: List[str] = ["TX"]
    DEFAULT_MAX_LOTS: int = 2
    DEFAULT_BACKTEST_START_DATE: datetime.date = datetime.date(2024, 1, 1)
    DEFAULT_BACKTEST_END_DATE: datetime.date = datetime.date(2024, 12, 31)

    # 買進參數
    MIN_PRICE_CHANGE_PCT_FOR_SIGNAL: float = 1.0  # 相對昨收之最小漲幅（%）
    MIN_HOLDING_DAYS: int = 1  # 最少持有曆日數
    # 取前一交易日收盤時往回看幾個曆日；連假最長 9 天，取 15 留餘裕
    LOOKBACK_DAYS: int = 15

    def __init__(self):
        super().__init__()
        self.strategy_name: str = "Momentum-Futures"
        self.init_capital: float = 3000000.0
        self.products: List[str] = self.DEFAULT_PRODUCTS
        self.max_lots: int = self.DEFAULT_MAX_LOTS
        self.position_type: PositionType = PositionType.LONG
        self.scale: Scale = Scale.DAY

        self.start_date: datetime.date = self.DEFAULT_BACKTEST_START_DATE
        self.end_date: datetime.date = self.DEFAULT_BACKTEST_END_DATE

    def setup_account(self, account: FuturesAccount) -> None:
        """設置虛擬帳戶資訊"""

        self.account: FuturesAccount = account

    def setup_apis(self, feed: BaseDataFeed) -> None:
        """宣告本策略要用的資料源；實例由 DataFeed 統一持有"""

        self.futures_price = feed.futures_price
        self.margin = getattr(feed, "margin", None)
        self.calendar = getattr(feed, "calendar", None)

    def check_open_signal(self, quotes: List[FuturesQuote]) -> List[FuturesOrder]:
        """開倉：近月契約相對昨收漲幅達門檻且目前無部位"""

        if self.max_lots == 0 or not quotes:
            return []

        # 日盤與夜盤是兩筆獨立行情，先過濾再挑契約
        day_quotes: List[FuturesQuote] = self.filter_session(quotes)

        candidates: List[FuturesQuote] = []
        for product in self.products:
            quote: Optional[FuturesQuote] = self.select_near_month(day_quotes, product)
            if quote is None:
                continue
            # 已有該商品的部位就不再開（本策略不加碼）
            if any(
                code.startswith(product) and lots != 0
                for code, lots in self.get_open_lots().items()
            ):
                continue
            if self.is_momentum(quote):
                candidates.append(quote)

        return self.calculate_position_size(candidates, Action.OPEN)

    def is_momentum(self, quote: FuturesQuote) -> bool:
        """當日收盤相對前一交易日收盤的漲幅是否達門檻"""

        if self.futures_price is None:
            return False

        date: datetime.date = self.normalize_quote_date(quote.date)
        # 取該契約在本日之前最近一個交易日的收盤
        series = self.futures_price.get_close_series(
            product=quote.product,
            expiry=quote.expiry,
            start_date=date - datetime.timedelta(days=self.LOOKBACK_DAYS),
            end_date=date,
            session=self.session,
        )
        if len(series) < 2:
            return False

        previous_close: float = float(series.iloc[-2])
        if previous_close <= 0:
            return False

        change_pct: float = (quote.close / previous_close - 1) * 100
        return change_pct >= self.MIN_PRICE_CHANGE_PCT_FOR_SIGNAL

    def check_close_signal(self, quotes: List[FuturesQuote]) -> List[FuturesOrder]:
        """平倉：持有滿門檻天數即出場"""

        if self.account is None:
            return []

        day_quotes: List[FuturesQuote] = self.filter_session(quotes)
        quote_by_contract = {quote.contract_id: quote for quote in day_quotes}

        orders: List[FuturesOrder] = []
        for position in self.account.get_positions():
            quote: Optional[FuturesQuote] = quote_by_contract.get(position.contract_id)
            if quote is None:
                continue

            holding_days: int = (
                self.normalize_quote_date(quote.date)
                - self.normalize_quote_date(position.date)
            ).days
            if holding_days < self.MIN_HOLDING_DAYS:
                continue

            orders.append(
                self.build_order(
                    quote,
                    action=Action.SELL
                    if position.position_type == PositionType.LONG
                    else Action.BUY,
                    volume=position.volume,
                )
            )

        return orders

    def check_stop_loss_signal(self, quotes: List[FuturesQuote]) -> List[FuturesOrder]:
        """停損：本策略未實作"""

        return []

    def calculate_position_size(
        self, quotes: List[FuturesQuote], action: Action
    ) -> List[FuturesOrder]:
        """
        依保證金與口數上限計算下單口數

        **可開口數由保證金決定不是契約價值**（見 `calculate_max_lots()`）；
        再與 `max_lots` 取小值。
        """

        if not quotes or self.account is None:
            return []

        orders: List[FuturesOrder] = []
        remaining_lots: int = self.max_lots - sum(
            abs(lots) for lots in self.get_open_lots().values()
        )

        for quote in quotes:
            if remaining_lots <= 0:
                break

            affordable: int = self.calculate_max_lots(quote)
            volume: int = min(affordable, remaining_lots)
            if volume <= 0:
                logger.info(
                    f"[{self.strategy_name}] {quote.contract_id} 保證金不足或已達口數上限，跳過"
                )
                continue

            orders.append(
                self.build_order(
                    quote,
                    action=Action.BUY
                    if self.position_type == PositionType.LONG
                    else Action.SELL,
                    volume=volume,
                )
            )
            remaining_lots -= volume

        return orders
