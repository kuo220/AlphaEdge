# Python standard library
import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

from core.backtest.datafeed.base import BaseDataFeed
from core.models import StockAccount, StockOrder, StockPosition, StockQuote
from core.strategies.stock import BaseStockStrategy
from core.utils import Action, PositionType, Scale, Units
from core.backtest.datafeed.market_calendar import MarketCalendar


class MomentumStrategy5(BaseStockStrategy):
    """
    動能策略 5（投信籌碼動能，日線）

    名詞約定（避免 look-ahead bias）：
    - 設框架當前交易日為 T（即實際下單日），於 T 日開盤價買進
    - 所有判斷條件只使用 T 日開盤前已可得的資料（不使用 T 當日盤中或收盤資訊）

    買進條件（全部滿足，於 T 日以開盤價成交）：
    - 投信買賣超股數 > 0 連續三日：T−1、T−2、T−3
        （即 T−1、T−2、T−3 三個交易日的 `投信買賣超股數` 皆 > 0）
    - 前一日漲幅 > 門檻（預設 9%），漲幅以 T−1 收盤相對 T−2 收盤計算
    - T−1 成交量 ≥ 門檻（預設 5000 張）
    - T 日開盤漲幅（相對 T−1 收盤）> 門檻（預設 3%），且 < 漲停過濾門檻（預設 9%）

    賣出條件：
    - 開倉日後第 5 個交易日（T+5）以開盤價（open）全數平倉

    停損條件：
    - 未實作（一律不回傳停損單）
    """

    DEFAULT_MAX_HOLDINGS: int = 10
    DEFAULT_BACKTEST_START_DATE: datetime.date = datetime.date(2021, 1, 1)
    DEFAULT_BACKTEST_END_DATE: datetime.date = datetime.date(2026, 4, 30)

    MIN_PRICE_CHANGE_PCT_FOR_SIGNAL: float = 9.0  # T−1 收盤相對 T−2 收盤之最小漲幅（%）
    MIN_VOLUME_LOTS: int = 5000  # T−1 最小成交量（張）
    MIN_OPEN_GAP_PCT: float = 3.0  # T 開盤相對 T−1 收盤之最小漲幅（%）
    LIMIT_UP_PCT: float = 9.0  # 開盤漲幅上限（%），避免開盤接近漲停難成交
    HOLDING_TRADING_DAYS: int = 5  # 持倉交易日數，於開倉日後第 N 日（T+N）開盤賣出
    TRUST_NET_BUY_LOOKBACK_DAYS: int = 3  # 連續觀察的「投信買賣超股數 > 0」交易日數

    def __init__(self):
        super().__init__()
        self.strategy_name: str = "Momentum-5"
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
    def _lookup_close(close_map: Dict[str, Any], stock_id: str) -> Optional[float]:
        """自單日全市場對照表取出該股收盤價。資料缺失或值異常時回傳 None。"""

        if stock_id not in close_map:
            return None
        try:
            return float(close_map[stock_id])
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _lookup_trust_net_buy(
        chip_map: Dict[str, Any], stock_id: str
    ) -> Optional[int]:
        """自單日全市場籌碼對照表取出該股投信買賣超股數；缺資料回傳 None。"""

        if stock_id not in chip_map:
            return None
        try:
            return int(chip_map[stock_id])
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

    def _get_trading_date_after(
        self, after_date: datetime.date, trading_days: int
    ) -> datetime.date:
        """開倉日之後第 N 個交易日（N=1 為隔日，N=5 為 T+5）。"""
        d: datetime.date = after_date
        found: int = 0
        while found < trading_days:
            d += datetime.timedelta(days=1)
            while not MarketCalendar.check_stock_market_open(self.price, d):
                d += datetime.timedelta(days=1)
            found += 1
        return d

    def check_open_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        """開倉：投信連買、T−1 漲幅/量能達標、T 開盤跳空 > 3%；於 T 日開盤價買進"""

        open_positions: List[StockQuote] = []

        if self.max_holdings == 0 or not stock_quotes:
            return []

        base_date: datetime.date = stock_quotes[0].date

        # T = base_date（當日開盤進場日）；往前找 T−1、T−2、T−3。
        # 需求：T−1、T−2、T−3 三日「投信買賣超股數 > 0」，
        # 且前一日漲幅 (T−1 收盤 / T−2 收盤 - 1) > 9%。
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

        d_t_minus_1: datetime.date = prev_dates[0]  # T−1
        d_t_minus_2: datetime.date = prev_dates[1]  # T−2
        chip_dates: List[datetime.date] = prev_dates[: self.TRUST_NET_BUY_LOOKBACK_DAYS]

        close_map_t_minus_1: Dict[str, Any] = self.price.get_close_map(d_t_minus_1)
        close_map_t_minus_2: Dict[str, Any] = self.price.get_close_map(d_t_minus_2)
        volume_map_t_minus_1: Dict[str, int] = self.price.get_volume_lots_map(
            d_t_minus_1
        )

        if not close_map_t_minus_1 or not close_map_t_minus_2:
            logger.warning(
                f"{base_date}: T-1 或 T-2 價量資料為空 (T-1={d_t_minus_1}, T-2={d_t_minus_2})"
            )
            return []

        chip_maps: List[Dict[str, Any]] = [
            self.chip.get_trust_net_shares_map(d) for d in chip_dates
        ]
        if any(not chip_map for chip_map in chip_maps):
            empty_dates: List[str] = [
                str(d) for d, chip_map in zip(chip_dates, chip_maps) if not chip_map
            ]
            logger.warning(f"{base_date}: 籌碼資料為空，缺日 {empty_dates}")
            return []

        for stock_quote in stock_quotes:
            if self.account.check_has_position(stock_quote.stock_id):
                continue

            close_t_minus_1: Optional[float] = self._lookup_close(
                close_map_t_minus_1, stock_quote.stock_id
            )
            close_t_minus_2: Optional[float] = self._lookup_close(
                close_map_t_minus_2, stock_quote.stock_id
            )

            if close_t_minus_1 is None or close_t_minus_2 is None:
                logger.warning(
                    f"股票 {stock_quote.stock_id} 在 {d_t_minus_1}/{d_t_minus_2} 收盤資料缺失"
                )
                continue

            if close_t_minus_2 == 0:
                logger.warning(
                    f"股票 {stock_quote.stock_id} {d_t_minus_2} 收盤價為 0，略過漲幅計算"
                )
                continue

            price_chg: float = (close_t_minus_1 / close_t_minus_2 - 1) * 100
            if price_chg <= self.MIN_PRICE_CHANGE_PCT_FOR_SIGNAL:
                continue

            vol_t_minus_1_lots: Optional[int] = volume_map_t_minus_1.get(
                stock_quote.stock_id
            )
            if vol_t_minus_1_lots is None or vol_t_minus_1_lots < self.MIN_VOLUME_LOTS:
                continue

            # 連續 N 日投信買賣超股數 > 0（T−1, T−2, T−3）
            net_buys: List[Optional[int]] = [
                self._lookup_trust_net_buy(chip_map, stock_quote.stock_id)
                for chip_map in chip_maps
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

            open_chg_pct: float = (stock_quote.open / close_t_minus_1 - 1) * 100
            if open_chg_pct <= self.MIN_OPEN_GAP_PCT:
                continue
            if open_chg_pct >= self.LIMIT_UP_PCT:
                logger.info(
                    f"股票 {stock_quote.stock_id} T({base_date}) 開盤漲幅 "
                    f"{round(open_chg_pct, 2)}%（>= {self.LIMIT_UP_PCT}% 漲停門檻），略過買進"
                )
                continue

            logger.info(
                f"股票 {stock_quote.stock_id} T-1({d_t_minus_1}) 漲幅 {round(price_chg, 2)}%、"
                f"量 {vol_t_minus_1_lots} 張，投信 {chip_dates} 買賣超 {net_buys}（皆 > 0），"
                f"T({base_date}) 開盤漲 {round(open_chg_pct, 2)}%，開盤買進"
            )
            open_positions.append(stock_quote)

        return self.calculate_position_size(open_positions, Action.BUY)

    def check_close_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        """平倉：報價日為開倉日後第 5 個交易日（T+5）時，以當日 open 賣出"""

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

            exit_date: datetime.date = self._get_trading_date_after(
                position.date, self.HOLDING_TRADING_DAYS
            )
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
