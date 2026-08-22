# Python standard library
import datetime
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from core.backtest.datafeed.base import BaseDataFeed
from core.backtest.datafeed.market_calendar import MarketCalendar
from core.models import StockAccount, StockOrder, StockPosition, StockQuote
from core.strategies.stock import BaseStockStrategy
from core.utils import Action, PositionType, Scale


class MomentumStrategy1(BaseStockStrategy):
    """
    動能策略 1（日線）

    買進條件（全部滿足）：
    - 當日收盤相對「前一交易日」收盤漲幅 ≥ 門檻（預設 9%）
    - 當日成交量 ≥ 門檻（預設 5000 張）

    賣出條件：
    - 已有部位且「報價日」≥ 開倉日 + 1 日曆日（持倉至少隔一天後可平倉）

    停損條件：
    - 未實作（一律不回傳停損單）
    """

    DEFAULT_MAX_HOLDINGS: int = 10
    DEFAULT_BACKTEST_START_DATE: datetime.date = datetime.date(2020, 5, 1)
    DEFAULT_BACKTEST_END_DATE: datetime.date = datetime.date(2025, 5, 31)

    # 買進參數
    MIN_PRICE_CHANGE_PCT_FOR_SIGNAL: float = 9.0  # 相對昨收之最小漲幅（%）
    MIN_VOLUME_LOTS: int = 5000  # 最小成交量（張）

    def __init__(self):
        super().__init__()
        self.strategy_name: str = "Momentum-1"
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

    def check_open_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        """開倉策略：昨收基準漲幅達門檻且成交量達門檻，做多；部位數由 calculate_position_size 依 max_holdings 與資金切分"""

        open_positions: List[StockQuote] = []

        if self.max_holdings == 0:
            return []

        # 以「前一交易日」收盤為基準計算當日漲跌幅（非日曆昨日）
        yesterday: datetime.date = MarketCalendar.get_last_trading_date(
            api=self.price, date=stock_quotes[0].date
        )

        # 訊號用收盤價：與下方的 signal_close 成對，由引擎的還原模式統一決定
        yesterday_close_map: Dict[str, Any] = self.get_signal_close_map(
            stock_quotes, yesterday
        )

        for stock_quote in stock_quotes:
            # a. 對齊該股在昨交易日的收盤價；缺資料或價格無效則跳過
            if stock_quote.stock_id not in yesterday_close_map:
                logger.warning(f"股票 {stock_quote.stock_id} {yesterday} 收盤價為空")
                continue
            yesterday_close_price: float = yesterday_close_map[stock_quote.stock_id]

            if yesterday_close_price == 0:
                logger.warning(
                    f"股票 {stock_quote.stock_id} {yesterday} 收盤價為 0 或 None"
                )
                continue

            # b. 當日收盤相對昨收之漲幅（%）≥ MIN_PRICE_CHANGE_PCT_FOR_SIGNAL
            price_chg: float = (
                stock_quote.signal_close / yesterday_close_price - 1
            ) * 100

            if price_chg < self.MIN_PRICE_CHANGE_PCT_FOR_SIGNAL:
                continue
            logger.info(f"股票 {stock_quote.stock_id} 漲幅 {round(price_chg, 2)}%")

            # c. 當日成交量 ≥ MIN_VOLUME_LOTS（張）
            if stock_quote.volume < self.MIN_VOLUME_LOTS:
                continue

            open_positions.append(stock_quote)

        return self.calculate_position_size(open_positions, Action.BUY)

    def check_close_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        """平倉策略：帳上已有該股部位時，若報價日 ≥ 開倉日 + 1 日曆日則列入出場候選（至少持有一天後可賣）"""

        close_positions: List[StockQuote] = []

        for stock_quote in stock_quotes:
            if self.account.check_has_position(stock_quote.stock_id):
                position: Optional[StockPosition] = (
                    self.account.get_first_open_position(stock_quote.stock_id)
                )
                if position is None:
                    logger.warning(f"股票 {stock_quote.stock_id} 沒有開倉記錄")
                    continue
                # 開倉當日不平：隔日（含）起才允許平倉
                if stock_quote.date >= position.date + datetime.timedelta(days=1):
                    close_positions.append(stock_quote)

        return self.calculate_position_size(close_positions, Action.SELL)

    def check_stop_loss_signal(
        self, stock_quotes: List[StockQuote]
    ) -> List[StockOrder]:
        """停損策略：本策略未實作停損，固定回傳空列表"""
        return []

    def calculate_position_size(
        self, stock_quotes: List[StockQuote], action: Action
    ) -> List[StockOrder]:
        """計算部位：BUY 時依剩餘可開倉名額均分餘額並換算張數；SELL 時全數平掉該筆開倉部位"""

        orders: List[StockOrder] = []

        if action == Action.BUY:
            # 張數由 EqualWeightSizer 統一計算；本策略只負責選參考價（當日收盤）
            candidates: List[Tuple[StockQuote, float]] = [
                (stock_quote, stock_quote.close) for stock_quote in stock_quotes
            ]

            for stock_quote, _, open_volume in self.sizer.size(
                self.account, candidates, self.max_holdings
            ):
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
        elif action == Action.SELL:
            # 平倉：依該股第一筆開倉部位的張數與多空類型全數賣出
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
