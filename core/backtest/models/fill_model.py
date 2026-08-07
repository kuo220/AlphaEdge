from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

from loguru import logger

from core.backtest.models.instrument_spec import InstrumentSpec, TwStockSpec
from core.models import BaseOrder, BaseQuote
from core.utils import Scale

"""FillModel: 成交價可信度（前視偏誤與不可能成交的擋板）"""


class BaseFillModel(ABC):
    """
    成交價模型：判斷一張訂單在該根 bar 是否可能以指定價格成交

    成交價可信度是市場規則而非引擎邏輯，故與 InstrumentSpec 一樣下沉為可插拔 model。
    對應 Lean 的 FillModel。
    """

    @abstractmethod
    def validate(self, order: BaseOrder, quote: BaseQuote) -> bool:
        """
        - Description:
            成交價合理性檢查
        - Parameters:
            - order: BaseOrder
                待驗證的訂單
            - quote: BaseQuote
                同一標的的當根 bar 報價
        - Return:
            - bool
                False 時呼叫端應拒單
        """
        pass

    @abstractmethod
    def on_bar_open(self, quotes: List[BaseQuote]) -> None:
        """一根 bar 開始：重置並累計盤中已發生的高低點"""
        pass

    @abstractmethod
    def on_bar_close(self, quotes: List[BaseQuote]) -> None:
        """一根 bar 收盤：記錄收盤價，作為次一根 bar 的漲跌停基準"""
        pass


class TwStockFillModel(BaseFillModel):
    """
    台股成交價模型

    - DAY 級別以當日 high/low 為界；TICK 級別以當日「已發生」的累計高低點為界
    - 漲跌停以前一交易日收盤為基準；尚未取得前收時跳過該項檢查
    - 檔位未對齊僅記錄警告，不拒單（避免既有資料的價格精度問題擋掉正常回測）
    """

    def __init__(
        self,
        instrument: Optional[InstrumentSpec] = None,
        event_counts: Optional[Dict[str, int]] = None,
    ):
        self.instrument: InstrumentSpec = instrument or TwStockSpec()

        # 與引擎共用同一個 dict，拒單計數才會反映到報表（傳 None 時自行持有，供單獨測試）
        self.event_counts: Dict[str, int] = (
            event_counts if event_counts is not None else {"rejected_fill_price": 0}
        )

        # Tick 級別的當日累計高低點（TickQuote 沒有 OHLC，成交價驗證需自行維護）
        self.intraday_range: Dict[str, Tuple[float, float]] = {}

        # 前一交易日收盤價，作為漲跌停判定基準
        self.prev_close: Dict[str, float] = {}

    def validate(self, order: BaseOrder, quote: BaseQuote) -> bool:
        """成交價合理性檢查（前視偏誤與不可能成交的擋板）"""

        low, high = self.get_price_range(quote)
        if low is not None and high is not None and not (low <= order.price <= high):
            logger.warning(
                f"[Validate Fill] {order.symbol} 成交價 {order.price} 超出當日區間 "
                f"[{low}, {high}]，拒單"
            )
            self.event_counts["rejected_fill_price"] += 1
            return False

        prev_close: Optional[float] = self.prev_close.get(order.symbol)
        if prev_close:
            limit_down, limit_up = self.instrument.get_price_limits(prev_close)
            if not (limit_down <= order.price <= limit_up):
                logger.warning(
                    f"[Validate Fill] {order.symbol} 成交價 {order.price} 超出漲跌停 "
                    f"[{limit_down}, {limit_up}]，拒單"
                )
                self.event_counts["rejected_fill_price"] += 1
                return False

        if self.instrument.round_to_tick(order.price, "nearest") != order.price:
            logger.warning(
                f"[Validate Fill] {order.symbol} 成交價 {order.price} 未對齊檔位"
            )

        return True

    def get_price_range(
        self, quote: BaseQuote
    ) -> Tuple[Optional[float], Optional[float]]:
        """取得該報價可成交的價格區間：日 K 用 OHLC，Tick 用當日累計高低點"""

        if quote.scale == Scale.TICK:
            return self.intraday_range.get(quote.symbol, (None, None))

        if quote.high and quote.low:
            return (quote.low, quote.high)

        return (None, None)

    def on_bar_open(self, quotes: List[BaseQuote]) -> None:
        """一根 bar 開始：Tick 級別的累計高低點以該根 bar 為範圍，故先重置再累計"""

        self.intraday_range = {}
        self.update_intraday_range(quotes)

    def update_intraday_range(self, quotes: List[BaseQuote]) -> None:
        """更新 Tick 級別的當日累計高低點（只納入已發生的報價，本身即防前視）"""

        for quote in quotes:
            price: float = quote.cur_price or quote.close
            if not price:
                continue

            low, high = self.intraday_range.get(quote.symbol, (price, price))
            self.intraday_range[quote.symbol] = (min(low, price), max(high, price))

    def on_bar_close(self, quotes: List[BaseQuote]) -> None:
        """收盤後記錄當日收盤價，作為次一交易日的漲跌停基準"""

        for quote in quotes:
            close: float = quote.close or quote.cur_price
            if close:
                self.prev_close[quote.symbol] = close
