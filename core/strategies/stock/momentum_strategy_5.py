# Python standard library
import datetime
from typing import List, Optional, Tuple

import pandas as pd
from loguru import logger

from core.api.financial_statement_api import FinancialStatementAPI
from core.api.monthly_revenue_report_api import MonthlyRevenueReportAPI
from core.api.stock_chip_api import StockChipAPI
from core.api.stock_price_api import StockPriceAPI
from core.api.stock_tick_api import StockTickAPI
from core.models import StockAccount, StockOrder, StockPosition, StockQuote
from core.strategies.stock import BaseStockStrategy
from core.utils import Action, PositionType, Scale, Units
from core.utils.market_calendar import MarketCalendar


class MomentumStrategy5(BaseStockStrategy):
    """
    動能策略 5（投信籌碼動能，日線）

    名詞約定（避免 look-ahead bias）：
    - 設使用者語境之「訊號日 T」 = 框架當前交易日 D 的「前一交易日」
        亦即 T = D − 1，T−1 = D − 2，T−2 = D − 3，T−3 = D − 4
    - 所有判斷條件只使用 D 日開盤前已可得的資料（不使用 D 當日盤中或收盤資訊）

    買進條件（全部滿足，於 D 日以開盤價成交）：
    - 投信買賣超股數 > 0 連續三日：T−1、T−2、T−3
        （即 D−2、D−3、D−4 三個交易日的 `投信買賣超股數` 皆 > 0）
    - T 當日漲幅 > 門檻（預設 8%），漲幅以 T 收盤相對 T−1 收盤計算
        （即 D−1 收盤相對 D−2 收盤之漲幅 > 8%）

    賣出條件：
    - 開倉日的「下一個交易日」以開盤價（open）全數平倉

    停損條件：
    - 未實作（一律不回傳停損單）
    """

    DEFAULT_MAX_HOLDINGS: int = 10
    DEFAULT_BACKTEST_START_DATE: datetime.date = datetime.date(2022, 1, 1)
    DEFAULT_BACKTEST_END_DATE: datetime.date = datetime.date(2026, 4, 30)

    MIN_PRICE_CHANGE_PCT_FOR_SIGNAL: float = 8.0  # T 收盤相對 T−1 收盤之最小漲幅（%）
    TRUST_NET_BUY_LOOKBACK_DAYS: int = 3  # 連續觀察的「投信買賣超股數 > 0」交易日數

    def __init__(self):
        super().__init__()
        self.strategy_name: str = "Momentum-5"
        self.init_capital: float = 1000000.0
        self.max_holdings: int = self.DEFAULT_MAX_HOLDINGS
        self.scale: Scale = Scale.DAY

        self.start_date: datetime.date = self.DEFAULT_BACKTEST_START_DATE
        self.end_date: datetime.date = self.DEFAULT_BACKTEST_END_DATE

        self.setup_apis()

    def setup_account(self, account: StockAccount) -> None:
        """設置虛擬帳戶資訊"""

        self.account: StockAccount = account

    def setup_apis(self) -> None:
        """設置資料 API：日線價量 + 三大法人籌碼"""

        self.chip: StockChipAPI = StockChipAPI()
        self.mrr: MonthlyRevenueReportAPI = MonthlyRevenueReportAPI()
        self.fs: FinancialStatementAPI = FinancialStatementAPI()

        if self.scale in (Scale.TICK, Scale.MIX):
            self.tick: StockTickAPI = StockTickAPI()

        elif self.scale in (Scale.DAY, Scale.MIX):
            self.price: StockPriceAPI = StockPriceAPI()

        elif self.scale in (Scale.MIX, Scale.ALL):
            self.tick: StockTickAPI = StockTickAPI()
            self.price: StockPriceAPI = StockPriceAPI()

    @staticmethod
    def _row_close(prices_df: pd.DataFrame, stock_id: str) -> Optional[float]:
        """自單日全市場 DataFrame 取出該股收盤價。資料缺失時回傳 None。"""
        mask: pd.Series = prices_df["stock_id"] == stock_id
        series: pd.Series = prices_df.loc[mask, "收盤價"]
        if series.empty:
            return None
        try:
            return float(series.iloc[0])
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _row_trust_net_buy(chip_df: pd.DataFrame, stock_id: str) -> Optional[int]:
        """自單日全市場籌碼 DataFrame 取出該股投信買賣超股數；缺資料回傳 None。"""
        if chip_df.empty:
            return None
        mask: pd.Series = chip_df["stock_id"] == stock_id
        series: pd.Series = chip_df.loc[mask, "投信買賣超股數"]
        if series.empty:
            return None
        try:
            return int(series.iloc[0])
        except (TypeError, ValueError):
            return None

    def _previous_trading_dates(
        self, base_date: datetime.date, lookback: int
    ) -> List[datetime.date]:
        """回傳 base_date 之前 `lookback` 個交易日，順序由最近到最遠。"""
        dates: List[datetime.date] = []
        cursor: datetime.date = base_date
        for _ in range(lookback):
            cursor = MarketCalendar.get_last_trading_date(api=self.price, date=cursor)
            dates.append(cursor)
        return dates

    def _get_next_trading_date_after(self, after_date: datetime.date) -> datetime.date:
        """開倉日之後的「下一個交易日」（跳過休市日）。"""
        d: datetime.date = after_date + datetime.timedelta(days=1)
        while not MarketCalendar.check_stock_market_open(self.price, d):
            d += datetime.timedelta(days=1)
        return d

    def check_open_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        """開倉：T−1/T−2/T−3 投信買賣超皆 > 0，且 T 漲幅 > 8%；於 D 日（=T+1）以開盤價買進"""

        open_positions: List[StockQuote] = []

        if self.max_holdings == 0 or not stock_quotes:
            return []

        base_date: datetime.date = stock_quotes[0].date

        # D = base_date；以 D 為錨點往前找出 T、T−1、T−2、T−3 四個交易日。
        # 需求：T−1、T−2、T−3 三日「投信買賣超股數 > 0」，且 T 漲幅 > 8%。
        # T = D−1（最近一個交易日），漲幅算 T 收盤 / T−1 收盤；
        # 籌碼條件對應日為 D−2、D−3、D−4。
        prev_dates: List[datetime.date] = self._previous_trading_dates(
            base_date=base_date,
            lookback=self.TRUST_NET_BUY_LOOKBACK_DAYS + 1,
        )

        if len(prev_dates) < self.TRUST_NET_BUY_LOOKBACK_DAYS + 1:
            logger.warning(
                f"{base_date}: 找不到足夠的歷史交易日（需要 "
                f"{self.TRUST_NET_BUY_LOOKBACK_DAYS + 1} 個，實際 {len(prev_dates)} 個）"
            )
            return []

        d_t: datetime.date = prev_dates[0]  # T
        d_t_minus_1: datetime.date = prev_dates[1]  # T−1
        chip_dates: List[datetime.date] = prev_dates[1:]  # T−1, T−2, T−3

        prices_t: pd.DataFrame = self.price.get(d_t)
        prices_t_minus_1: pd.DataFrame = self.price.get(d_t_minus_1)

        if prices_t.empty or prices_t_minus_1.empty:
            logger.warning(
                f"{base_date}: T 或 T-1 價量資料為空 (T={d_t}, T-1={d_t_minus_1})"
            )
            return []

        chip_frames: List[pd.DataFrame] = [self.chip.get(d) for d in chip_dates]
        if any(df.empty for df in chip_frames):
            empty_dates: List[str] = [
                str(d) for d, df in zip(chip_dates, chip_frames) if df.empty
            ]
            logger.warning(f"{base_date}: 籌碼資料為空，缺日 {empty_dates}")
            return []

        for stock_quote in stock_quotes:
            if self.account.check_has_position(stock_quote.stock_id):
                continue

            close_t: Optional[float] = self._row_close(prices_t, stock_quote.stock_id)
            close_t_minus_1: Optional[float] = self._row_close(
                prices_t_minus_1, stock_quote.stock_id
            )

            if close_t is None or close_t_minus_1 is None:
                logger.warning(
                    f"股票 {stock_quote.stock_id} 在 {d_t}/{d_t_minus_1} 收盤資料缺失"
                )
                continue

            if close_t_minus_1 == 0:
                logger.warning(
                    f"股票 {stock_quote.stock_id} {d_t_minus_1} 收盤價為 0，略過漲幅計算"
                )
                continue

            price_chg: float = (close_t / close_t_minus_1 - 1) * 100
            if price_chg <= self.MIN_PRICE_CHANGE_PCT_FOR_SIGNAL:
                continue

            # 連續 N 日投信買賣超股數 > 0（T−1, T−2, T−3）
            net_buys: List[Optional[int]] = [
                self._row_trust_net_buy(df, stock_quote.stock_id)
                for df in chip_frames
            ]
            if any(nb is None for nb in net_buys):
                logger.debug(
                    f"股票 {stock_quote.stock_id} 籌碼缺漏（{chip_dates}）"
                )
                continue
            if not all(nb > 0 for nb in net_buys):  # type: ignore[operator]
                continue

            if stock_quote.open <= 0:
                logger.warning(
                    f"股票 {stock_quote.stock_id} {base_date} 開盤價無效，略過"
                )
                continue

            logger.info(
                f"股票 {stock_quote.stock_id} T({d_t}) 漲幅 {round(price_chg, 2)}%，"
                f"投信 {chip_dates} 買賣超 {net_buys}（皆 > 0），於 {base_date} 開盤買進"
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

                    open_volume: int = int(per_position_size / (open_px * Units.LOT))

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
