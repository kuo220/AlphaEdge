# Python standard library
import datetime
from typing import List, Optional

import pandas as pd
from loguru import logger

from trader.api.stock_price_api import StockPriceAPI
from trader.models import StockAccount, StockOrder, StockPosition, StockQuote
from trader.strategies.stock import BaseStockStrategy
from trader.utils import Action, Market, PositionType, Scale, Units
from trader.utils.market_calendar import MarketCalendar


class SimpleLongStrategy(BaseStockStrategy):
    """簡易做多策略

    策略邏輯：
    - 開倉條件：當日漲幅超過 3%，且成交量超過 1000 張
    - 平倉條件：持倉超過 5 天，或獲利超過 10%
    - 停損條件：虧損超過 5%
    """

    def __init__(self):
        super().__init__()

        # === 策略基本資訊 ===
        self.strategy_name: str = "SimpleLong"
        self.market: str = Market.STOCK
        self.position_type: str = PositionType.LONG  # 做多策略
        self.enable_intraday: bool = True

        # === 帳戶設定 ===
        self.init_capital: float = 1000000.0  # 初始資金 100 萬
        self.max_holdings: int = 10  # 最大持倉 10 檔

        # === 回測設定 ===
        self.is_backtest: bool = True
        self.scale: str = Scale.DAY  # 使用日線回測
        self.start_date: datetime.date = datetime.date(2025, 1, 1)
        self.end_date: datetime.date = datetime.date(2025, 12, 31)

        # === 策略參數 ===
        self.min_price_change_pct: float = 8.0  # 最小漲幅百分比（開倉條件）
        self.min_volume: int = 1000  # 最小成交量（張數，開倉條件）
        self.max_holding_days: int = 5  # 最大持倉天數（平倉條件）
        self.profit_target_pct: float = 10.0  # 獲利目標百分比（平倉條件）
        self.stop_loss_pct: float = 5.0  # 停損百分比

        # 載入資料 API
        self.setup_apis()

    def setup_account(self, account: StockAccount):
        """設置虛擬帳戶資訊"""
        self.account = account

    def setup_apis(self):
        """設置資料 API"""
        # 根據回測級別載入對應的價格資料
        if self.scale in (Scale.DAY, Scale.MIX):
            self.price: StockPriceAPI = StockPriceAPI()

    def check_open_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        """開倉策略（做多）"""

        open_positions: List[StockQuote] = []

        # 檢查是否已達最大持倉數
        if (
            self.max_holdings > 0
            and self.account.get_position_count() >= self.max_holdings
        ):
            return []

        # 取得前一個交易日的價格資料
        yesterday: datetime.date = MarketCalendar.get_last_trading_date(
            api=self.price, date=stock_quotes[0].date
        )
        yesterday_prices: pd.DataFrame = self.price.get(yesterday)

        for stock_quote in stock_quotes:
            # 檢查是否已經持有該股票
            if self.account.check_has_position(stock_quote.stock_id):
                continue

            # 取得前一日收盤價
            mask: pd.Series = yesterday_prices["stock_id"] == stock_quote.stock_id
            if yesterday_prices.loc[mask, "收盤價"].empty:
                continue

            yesterday_close: float = yesterday_prices.loc[mask, "收盤價"].iloc[0]
            if yesterday_close == 0:
                continue

            # 計算當日漲幅
            price_chg: float = (stock_quote.close / yesterday_close - 1) * 100

            # 開倉條件：漲幅超過設定值且成交量超過設定值
            if (
                price_chg >= self.min_price_change_pct
                and stock_quote.volume >= self.min_volume
            ):
                logger.info(
                    f"股票 {stock_quote.stock_id} 符合開倉條件："
                    f"漲幅 {round(price_chg, 2)}%，成交量 {stock_quote.volume} 張"
                )
                open_positions.append(stock_quote)

        # 計算部位大小並產生訂單
        return self.calculate_position_size(open_positions, Action.BUY)

    def check_close_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        """平倉策略（做多）"""

        close_positions: List[StockQuote] = []

        for stock_quote in stock_quotes:
            # 檢查是否持有該股票
            if not self.account.check_has_position(stock_quote.stock_id):
                continue

            # 取得持倉資訊
            position: Optional[StockPosition] = self.account.get_first_open_position(
                stock_quote.stock_id
            )
            if position is None:
                continue

            # 計算持倉天數
            holding_days: int = (stock_quote.date - position.date).days

            # 計算獲利比例
            profit_rate: float = (stock_quote.close / position.price - 1) * 100

            # 平倉條件：持倉超過最大天數，或獲利達到目標
            if holding_days >= self.max_holding_days:
                logger.info(
                    f"股票 {stock_quote.stock_id} 持倉 {holding_days} 天，觸發平倉"
                )
                close_positions.append(stock_quote)
            elif profit_rate >= self.profit_target_pct:
                logger.info(
                    f"股票 {stock_quote.stock_id} 獲利 {round(profit_rate, 2)}%，觸發獲利了結"
                )
                close_positions.append(stock_quote)

        # 計算部位大小並產生訂單
        return self.calculate_position_size(close_positions, Action.SELL)

    def check_stop_loss_signal(
        self, stock_quotes: List[StockQuote]
    ) -> List[StockOrder]:
        """停損策略"""

        stop_loss_orders: List[StockQuote] = []

        for stock_quote in stock_quotes:
            # 檢查是否持有該股票
            if not self.account.check_has_position(stock_quote.stock_id):
                continue

            # 取得持倉資訊
            position: Optional[StockPosition] = self.account.get_first_open_position(
                stock_quote.stock_id
            )
            if position is None:
                continue

            # 計算虧損比例
            loss_rate: float = (stock_quote.close / position.price - 1) * 100

            # 停損條件：虧損超過設定值
            if loss_rate <= -self.stop_loss_pct:
                logger.warning(
                    f"股票 {stock_quote.stock_id} 觸發停損，"
                    f"虧損 {round(loss_rate, 2)}%"
                )
                stop_loss_orders.append(stock_quote)

        return self.calculate_position_size(stop_loss_orders, Action.SELL)

    def calculate_position_size(
        self, stock_quotes: List[StockQuote], action: Action
    ) -> List[StockOrder]:
        """計算 Open or Close 的部位大小"""

        orders: List[StockOrder] = []

        if action == Action.BUY:
            # 計算可用的持倉檔數
            if self.max_holdings is not None:
                available_position_cnt: int = max(
                    0, self.max_holdings - self.account.get_position_count()
                )
            else:
                available_position_cnt: int = len(stock_quotes)

            if available_position_cnt > 0:
                # 平均分配資金到每個部位
                per_position_size: float = (
                    self.account.balance / available_position_cnt
                )

                for stock_quote in stock_quotes:
                    if available_position_cnt == 0:
                        break

                    # 計算可買張數：可用資金 / 每張價格
                    # Units.LOT = 1000（1 張 = 1000 股）
                    open_volume: int = int(
                        per_position_size / (stock_quote.close * Units.LOT)
                    )

                    # 至少買 1 張
                    if open_volume >= 1:
                        logger.info(
                            f"計算買入張數：股票 {stock_quote.stock_id}，"
                            f"價格 {stock_quote.close}，下單張數 {open_volume} 張"
                        )
                        orders.append(
                            StockOrder(
                                stock_id=stock_quote.stock_id,
                                date=stock_quote.date,
                                action=action,
                                position_type=PositionType.LONG,
                                price=stock_quote.cur_price,  # 使用當前價格
                                volume=open_volume,
                            )
                        )
                        available_position_cnt -= 1

        elif action == Action.SELL:
            # 平倉時使用持倉的全部股數
            for stock_quote in stock_quotes:
                position: Optional[StockPosition] = (
                    self.account.get_first_open_position(stock_quote.stock_id)
                )

                if position is None:
                    continue

                # 計算要賣出的張數（1 張 = 1000 股）
                sell_volume: int = position.volume // Units.LOT
                logger.info(
                    f"計算賣出張數：股票 {stock_quote.stock_id}，"
                    f"價格 {stock_quote.close}，下單張數 {sell_volume} 張"
                )
                orders.append(
                    StockOrder(
                        stock_id=stock_quote.stock_id,
                        date=stock_quote.date,
                        action=action,
                        position_type=position.position_type,
                        price=stock_quote.cur_price,
                        volume=position.volume,  # 使用持倉的全部股數
                    )
                )

        return orders
