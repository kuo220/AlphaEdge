# Python standard library
import datetime
from typing import List, Optional, Tuple

import pandas as pd
from loguru import logger

from core.backtest.datafeed.base import BaseDataFeed
from core.models import StockAccount, StockOrder, StockPosition, StockQuote
from core.strategies.stock import BaseStockStrategy
from core.utils import Action, PositionType, Scale, Units
from core.utils.instrument import StockUtils
from core.utils.market_calendar import MarketCalendar


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
    def _row_close_and_volume_lots(
        prices_df: pd.DataFrame, stock_id: str
    ) -> Tuple[Optional[float], Optional[int]]:
        """自單日全市場 DataFrame 取出該股收盤價與成交量（張）。"""
        mask: pd.Series = prices_df["stock_id"] == stock_id
        if prices_df.loc[mask, "收盤價"].empty:
            return None, None
        close_px: float = float(prices_df.loc[mask, "收盤價"].iloc[0])
        shares = prices_df.loc[mask, "成交股數"].iloc[0]
        volume_lots: int = StockUtils.convert_share_to_lot(int(shares))
        return close_px, volume_lots

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

        prices_d1: pd.DataFrame = self.price.get(d_minus_1)
        prices_d2: pd.DataFrame = self.price.get(d_minus_2)

        if prices_d1.empty or prices_d2.empty:
            logger.warning(
                f"{base_date}: T-1 或 T-2 價量資料為空 (d1={d_minus_1}, d2={d_minus_2})"
            )
            return []

        for stock_quote in stock_quotes:
            if self.account.check_has_position(stock_quote.stock_id):
                continue

            close_d1, vol_d1_lots = self._row_close_and_volume_lots(
                prices_d1, stock_quote.stock_id
            )
            close_d2, _ = self._row_close_and_volume_lots(
                prices_d2, stock_quote.stock_id
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
            available_position_cnt: int = (
                max(0, self.max_holdings - self.account.get_position_count())
                if self.max_holdings is not None
                else len(stock_quotes)
            )

            if available_position_cnt > 0:
                per_position_size: float = self.account.balance / available_position_cnt

                for stock_quote in stock_quotes:
                    open_px: float = stock_quote.open
                    if open_px <= 0:
                        continue

                    open_volume: int = int(
                        per_position_size / (open_px * Units.LOT)
                    )

                    if open_volume >= 1:
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
                        available_position_cnt -= 1

                    if available_position_cnt == 0:
                        break
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
