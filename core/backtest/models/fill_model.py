import copy
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

from loguru import logger

from core.backtest.models.instrument_spec import InstrumentSpec, TwStockSpec
from core.models import BaseOrder, BaseQuote
from core.utils import Action, PositionType, Scale, TimeUtils

"""
FillModel: 這張單成不成交、以什麼價量成交

包含四件事，全部屬「市場執行假設」而非引擎邏輯：
1. **成交價可信度**（`validate()`）：前視偏誤與不可能成交的擋板
2. **滑價**（`FillConfig.slippage_bps_*`）：拿不到理想價
3. **成交量上限**（`FillConfig.max_volume_share`）：一張單不可能吃掉當日大半成交量
4. **券源檢核**（`ShortConstraint.check_borrowable`）：借不到券就放空不了

2~4 三項的預設值皆為「關閉」，行為與導入前完全相同。
"""


class VolumeCapPolicy(str, Enum):
    """超過成交量上限時的處理方式"""

    TRUNCATE = "TRUNCATE"  # 縮量到上限（預設，較貼近實務）
    REJECT = "REJECT"  # 整張拒單


@dataclass
class FillConfig:
    """
    成交假設設定

    **落點與「回測滑價與執行係數」S1 的原規劃不同**（該工作已於 2026-08-15
    完成並移出 `backlog/`，使用說明見 `core/backtest/README.md`〈成交假設〉）：原規劃寫
    `core/utils/backtest_execution.py`，但多市場重構已把 `cost_model.py` 由
    `core/utils/` 搬到 `core/backtest/models/`，回測假設一律與其 model 同檔
    （`CostConfig` 之於 `CostModel`）。再放回 `core/utils/` 會與該結構相衝突，
    故改為與 `FillModel` 同檔，語意仍與「法規費率」（`Commission`）分離。

    全部預設為關閉，行為與導入前逐筆相同。
    """

    # 滑價基點（1 bps = 0.01%）；買進加價、賣出減價
    slippage_bps_buy: float = 0.0
    slippage_bps_sell: float = 0.0

    # 單筆訂單張數不得超過當日成交量的比例；None 為關閉
    max_volume_share: Optional[float] = None

    # 超量時縮量或拒單
    volume_cap_policy: VolumeCapPolicy = VolumeCapPolicy.TRUNCATE


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

    def apply_price_limit_basis(self, basis: Dict[str, float]) -> None:
        """一根 bar 開始：以交易所公告的基準價覆寫漲跌停基準；預設不處理"""

        pass

    def apply_short_balance(self, balance: Dict[str, int]) -> None:
        """一根 bar 開始：更新當日可借券餘額；預設不處理"""

        pass

    def fill(self, order: BaseOrder, quote: BaseQuote) -> Optional[BaseOrder]:
        """
        - Description:
            決定這張單成不成交、以什麼價量成交

            **與 `validate()` 的分工**：`validate()` 只回答「這個價格在當根 bar
            可不可能成交」，是既有的前視偏誤擋板；`fill()` 負責市場執行假設
            （滑價、成交量上限、券源），並在需要調整時回傳**訂單副本**。

            **絕不就地修改傳入的 order**：策略可能持有同一個物件，
            就地改動會讓策略下一根 bar 看到被引擎改過的價量。
        - Parameters:
            - order: BaseOrder
                策略產生的訂單
            - quote: BaseQuote
                同一標的的當根 bar 報價
        - Return:
            - Optional[BaseOrder]
                可成交的訂單（未調整時為原物件本身）；不可成交時為 None
        """

        return order


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
        config: Optional[FillConfig] = None,
        check_borrowable: bool = False,
    ):
        self.instrument: InstrumentSpec = instrument or TwStockSpec()

        # 成交假設（滑價、成交量上限）；預設全關
        self.config: FillConfig = config or FillConfig()

        # 是否檢核券源；由 factory 依 ShortConstraint.check_borrowable 帶入
        self.check_borrowable: bool = check_borrowable

        # 當日可借券餘額（張）：{stock_id: 融券今日餘額}，由 DataFeed 於每根 bar 開始時提供
        self.short_balance: Dict[str, int] = {}

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
            # 帶入報價日期：2015-06-01 前的漲跌停幅度為 7%，非現行的 10%
            limit_down, limit_up = self.instrument.get_price_limits(
                prev_close, TimeUtils.to_date(quote.date)
            )
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

    def apply_short_balance(self, balance: Dict[str, int]) -> None:
        """
        - Description:
            更新當日可借券餘額（融券今日餘額，單位：張）

            **空 dict 代表「今日查無融券資料」而非「所有標的都借不到券」**——
            `fill()` 在查不到餘額時一律放行並記錄，不可預設拒單。
        - Parameters:
            - balance: Dict[str, int]
                `{stock_id: 融券今日餘額}`，由 DataFeed 依當日信用交易資料提供
        """

        self.short_balance = balance

    def fill(self, order: BaseOrder, quote: BaseQuote) -> Optional[BaseOrder]:
        """
        - Description:
            台股的成交假設：券源檢核 → 滑價 → 成交量上限

            三項預設皆為關閉，此時直接回傳**原物件**（不是副本），
            確保未啟用任何假設時行為與導入前逐筆相同。
        - Parameters:
            - order: BaseOrder
                策略產生的訂單
            - quote: BaseQuote
                同一標的的當根 bar 報價
        - Return:
            - Optional[BaseOrder]
                可成交的訂單；不可成交時為 None
        """

        if not self.check_short_borrowable(order):
            return None

        price: float = self.get_filled_price(order)
        volume: Optional[int] = self.get_filled_volume(order, quote)

        if volume is None:
            return None

        if price == order.price and volume == order.volume:
            return order

        filled_order: BaseOrder = copy.copy(order)
        filled_order.price = price
        filled_order.volume = volume
        return filled_order

    def check_short_borrowable(self, order: BaseOrder) -> bool:
        """
        - Description:
            券源檢核：融券餘額不足時拒絕放空開倉

            只檢查**放空開倉**（賣出且方向為 SHORT）。放空回補是買進、
            做多賣出是 `PositionType.LONG`，兩者都不需要券源。

            **查無資料時放行**：`margin` 表可能尚未回補歷史，
            此時「查不到」不等於「借不到」。但若使用者明確開啟了檢核卻整場都查無資料，
            等於開關沒有實際作用，故以 warning 提示。
        - Parameters:
            - order: BaseOrder
                待檢核的訂單
        - Return:
            - bool
                False 時呼叫端應拒單
        """

        if not self.check_borrowable:
            return True

        is_short_open: bool = (
            order.action == Action.SELL and order.position_type == PositionType.SHORT
        )
        if not is_short_open:
            return True

        balance: Optional[int] = self.short_balance.get(order.symbol)

        if balance is None:
            logger.warning(
                f"[Fill] {order.symbol} 查無融券餘額資料，本次跳過券源檢核。"
                f"若整場回測皆如此，代表 margin 資料未涵蓋該區間，check_borrowable 形同未啟用"
            )
            return True

        if balance < order.volume:
            logger.warning(
                f"[Fill] {order.symbol} 融券餘額 {balance} 張 < 委託 {order.volume} 張，"
                f"券源不足，拒單"
            )
            self.event_counts["rejected_no_borrow"] += 1
            return False

        return True

    def get_filled_price(self, order: BaseOrder) -> float:
        """依訂單方向套用滑價；係數為 0 時原價回傳"""

        bps: float = (
            self.config.slippage_bps_buy
            if order.action == Action.BUY
            else self.config.slippage_bps_sell
        )
        return self.instrument.apply_slippage(order.price, order.action, bps)

    def get_filled_volume(self, order: BaseOrder, quote: BaseQuote) -> Optional[int]:
        """
        - Description:
            套用成交量上限：單筆訂單張數不得超過當日成交量的指定比例

            **`quote.volume` 的語意依級別不同**：DAY 為當日總量、TICK 為單筆成交量。
            TICK 級別下以單筆量當分母沒有意義，故本檢查只在 DAY 級別生效
            （TICK 的累計量檢查尚未實作，見 `core/backtest/README.md`
            〈成交假設〉的已知限制）。
        - Parameters:
            - order: BaseOrder
                待檢查的訂單
            - quote: BaseQuote
                同一標的的當根 bar 報價
        - Return:
            - Optional[int]
                可成交張數；整張拒單時為 None
        """

        share: Optional[float] = self.config.max_volume_share

        if not share or quote.scale != Scale.DAY or not quote.volume:
            return order.volume

        cap: int = int(quote.volume * share)

        if order.volume <= cap:
            return order.volume

        if self.config.volume_cap_policy == VolumeCapPolicy.REJECT:
            logger.warning(
                f"[Fill] {order.symbol} 委託 {order.volume} 張 > 當日成交量上限 "
                f"{cap} 張（{share:.1%} × {quote.volume}），拒單"
            )
            self.event_counts["rejected_volume_cap"] += 1
            return None

        if cap <= 0:
            logger.warning(
                f"[Fill] {order.symbol} 當日成交量上限不足一張（{share:.1%} × "
                f"{quote.volume}），拒單"
            )
            self.event_counts["rejected_volume_cap"] += 1
            return None

        logger.warning(
            f"[Fill] {order.symbol} 委託 {order.volume} 張縮量至 {cap} 張"
            f"（當日成交量 {quote.volume} 張的 {share:.1%}）"
        )
        self.event_counts["truncated_by_volume"] += 1
        return cap

    def apply_price_limit_basis(self, basis: Dict[str, float]) -> None:
        """
        - Description:
            以交易所公告的開盤競價基準覆寫當日的漲跌停基準

            除權息日的漲跌停不是以前一交易日收盤計算，而是以除權息參考價換算的
            **開盤競價基準**。沿用前收會讓整段區間偏移——除息日前收偏高，
            上下界一起偏高，`validate()` 的第二道檢查因此失準。

            **只覆寫有公告的標的**，其餘維持 `on_bar_close()` 累積的前收盤價。
        - Parameters:
            - basis: Dict[str, float]
                `{stock_id: 開盤競價基準}`，由 DataFeed 依當日除權息公告提供
        """

        for symbol, price in basis.items():
            if price:
                self.prev_close[symbol] = price
