# Python standard library
import datetime
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from core.backtest.datafeed.base import BaseDataFeed
from core.models import StockAccount, StockOrder, StockPosition, StockQuote
from core.strategies.stock import BaseStockStrategy
from core.utils import Action, PositionType, Scale
from core.backtest.datafeed.market_calendar import MarketCalendar


class MomentumStrategy4(BaseStockStrategy):
    """
    動能策略 4（日線）

    篩選（在 T 日開盤前即可用前兩交易日收盤與量能判定）：
    - T−1 收盤相對 T−2 收盤漲幅 ≥ 門檻（預設 9%）
    - T−1 全日成交量 ≥ 門檻（預設 5000 張）

    買進：
    - T 日以開盤價（open）做多

    賣出：
    - 持有至「開倉日的下一個交易日」，以當日開盤價（open）全數賣出
    """

    DEFAULT_MAX_HOLDINGS: int = 10
    DEFAULT_BACKTEST_START_DATE: datetime.date = datetime.date(2020, 5, 1)
    DEFAULT_BACKTEST_END_DATE: datetime.date = datetime.date(2025, 5, 31)

    MIN_PRICE_CHANGE_PCT_FOR_SIGNAL: float = 9.0  # T−1 收盤相對 T−2 收盤之最小漲幅（%）
    MIN_VOLUME_LOTS: int = 5000  # T−1 日最小成交量（張）

    def __init__(self):
        super().__init__()
        self.strategy_name: str = "Momentum-4"
        self.init_capital: float = 1000000.0
        self.max_holdings: int = self.DEFAULT_MAX_HOLDINGS
        self.scale: Scale = Scale.DAY

        self.start_date: datetime.date = self.DEFAULT_BACKTEST_START_DATE
        self.end_date: datetime.date = self.DEFAULT_BACKTEST_END_DATE


    def setup_account(self, account: StockAccount) -> None:
        """設置虛擬帳戶資訊"""

        self.account: StockAccount = account

    def setup_apis(self, feed: BaseDataFeed) -> None:
        """宣告本策略要用的資料源；實例由 DataFeed 統一持有"""

        self.chip = feed.chip
        self.mrr = feed.mrr
        self.fs = feed.fs

        if self.scale == Scale.TICK:
            self.tick = feed.tick

        elif self.scale == Scale.DAY:
            self.price = feed.price

    @staticmethod
    def _lookup_close_and_volume_lots(
        close_map: Dict[str, Any], volume_map: Dict[str, int], stock_id: str
    ) -> Tuple[Optional[float], Optional[int]]:
        """自單日全市場對照表取出該股收盤價與成交量（張）。"""

        if stock_id not in close_map:
            return None, None

        close_px: float = float(close_map[stock_id])
        return close_px, volume_map.get(stock_id)

    def _get_next_trading_date_after(self, after_date: datetime.date) -> datetime.date:
        """開倉日之後的「下一個交易日」（跳過休市日）。"""
        d: datetime.date = after_date + datetime.timedelta(days=1)
        while not MarketCalendar.check_stock_market_open(self.price, d):
            d += datetime.timedelta(days=1)
        return d

    def check_open_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        """開倉：T−1 收盤相對 T−2 收盤達漲幅且 T−1 量達標，於 T 日以 open 買進"""

        open_positions: List[StockQuote] = []

        if self.max_holdings == 0 or not stock_quotes:
            return []

        base_date: datetime.date = stock_quotes[0].date
        d_minus_1: datetime.date = MarketCalendar.get_last_trading_date(
            api=self.price, date=base_date
        )
        d_minus_2: datetime.date = MarketCalendar.get_last_trading_date(
            api=self.price, date=d_minus_1
        )

        close_map_d1: Dict[str, Any] = self.price.get_close_map(d_minus_1)
        close_map_d2: Dict[str, Any] = self.price.get_close_map(d_minus_2)
        volume_map_d1: Dict[str, int] = self.price.get_volume_lots_map(d_minus_1)

        if not close_map_d1 or not close_map_d2:
            logger.warning(
                f"{base_date}: T-1 或 T-2 價量資料為空 (d1={d_minus_1}, d2={d_minus_2})"
            )
            return []

        for stock_quote in stock_quotes:
            if self.account.check_has_position(stock_quote.stock_id):
                continue

            close_d1, vol_d1_lots = self._lookup_close_and_volume_lots(
                close_map_d1, volume_map_d1, stock_quote.stock_id
            )
            close_d2, _ = self._lookup_close_and_volume_lots(
                close_map_d2, {}, stock_quote.stock_id
            )

            if close_d1 is None or close_d2 is None:
                logger.warning(
                    f"股票 {stock_quote.stock_id} 在 {d_minus_1}/{d_minus_2} 收盤資料缺失"
                )
                continue

            if close_d2 == 0:
                logger.warning(
                    f"股票 {stock_quote.stock_id} {d_minus_2} 收盤價為 0，略過漲幅計算"
                )
                continue

            price_chg: float = (close_d1 / close_d2 - 1) * 100
            if price_chg < self.MIN_PRICE_CHANGE_PCT_FOR_SIGNAL:
                continue

            if vol_d1_lots is None or vol_d1_lots < self.MIN_VOLUME_LOTS:
                continue

            if stock_quote.open <= 0:
                logger.warning(
                    f"股票 {stock_quote.stock_id} {base_date} 開盤價無效，略過"
                )
                continue

            logger.info(
                f"股票 {stock_quote.stock_id} T-1 相對 T-2 漲幅 {round(price_chg, 2)}%，"
                f"T-1 成交量 {vol_d1_lots} 張"
            )
            open_positions.append(stock_quote)

        return self.calculate_position_size(open_positions, Action.BUY)

    def check_close_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        """平倉：報價日為開倉日之「下一交易日」時，以當日 open 賣出"""

        close_positions: List[StockQuote] = []

        for stock_quote in stock_quotes:
            if not self.account.check_has_position(stock_quote.stock_id):
                continue
            position: Optional[StockPosition] = self.account.get_first_open_position(
                stock_quote.stock_id
            )
            if position is None:
                logger.warning(f"股票 {stock_quote.stock_id} 沒有開倉記錄")
                continue

            exit_date: datetime.date = self._get_next_trading_date_after(position.date)
            if stock_quote.date == exit_date and stock_quote.open > 0:
                close_positions.append(stock_quote)

        return self.calculate_position_size(close_positions, Action.SELL)

    def check_stop_loss_signal(
        self, stock_quotes: List[StockQuote]
    ) -> List[StockOrder]:
        """停損：未實作"""
        return []

    def calculate_position_size(
        self, stock_quotes: List[StockQuote], action: Action
    ) -> List[StockOrder]:
        """BUY 以 open 計張數與成交價；SELL 以 open 平倉"""

        orders: List[StockOrder] = []

        if action == Action.BUY:
            # 張數由 EqualWeightSizer 統一計算；本策略以當日開盤價為參考價與成交價
            candidates: List[Tuple[StockQuote, float]] = [
                (stock_quote, stock_quote.open) for stock_quote in stock_quotes
            ]

            for stock_quote, open_px, open_volume in self.sizer.size(
                self.account, candidates, self.max_holdings
            ):
                orders.append(
                    StockOrder(
                        stock_id=stock_quote.stock_id,
                        date=stock_quote.date,
                        action=action,
                        position_type=PositionType.LONG,
                        price=open_px,
                        volume=open_volume,
                    )
                )
        elif action == Action.SELL:
            for stock_quote in stock_quotes:
                position: Optional[StockPosition] = (
                    self.account.get_first_open_position(stock_quote.stock_id)
                )
                if position is None:
                    continue

                sell_px: float = stock_quote.open
                if sell_px <= 0:
                    continue

                orders.append(
                    StockOrder(
                        stock_id=stock_quote.stock_id,
                        date=stock_quote.date,
                        action=action,
                        position_type=position.position_type,
                        price=sell_px,
                        volume=position.volume,
                    )
                )
        return orders
