# Python standard library
import datetime
from typing import List, Optional, Tuple

import pandas as pd
from loguru import logger

from trader.api.stock_price_api import StockPriceAPI
from trader.models import StockAccount, StockOrder, StockPosition, StockQuote
from trader.strategies.stock import BaseStockStrategy
from trader.utils import Action, Market, PositionType, Scale, Units
from trader.utils.market_calendar import MarketCalendar


class NewMomentumStrategy(BaseStockStrategy):
    """
    新動能策略

    買進條件（全部滿足）：
    - 5日線 > 10日線 > 20日線
    - 成交量 > 5000 張
    - 20 < 股價 < 300

    賣出條件（任一滿足）：
    - 5天內漲幅 > 25%
    - 買進大於5天後，已是獲利且 5日線跌破20日線

    停損條件：
    - 未實現虧損 > 10%
    """

    DEFAULT_MAX_HOLDINGS: int = 10
    DEFAULT_BACKTEST_START_DATE: datetime.date = datetime.date(2025, 1, 1)
    DEFAULT_BACKTEST_END_DATE: datetime.date = datetime.date(2025, 12, 31)

    # 買進參數
    MIN_VOLUME_LOTS: int = 5000  # 最小成交量（張）
    MIN_PRICE: float = 20.0
    MAX_PRICE: float = 300.0

    # 賣出參數
    TAKE_PROFIT_PCT: float = 25.0  # 5天內漲幅 > 25% 獲利了結
    TAKE_PROFIT_HOLDING_DAYS: int = 5  # 上述條件適用於持倉 5 天內
    MA_CROSS_HOLDING_DAYS: int = 5  # 買進大於 5 天後才檢查 MA 交叉

    # 停損參數
    STOP_LOSS_PCT: float = 10.0  # 虧損超過 10% 停損

    def __init__(self):
        super().__init__()
        self.strategy_name: str = "NewMomentum"
        self.market: str = Market.STOCK
        self.position_type: str = PositionType.LONG
        self.init_capital: float = 1000000.0
        self.max_holdings: int = self.DEFAULT_MAX_HOLDINGS
        self.scale: str = Scale.DAY
        self.start_date: datetime.date = self.DEFAULT_BACKTEST_START_DATE
        self.end_date: datetime.date = self.DEFAULT_BACKTEST_END_DATE

        self.setup_apis()

    def setup_account(self, account: StockAccount) -> None:
        """設置虛擬帳戶資訊"""
        self.account: StockAccount = account

    def setup_apis(self) -> None:
        """設置資料 API"""
        if self.scale in (Scale.DAY, Scale.MIX):
            self.price: StockPriceAPI = StockPriceAPI()

    def _get_ma_values(
        self, stock_id: str, current_date: datetime.date
    ) -> Optional[Tuple[float, float, float]]:
        """
        取得指定日期的 5日、10日、20日 均線（以當日收盤價為基準，含當日）

        Returns:
            (ma5, ma10, ma20) 或 None（若資料不足）
        """
        # 取足夠範圍以涵蓋 20 個交易日（約 30 個日曆日）
        start_date: datetime.date = current_date - datetime.timedelta(days=45)

        prices_df: pd.DataFrame = self.price.get_stock_price(
            stock_id=stock_id,
            start_date=start_date,
            end_date=current_date,
        )

        if prices_df.empty or len(prices_df) < 20:
            return None

        # 依日期排序，取最後 20 筆
        prices_df = prices_df.sort_values("date").tail(20)
        close_series = prices_df["收盤價"]

        ma5: float = close_series.tail(5).mean()
        ma10: float = close_series.tail(10).mean()
        ma20: float = close_series.tail(20).mean()

        return (ma5, ma10, ma20)

    def check_open_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        """開倉策略：5日線 > 10日線 > 20日線，成交量 > 5000 張，20 < 股價 < 300"""
        open_positions: List[StockQuote] = []

        if self.max_holdings > 0 and self.account.get_position_count() >= self.max_holdings:
            return []

        for stock_quote in stock_quotes:
            if self.account.check_has_position(stock_quote.stock_id):
                continue

            # a. 5日線 > 10日線 > 20日線
            ma_result = self._get_ma_values(stock_quote.stock_id, stock_quote.date)
            if ma_result is None:
                continue

            ma5, ma10, ma20 = ma_result
            if not (ma5 > ma10 > ma20):
                continue

            # b. 成交量 > 5000 張
            if stock_quote.volume < self.MIN_VOLUME_LOTS:
                continue

            # c. 20 < 股價 < 300
            if not (self.MIN_PRICE < stock_quote.close < self.MAX_PRICE):
                continue

            logger.info(
                f"股票 {stock_quote.stock_id} 符合買進條件："
                f"MA5={ma5:.2f} > MA10={ma10:.2f} > MA20={ma20:.2f}，"
                f"成交量 {stock_quote.volume} 張，股價 {stock_quote.close:.2f}"
            )
            open_positions.append(stock_quote)

        return self.calculate_position_size(open_positions, Action.BUY)

    def check_close_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        """平倉策略：5天內漲幅 > 25% 或 持倉>5天且獲利且5日線跌破20日線"""
        close_positions: List[StockQuote] = []

        for stock_quote in stock_quotes:
            if not self.account.check_has_position(stock_quote.stock_id):
                continue

            position: Optional[StockPosition] = (
                self.account.get_first_open_position(stock_quote.stock_id)
            )
            if position is None:
                continue

            holding_days: int = (stock_quote.date - position.date).days
            profit_rate: float = (stock_quote.close / position.price - 1) * 100

            # a. 5天內漲幅 > 25%
            if holding_days <= self.TAKE_PROFIT_HOLDING_DAYS and profit_rate > self.TAKE_PROFIT_PCT:
                logger.info(
                    f"股票 {stock_quote.stock_id} 5天內漲幅 {profit_rate:.2f}% > 25% → 獲利了結"
                )
                close_positions.append(stock_quote)
                continue

            # b. 買進大於5天後，已是獲利且 5日線跌破20日線
            if holding_days > self.MA_CROSS_HOLDING_DAYS and profit_rate > 0:
                ma_result = self._get_ma_values(stock_quote.stock_id, stock_quote.date)
                if ma_result is not None:
                    ma5, _, ma20 = ma_result
                    if ma5 < ma20:
                        logger.info(
                            f"股票 {stock_quote.stock_id} 持倉 {holding_days} 天，"
                            f"獲利 {profit_rate:.2f}%，5日線 {ma5:.2f} 跌破 20日線 {ma20:.2f} → 出場"
                        )
                        close_positions.append(stock_quote)

        return self.calculate_position_size(close_positions, Action.SELL)

    def check_stop_loss_signal(
        self, stock_quotes: List[StockQuote]
    ) -> List[StockOrder]:
        """停損策略：未實現虧損 > 10%"""
        stop_loss_orders: List[StockQuote] = []

        for stock_quote in stock_quotes:
            if not self.account.check_has_position(stock_quote.stock_id):
                continue

            position: Optional[StockPosition] = (
                self.account.get_first_open_position(stock_quote.stock_id)
            )
            if position is None:
                continue

            loss_rate: float = (stock_quote.close / position.price - 1) * 100

            # 未實現虧損 > 10%（即 loss_rate < -10%）
            if loss_rate < -self.STOP_LOSS_PCT:
                logger.warning(
                    f"股票 {stock_quote.stock_id} 觸發停損，"
                    f"未實現虧損 {loss_rate:.2f}%"
                )
                stop_loss_orders.append(stock_quote)

        return self.calculate_position_size(stop_loss_orders, Action.SELL)

    def calculate_position_size(
        self, stock_quotes: List[StockQuote], action: Action
    ) -> List[StockOrder]:
        """計算 Open or Close 的部位大小"""
        orders: List[StockOrder] = []

        if action == Action.BUY:
            available_position_cnt: int = (
                max(0, self.max_holdings - self.account.get_position_count())
                if self.max_holdings is not None
                else len(stock_quotes)
            )

            if available_position_cnt > 0:
                per_position_size: float = (
                    self.account.balance / available_position_cnt
                )

                for stock_quote in stock_quotes:
                    if available_position_cnt == 0:
                        break

                    open_volume: int = int(
                        per_position_size / (stock_quote.close * Units.LOT)
                    )

                    if open_volume >= 1:
                        orders.append(
                            StockOrder(
                                stock_id=stock_quote.stock_id,
                                date=stock_quote.date,
                                action=action,
                                position_type=PositionType.LONG,
                                price=stock_quote.cur_price,
                                volume=open_volume,
                            )
                        )
                        available_position_cnt -= 1

        elif action == Action.SELL:
            for stock_quote in stock_quotes:
                position: Optional[StockPosition] = (
                    self.account.get_first_open_position(stock_quote.stock_id)
                )

                if position is None:
                    continue

                orders.append(
                    StockOrder(
                        stock_id=stock_quote.stock_id,
                        date=stock_quote.date,
                        action=action,
                        position_type=position.position_type,
                        price=stock_quote.cur_price,
                        volume=position.volume,
                    )
                )

        return orders
