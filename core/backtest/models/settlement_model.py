import datetime
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from loguru import logger

from core.backtest.models.cost_model import StockCostModel
from core.backtest.models.instrument_spec import InstrumentSpec, TwStockSpec
from core.managers.stock.position_manager import StockPositionManager
from core.models import (
    BaseAccount,
    BasePosition,
    BaseQuote,
    StockOrder,
    StockPosition,
    StockQuote,
    StockTradeRecord,
)
from core.utils import (
    Action,
    DayTradeUncoveredPolicy,
    MarginCallPolicy,
    PositionType,
    ShortMethod,
    TimeUtils,
)

"""SettlementModel: 一根 bar 收盤後由市場規則強制執行的動作"""


class BaseSettlementModel(ABC):
    """
    結算模型：一根 bar 收盤後，市場規則強制對部位做的事

    這是本次重構的關鍵抽象——台股的「當沖日終強制回補」與期貨的「每日結算」
    在架構上是同一個掛點的兩種實作，看出這點之後就不需要兩個引擎。
    對應 Lean 的 SettlementModel / MarginCallModel / MarginInterestRateModel。
    """

    @abstractmethod
    def on_bar_close(
        self,
        date: datetime.date,
        quotes: List[BaseQuote],
        account: BaseAccount,
        event_counts: Dict[str, int],
    ) -> None:
        """
        - Description:
            一根 bar 收盤後由市場規則強制執行的動作
        - Parameters:
            - date: datetime.date
                當前交易日
            - quotes: List[BaseQuote]
                當根 bar 的報價
            - account: BaseAccount
                交易帳戶
            - event_counts: Dict[str, int]
                事件計數（key 需與報表相容）
        """
        pass

    @abstractmethod
    def update_no_quote_days(
        self,
        quote_map: Dict[str, StockQuote],
        positions: List[StockPosition],
    ) -> None:
        """
        - Description:
            更新每個部位的連續無報價天數

            有報價即歸零，無報價則累加。長期停牌或已下市的標的會持續累加，
            成為 `check_no_quote_exit()` 的出場依據。
        - Parameters:
            - quote_map: Dict[str, StockQuote]
                當日報價對照表
            - positions: List[StockPosition]
                要更新的部位
        """

        for position in positions:
            quote: Optional[StockQuote] = quote_map.get(position.symbol)
            if quote is not None and (quote.close or quote.cur_price):
                position.no_quote_days = 0
            else:
                position.no_quote_days += 1

    def get_mark_price(
        self, position: BasePosition, quote_map: Dict[str, BaseQuote]
    ) -> float:
        """
        - Description:
            取得部位的盯市價格

            屬結算職責而非成交價職責：期貨的盯市價就是每日結算價。
            引擎的 snapshot_daily_equity() 也用這個價算未實現損益，故列入介面。
        - Parameters:
            - position: BasePosition
                待盯市的部位
            - quote_map: Dict[str, BaseQuote]
                當根 bar 的報價（以 symbol 為鍵）
        - Return:
            - float
                盯市價格
        """
        pass


class TwStockSettlementModel(BaseSettlementModel):
    """
    台股結算模型：當沖日終強制回補、借券費逐日計提、維持率追繳

    執行順序固定為「當沖回補 → 每日部位檢查」，不可對調：對調會讓同一次強制回補
    記到不同的事件桶。
    """

    def __init__(
        self,
        position_manager: StockPositionManager,
        cost_model: StockCostModel,
        prev_close: Dict[str, float],
        instrument: Optional[InstrumentSpec] = None,
        day_trade_uncovered_policy: DayTradeUncoveredPolicy = (
            DayTradeUncoveredPolicy.FORCE_COVER_AT_CLOSE
        ),
        margin_call_policy: MarginCallPolicy = MarginCallPolicy.FORCE_COVER,
        max_holding_days: Optional[int] = None,
        max_no_quote_days: Optional[int] = None,
    ):
        self.position_manager: StockPositionManager = position_manager
        self.cost_model: StockCostModel = cost_model
        self.instrument: InstrumentSpec = instrument or TwStockSpec()

        # 與 FillModel 共用同一個 dict：停牌盯市與漲停判定都要用前收，
        # 但「記錄前收」屬成交價模型的職責，故此處只持有參照，不自行維護
        self.prev_close: Dict[str, float] = prev_close

        # 策略宣告的處理政策，由 factory 從策略帶入
        self.day_trade_uncovered_policy: DayTradeUncoveredPolicy = (
            day_trade_uncovered_policy
        )
        self.margin_call_policy: MarginCallPolicy = margin_call_policy
        self.max_holding_days: Optional[int] = max_holding_days
        self.max_no_quote_days: Optional[int] = max_no_quote_days

    def on_bar_close(
        self,
        date: datetime.date,
        quotes: List[StockQuote],
        account: BaseAccount,
        event_counts: Dict[str, int],
    ) -> None:
        """當沖日終回補 → 留倉部位的借券費計提與維持率檢查（順序不可對調）"""

        self.enforce_day_trade_cover(date, quotes, account, event_counts)
        self.execute_daily_position_check(date, quotes, account, event_counts)

    def enforce_day_trade_cover(
        self,
        date: datetime.date,
        stock_quotes: List[StockQuote],
        account: BaseAccount,
        event_counts: Dict[str, int],
    ) -> None:
        """
        - Description:
            當沖放空於日終仍未回補時的處理

            現行引擎不會自己發現這件事，若放著不管，回測會出現實務上不存在的
            「當沖單留倉」；因此一律依 day_trade_uncovered_policy 明確處理並計數。
        - Parameters:
            - date: datetime.date
                當前交易日
            - stock_quotes: List[StockQuote]
                當日報價
            - account: BaseAccount
                交易帳戶
            - event_counts: Dict[str, int]
                事件計數
        """

        quote_map: Dict[str, StockQuote] = {sq.symbol: sq for sq in stock_quotes}
        policy: DayTradeUncoveredPolicy = self.day_trade_uncovered_policy

        for position in account.get_positions(position_type=PositionType.SHORT):
            if not position.is_day_trade:
                continue

            quote: Optional[StockQuote] = quote_map.get(position.symbol)
            if quote is None:
                logger.warning(
                    f"[Day Trade Cover] {position.symbol} 當日無報價，無法強制回補"
                )
                continue

            # 漲停鎖死無法回補：轉為融券留倉，並單獨計數（放空最致命的尾部風險）
            if self.check_limit_up_locked(quote):
                logger.warning(
                    f"[Day Trade Cover] {position.symbol} 全日鎖漲停無法回補，轉為融券留倉"
                )
                event_counts["limit_up_cover_failed"] += 1
                self.convert_to_margin_position(position, account)
                continue

            if policy == DayTradeUncoveredPolicy.RAISE:
                raise ValueError(
                    f"[Day Trade Cover] {position.symbol} 當沖放空於 {date} 日終未回補"
                )

            if policy == DayTradeUncoveredPolicy.CONVERT_TO_MARGIN:
                logger.warning(
                    f"[Day Trade Cover] {position.symbol} 未回補，依政策轉為融券留倉"
                )
                self.convert_to_margin_position(position, account)
                continue

            logger.warning(
                f"[Day Trade Cover] {position.symbol} 未回補，以收盤價 {quote.close} 強制回補"
            )
            event_counts["forced_cover_day_trade"] += 1
            self.force_cover_position(position, date, quote.close)

    def check_limit_up_locked(self, quote: StockQuote) -> bool:
        """判定是否全日鎖漲停（開高低收皆等於漲停價），此時放空無法回補"""

        prev_close: Optional[float] = self.prev_close.get(quote.symbol)
        if not prev_close:
            return False

        # 帶入報價日期：2015-06-01 前的漲跌停幅度為 7%，非現行的 10%
        _, limit_up = self.instrument.get_price_limits(
            prev_close, TimeUtils.to_date(quote.date)
        )
        return (
            quote.close == limit_up and quote.high == limit_up and quote.low == limit_up
        )

    def convert_to_margin_position(
        self, position: StockPosition, account: BaseAccount
    ) -> None:
        """
        - Description:
            將無法當日回補的當沖空單轉為融券留倉

            補收三項：保證金、融券手續費，以及**證交稅差額**。

            稅差額不可漏收：開倉當下該筆賣出是以現股當沖的減半稅率課稅，
            一旦轉為留倉，這筆賣出在現實中就不是當沖，應適用全額稅率。
            漏收會讓「漲停鎖死轉留倉」這種放空最痛的情境成本被系統性低估——
            低估恰好發生在最不該樂觀的地方。
        - Parameters:
            - position: StockPosition
                要轉為留倉的當沖空單
            - account: BaseAccount
                虛擬帳戶
        """

        margin: int = self.cost_model.margin_required(
            price=position.price,
            volume=position.volume,
            short_method=ShortMethod.MARGIN,
        )
        borrow_fee: int = self.cost_model.borrow_fee(
            price=position.price,
            volume=position.volume,
            short_method=ShortMethod.MARGIN,
        )
        tax_diff: int = self.get_day_trade_tax_top_up(position)

        position.is_day_trade = False
        position.short_method = ShortMethod.MARGIN
        position.margin += margin
        position.borrow_fee += borrow_fee
        position.tax += tax_diff
        position.transaction_cost += borrow_fee + tax_diff

        account.balance -= margin + borrow_fee + tax_diff
        account.margin_used += margin

    def get_day_trade_tax_top_up(self, position: StockPosition) -> int:
        """
        - Description:
            計算當沖轉留倉時應補徵的證交稅差額

            稅率一律取自 `CostConfig`，**不寫死 0.3% 與 0.15%**——落日條款或費率
            調整時只需改設定，不必回頭找散落在各處的字面值。
        - Parameters:
            - position: StockPosition
                轉換前的當沖空單
        - Return:
            - int
                應補徵的稅額（全額稅 − 已收的當沖減半稅）
        """

        full_tax: int = self.cost_model.tax(
            price=position.price,
            volume=position.volume,
            action=Action.SELL,
            is_day_trade=False,
        )
        day_trade_tax: int = self.cost_model.tax(
            price=position.price,
            volume=position.volume,
            action=Action.SELL,
            is_day_trade=True,
        )
        return max(0, full_tax - day_trade_tax)

    def force_cover_position(
        self,
        position: StockPosition,
        date: datetime.date,
        price: float,
    ) -> List[StockTradeRecord]:
        """以指定價格強制回補放空部位（當沖日終、維持率追繳、超過持有天數共用）"""

        order: StockOrder = StockOrder(
            stock_id=position.symbol,
            date=date,
            action=Action.BUY,
            position_type=PositionType.SHORT,
            price=price,
            volume=position.volume,
            short_method=position.short_method,
            is_day_trade=position.is_day_trade,
        )
        return self.position_manager.close_position(order)

    def execute_daily_position_check(
        self,
        date: datetime.date,
        stock_quotes: List[StockQuote],
        account: BaseAccount,
        event_counts: Dict[str, int],
    ) -> None:
        """
        - Description:
            每日收盤後對未平倉放空部位的檢查（做多部位直接略過）
        - Parameters:
            - date: datetime.date
                當前交易日
            - stock_quotes: List[StockQuote]
                當日報價；停牌無報價時沿用前一交易日收盤價
            - account: BaseAccount
                交易帳戶
            - event_counts: Dict[str, int]
                事件計數
        """

        short_positions: List[StockPosition] = account.get_positions(
            position_type=PositionType.SHORT
        )
        if not short_positions:
            return

        quote_map: Dict[str, StockQuote] = {sq.symbol: sq for sq in stock_quotes}

        self.update_no_quote_days(quote_map, short_positions)
        self.accrue_holding_cost(date, quote_map, account)
        self.check_margin_call(date, quote_map, account, event_counts)

    def accrue_holding_cost(
        self,
        date: datetime.date,
        quote_map: Dict[str, StockQuote],
        account: BaseAccount,
    ) -> None:
        """
        - Description:
            逐日計提持有成本並更新持有天數

            只有 SBL 借券費在此逐日累加；MARGIN 的融券手續費在開倉時一次收取、
            融券利息於平倉時依日期差一次計算，
            在此重複計算會造成雙重計費。
        """

        for position in account.get_positions(position_type=PositionType.SHORT):
            position.holding_days += 1

            if position.short_method != ShortMethod.SBL:
                continue

            price: float = self.get_mark_price(position, quote_map)
            position.accrued_borrow_fee += self.cost_model.borrow_fee(
                price=price,
                volume=position.volume,
                holding_days=1,
                short_method=ShortMethod.SBL,
            )

    def check_margin_call(
        self,
        date: datetime.date,
        quote_map: Dict[str, StockQuote],
        account: BaseAccount,
        event_counts: Dict[str, int],
    ) -> None:
        """
        - Description:
            維持率追繳與強制回補檢查

            現行引擎沒有跨日的委託佇列，無法模擬「次一交易日開盤成交」，
            因此一律以觸發當日收盤價立即回補。
        """

        for position in list(account.get_positions(position_type=PositionType.SHORT)):
            price: float = self.get_mark_price(position, quote_map)

            # 連續無報價（停牌／下市）：強制出場
            #
            # 出場價採「最後可得價格」而非歸零：下市清算實務上多為部分償還，
            # 回測無法精確模擬，歸零會系統性高估放空獲利。保守估計者可另行
            # 以報表的本事件計數自行調整。
            if (
                self.max_no_quote_days is not None
                and position.no_quote_days >= self.max_no_quote_days
            ):
                logger.warning(
                    f"[Force Cover] {position.symbol} 連續 {position.no_quote_days} 日"
                    f"無報價（停牌／下市），以最後可得價格 {price} 強制出場"
                )
                event_counts["forced_cover_no_quote"] += 1
                self.force_cover_position(position, date, price)
                continue

            # 超過最長持有天數：強制回補
            if (
                self.max_holding_days is not None
                and position.holding_days >= self.max_holding_days
            ):
                logger.warning(
                    f"[Force Cover] {position.symbol} 持有 {position.holding_days} 天"
                    f"已達上限，以 {price} 強制回補"
                )
                event_counts["forced_cover_max_holding"] += 1
                self.force_cover_position(position, date, price)
                continue

            # 停券強制回補日
            force_cover_dates: List[datetime.date] = (
                self.cost_model.config.short_constraint.get_force_cover_dates(
                    position.symbol
                )
            )
            if date in force_cover_dates:
                logger.warning(
                    f"[Force Cover] {position.symbol} 於 {date} 停券，以 {price} 強制回補"
                )
                # 停券與持有天數到期是兩種成因，記到同一個桶會讓「策略設定的持有上限
                # 太短」與「標的停券」無法區分，兩者的因應方式完全不同
                event_counts["forced_cover_suspended"] += 1
                self.force_cover_position(position, date, price)
                continue

            # 維持率追繳
            if position.short_method != ShortMethod.MARGIN:
                continue

            if not self.cost_model.check_margin_call(
                proceeds=position.short_proceeds,
                margin=position.margin,
                cur_price=price,
                volume=position.volume,
            ):
                continue

            if self.margin_call_policy == MarginCallPolicy.WARN_ONLY:
                logger.warning(
                    f"[Margin Call] {position.symbol} 維持率已低於門檻（僅記錄不回補）"
                )
                continue

            logger.warning(
                f"[Margin Call] {position.symbol} 維持率不足，以 {price} 強制回補（斷頭）"
            )
            event_counts["forced_cover_margin_call"] += 1
            self.force_cover_position(position, date, price)

    def update_no_quote_days(
        self,
        quote_map: Dict[str, StockQuote],
        positions: List[StockPosition],
    ) -> None:
        """
        - Description:
            更新每個部位的連續無報價天數

            有報價即歸零，無報價則累加。長期停牌或已下市的標的會持續累加，
            成為 `check_no_quote_exit()` 的出場依據。
        - Parameters:
            - quote_map: Dict[str, StockQuote]
                當日報價對照表
            - positions: List[StockPosition]
                要更新的部位
        """

        for position in positions:
            quote: Optional[StockQuote] = quote_map.get(position.symbol)
            if quote is not None and (quote.close or quote.cur_price):
                position.no_quote_days = 0
            else:
                position.no_quote_days += 1

    def get_mark_price(
        self, position: StockPosition, quote_map: Dict[str, StockQuote]
    ) -> float:
        """取得盯市價格：優先用當日收盤，停牌時沿用前收，再無資料則退回開倉價"""

        quote: Optional[StockQuote] = quote_map.get(position.symbol)
        if quote is not None and (quote.close or quote.cur_price):
            return quote.close or quote.cur_price

        logger.warning(
            f"[Mark Price] {position.symbol} 當日無報價，沿用前一交易日收盤價盯市"
        )
        return self.prev_close.get(position.symbol, position.price)
