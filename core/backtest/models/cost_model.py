import datetime
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from loguru import logger

from core.models import BaseOrder, StockOrder
from core.utils import (
    DAY_TRADE_TAX_EXPIRY,
    DAYS_PER_YEAR,
    Action,
    Commission,
    FuturesCost,
    MarginCost,
    PositionType,
    ShortCost,
    ShortMethod,
)
from core.utils.instrument import StockUtils

"""
成本模型：手續費／稅／借券費／保證金／損益口徑

- BaseCostModel：各市場共用的介面（對應 Lean 的 FeeModel）
- ShortConstraint / CostConfig / StockCostModel：台股實作，含信用交易

自 core/utils/ 移入：它是回測領域的核心，
與 log_manager、decorators 這類通用工具混在一起會讓 core/utils/ 變成雜物櫃。
"""


class BaseCostModel(ABC):
    """
    成本模型的共用介面

    必要方法為每個市場都有的四項：手續費、稅、已實現損益、報酬率。
    放空專屬的借券費、保證金與利息給預設 `0` 實作——期貨的保證金語意與
    台股融券不同，屆時由期貨實作自行覆寫，不必為此再拆一層介面。
    對應 Lean 的 FeeModel。
    """

    @abstractmethod
    def commission(self, price: float, volume: int) -> int:
        """手續費"""
        pass

    @abstractmethod
    def tax(self, price: float, volume: int, **kwargs) -> int:
        """交易稅（台股為證交稅、期貨為期交稅）"""
        pass

    @abstractmethod
    def realized_pnl(self, **kwargs) -> float:
        """已實現損益"""
        pass

    @abstractmethod
    def roi(self, **kwargs) -> float:
        """名目報酬率（%）"""
        pass

    @abstractmethod
    def roi_on_capital(self, **kwargs) -> float:
        """資金效率報酬率（%）"""
        pass

    def borrow_fee(self, **kwargs) -> int:
        """借券費；無此制度的市場維持 0"""
        return 0

    def margin_required(self, **kwargs) -> int:
        """開倉所需保證金；無保證金制度的市場維持 0"""
        return 0

    def short_interest(self, **kwargs) -> int:
        """放空擔保品的利息收入；無此制度的市場維持 0"""
        return 0

    def enrich_orders(self, orders: List[BaseOrder]) -> List[BaseOrder]:
        """
        - Description:
            依成本設定補上市場專屬的訂單欄位，策略不需自行填寫

            預設為不補值；有信用交易制度的市場自行覆寫。
        - Parameters:
            - orders: List[BaseOrder]
                策略回傳的訂單
        - Return:
            - List[BaseOrder]
                補值後的訂單
        """

        return orders

    @staticmethod
    def is_short(order: BaseOrder) -> bool:
        """訂單是否為放空方向（補值與成本路徑一律看每一張 order 的方向）"""

        return order.position_type == PositionType.SHORT


@dataclass
class ShortConstraint:
    """
    放空的可成交限制；全部可選，未提供資料時該項檢查自動跳過

    **兩個欄位目前有定義、無呼叫端**（`allow_below_reference`、`day_trade_whitelist`）。
    設了限制卻不生效比功能沒做更危險，故由 `StockCostModel` 在建構時逐一檢查並發出警告，
    見 `check_unimplemented_constraints()`。

    `check_borrowable` 則已接上呼叫端（`TwStockFillModel.check_short_borrowable()`），
    `force_cover_dates` 與 `auto_force_cover_on_ex_dividend` 接上
    `TwStockSettlementModel.check_force_cover()`。
    """

    allow_below_reference: bool = True  # 是否允許平盤下放空（**尚未實作**）
    day_trade_whitelist: Optional[Dict[datetime.date, Set[str]]] = (
        None  # 每日可當沖清單（**尚未實作**）
    )
    check_borrowable: bool = False  # 是否檢核券源（由 FillModel 依融券今日餘額檢核）
    force_cover_dates: Optional[Dict[str, List[datetime.date]]] = None  # 停券強制回補日
    # 是否由除權息行事曆自動推導融券最後回補日（**預設開啟**：這是融券制度的規則，
    # 不是可選功能；關掉等於回到「留倉放空不受停券影響」的高估假設）
    auto_force_cover_on_ex_dividend: bool = True
    max_short_exposure_ratio: Optional[float] = (
        None  # 單一空單曝險上限（佔初始本金比例）
    )

    def check_day_tradable(self, stock_id: str, date: datetime.date) -> bool:
        """
        檢查該股票當日是否可當沖；未提供清單時一律視為可當沖

        **目前未被任何路徑呼叫**：引擎的下單流程不會走到這裡，設定
        `day_trade_whitelist` 不會影響任何回測結果。接上呼叫端前不要
        以為它已生效。
        """

        if self.day_trade_whitelist is None:
            return True

        return stock_id in self.day_trade_whitelist.get(date, set())

    def get_force_cover_dates(self, stock_id: str) -> List[datetime.date]:
        """
        取得使用者**手動指定**的強制回補日

        由除權息行事曆自動推導的融券最後回補日不在此列，兩者的適用範圍不同
        （見 `TwStockSettlementModel.check_force_cover()`）
        """

        if self.force_cover_dates is None:
            return []

        return self.force_cover_dates.get(stock_id, [])


@dataclass
class CostConfig:
    """一次回測固定的成本參數；由策略提供或使用 default() 的市場常見值"""

    # 手續費
    comm_rate: float = float(Commission.CommRate)
    comm_discount: float = float(Commission.Discount)
    min_fee: int = int(Commission.MinFee)

    # 證交稅
    tax_rate: float = float(Commission.TaxRate)
    day_trade_tax_rate: float = float(Commission.DayTradeTaxRate)

    # 放空管道與其成本
    short_method: ShortMethod = ShortMethod.MARGIN
    is_day_trade: bool = False
    margin_rate: float = float(ShortCost.MarginRate)
    borrow_fee_rate: float = float(
        ShortCost.MarginBorrowFeeRate
    )  # MARGIN 一次性／SBL 年化
    interest_rate: float = float(ShortCost.MarginInterestRate)
    maintenance_ratio: float = float(ShortCost.MaintenanceRatio)

    # 融資（做多槓桿）：本階段僅保留參數不啟用
    financing_rate: float = float(MarginCost.FinancingRate)

    days_per_year: int = DAYS_PER_YEAR

    # 除息日是否對留倉空單扣股利補償（**預設開啟**：放空者補償出借方當期現金股利
    # 是實際發生的現金流，不計會系統性高估長天期放空的績效）
    compensate_cash_dividend: bool = True

    # 可成交限制
    short_constraint: ShortConstraint = field(default_factory=ShortConstraint)

    @classmethod
    def default(
        cls,
        short_method: ShortMethod = ShortMethod.MARGIN,
        is_day_trade: bool = False,
    ) -> "CostConfig":
        """依放空管道與是否當沖，組出市場常見值的成本設定"""

        # 當沖一律走現股當沖沖賣。
        # 費率不可歸零：當沖單漲停無法回補時會轉為融券留倉，
        # 屆時仍需以正常的保證金成數與券費率計算，歸零會讓維持率永遠不足而誤觸斷頭。
        if is_day_trade:
            return cls(short_method=ShortMethod.DAY_TRADE, is_day_trade=True)

        if short_method == ShortMethod.SBL:
            return cls(
                short_method=ShortMethod.SBL,
                is_day_trade=False,
                borrow_fee_rate=float(ShortCost.SBLFeeRate),
                interest_rate=0.0,
            )

        return cls(short_method=short_method, is_day_trade=is_day_trade)


class StockCostModel(BaseCostModel):
    """
    方向感知的成本／損益計算；PositionManager 與 Backtester 只呼叫這一層

    取整規則：
    - 費用（手續費／稅／券費／利息）一律無條件捨去，與既有 LONG 路徑一致
    - 保證金無條件進位（佔用資金進位較保守）
    - 損益與報酬率 round 至小數點後 2 位
    """

    # 尚未接上呼叫端的 ShortConstraint 欄位：{欄位名: (預設值, 未實作的原因)}
    # 檢查放在建構時，任何建立路徑（factory、測試、未來的實盤）都會經過
    UNIMPLEMENTED_CONSTRAINTS: Dict[str, Tuple[Any, str]] = {
        "allow_below_reference": (
            True,
            "平盤下放空限制需要警示／處置股清單，尚無資料源",
        ),
        "day_trade_whitelist": (None, "每日可當沖清單需要證交所每日公告，尚無資料源"),
    }

    def __init__(self, config: Optional[CostConfig] = None):
        self.config: CostConfig = config or CostConfig.default()

        self.check_day_trade_tax_expiry()
        self.check_unimplemented_constraints()

    def check_unimplemented_constraints(self) -> None:
        """
        - Description:
            檢查「設了限制卻不生效」的 ShortConstraint 欄位

            這些欄位有定義、無呼叫端。使用者設了限制卻完全不生效、也收不到
            任何提示，會讓回測結果被誤讀為「已考慮該限制」——這比功能沒做更
            危險，直接違反放空框架設計原則的「不可靜默失敗」。

            取捨：一律 `warning` 而非 `raise`，避免既有已設定這些欄位的策略
            直接壞掉。

            **`check_borrowable` 已於 2026-08-15 移出本清單**：券源檢核已接上
            `TwStockFillModel.check_short_borrowable()`，設為 `True` 會實際生效。
            但其資料來源 `margin` 表的歷史回補是獨立作業，若該表為空，
            `FillModel` 會在每次檢核時 warning 提示「查無資料，本次跳過」。
        """

        constraint: Optional[ShortConstraint] = self.config.short_constraint
        if constraint is None:
            return

        for field_name, (
            default_value,
            reason,
        ) in self.UNIMPLEMENTED_CONSTRAINTS.items():
            if getattr(constraint, field_name) != default_value:
                logger.warning(
                    f"[CostModel] ShortConstraint.{field_name} 尚未實作，"
                    f"本次回測不會生效（{reason}）"
                )

    def check_day_trade_tax_expiry(self) -> None:
        """當沖證交稅減半有落日期限，超過即提醒稅率假設可能失效"""

        if self.config.is_day_trade and datetime.date.today() > DAY_TRADE_TAX_EXPIRY:
            logger.warning(
                f"[CostModel] 現股當沖證交稅減半優惠已於 {DAY_TRADE_TAX_EXPIRY} 到期，"
                f"目前仍以 {self.config.day_trade_tax_rate} 計算，請確認現行法規"
            )

    # === 單邊成本 ===
    def enrich_orders(self, orders: List[StockOrder]) -> List[StockOrder]:
        """依成本設定補上放空管道與當沖旗標，策略不需自行填寫"""

        for order in orders:
            if not self.is_short(order):
                continue

            if order.short_method is None:
                order.short_method = self.config.short_method
            if not order.is_day_trade:
                order.is_day_trade = self.config.is_day_trade

        return orders

    def commission(self, price: float, volume: int) -> int:
        """
        - Description: 計算單邊手續費（買賣方向無關，費率相同）
        - Parameters:
            - price: float
                成交價格
            - volume: int
                成交張數（Unit: Lots）
        - Return:
            - commission: int
                手續費
        """

        shares: int = StockUtils.convert_lot_to_share(volume)
        return max(
            self.config.min_fee,
            int(price * shares * self.config.comm_rate * self.config.comm_discount),
        )

    def tax(
        self,
        price: float,
        volume: int,
        action: Action,
        is_day_trade: Optional[bool] = None,
    ) -> int:
        """
        - Description: 計算證交稅；買進恆為 0，賣出依是否當沖選用減半稅率
        - Parameters:
            - price: float
                成交價格
            - volume: int
                成交張數（Unit: Lots）
            - action: Action
                訂單動作（買進不課稅）
            - is_day_trade: Optional[bool]
                是否為現股當沖；None 時取用 config 的設定
        - Return:
            - tax: int
                證交稅
        """

        if action != Action.SELL:
            return 0

        day_trade: bool = (
            self.config.is_day_trade if is_day_trade is None else is_day_trade
        )
        tax_rate: float = (
            self.config.day_trade_tax_rate if day_trade else self.config.tax_rate
        )
        shares: int = StockUtils.convert_lot_to_share(volume)
        return max(1, int(price * shares * tax_rate))

    # === 放空專屬 ===
    def borrow_fee(
        self,
        price: float,
        volume: int,
        holding_days: int = 0,
        short_method: Optional[ShortMethod] = None,
    ) -> int:
        """
        - Description: 計算借券成本
        - Parameters:
            - price: float
                MARGIN 用開倉賣出價；SBL 用計費當日收盤價
            - volume: int
                張數（Unit: Lots）
            - holding_days: int
                持有曆日數（僅 SBL 使用）
            - short_method: Optional[ShortMethod]
                放空管道；None 時取用 config 的設定
        - Return:
            - borrow_fee: int
                借券費用
        - Notes:
            - MARGIN：融券手續費 0.08%，開倉時一次收取，與持有天數無關
            - SBL：年化費率按日計提，由 accrue_holding_cost() 逐日累加
            - DAY_TRADE：無借券成本
        """

        method: ShortMethod = short_method or self.config.short_method
        shares: int = StockUtils.convert_lot_to_share(volume)

        if method == ShortMethod.DAY_TRADE:
            return 0

        if method == ShortMethod.MARGIN:
            return int(price * shares * self.config.borrow_fee_rate)

        return int(
            price
            * shares
            * self.config.borrow_fee_rate
            * holding_days
            / self.config.days_per_year
        )

    def margin_required(
        self,
        price: float,
        volume: int,
        short_method: Optional[ShortMethod] = None,
    ) -> int:
        """
        - Description: 計算放空所需保證金（無條件進位）
        - Parameters:
            - price: float
                開倉賣出價
            - volume: int
                張數（Unit: Lots）
            - short_method: Optional[ShortMethod]
                放空管道；None 時取用 config 的設定
        - Return:
            - margin: int
                應繳保證金；當沖為 0
        """

        method: ShortMethod = short_method or self.config.short_method

        if method == ShortMethod.DAY_TRADE:
            return 0

        shares: int = StockUtils.convert_lot_to_share(volume)

        # 先消去浮點誤差再進位，避免 33.33 × 1000 × 0.9 這類尾數造成多進一元
        return math.ceil(round(price * shares * self.config.margin_rate, 6))

    def short_interest(
        self,
        proceeds: float,
        margin: float,
        holding_days: int,
        short_method: Optional[ShortMethod] = None,
    ) -> int:
        """
        - Description: 計算融券保證金利息（券商付給客戶，為收入）
        - Parameters:
            - proceeds: float
                融券賣出擔保價款
            - margin: float
                保證金
            - holding_days: int
                持有曆日數
        - Return:
            - interest: int
                利息收入；DAY_TRADE 與 SBL 為 0
        """

        method: ShortMethod = short_method or self.config.short_method

        if method != ShortMethod.MARGIN:
            return 0

        return int(
            (proceeds + margin)
            * self.config.interest_rate
            * holding_days
            / self.config.days_per_year
        )

    def maintenance_ratio(
        self,
        proceeds: float,
        margin: float,
        cur_price: float,
        volume: int,
    ) -> float:
        """
        - Description: 計算融券維持率 =（擔保價款 + 保證金）/ 目前市值
        - Parameters:
            - proceeds: float
                融券賣出擔保價款
            - margin: float
                保證金
            - cur_price: float
                目前股價
            - volume: int
                張數（Unit: Lots）
        - Return:
            - ratio: float
                維持率；市值為 0 時回傳無限大（視為安全）
        """

        market_value: float = cur_price * StockUtils.convert_lot_to_share(volume)
        if market_value <= 0:
            return float("inf")

        return (proceeds + margin) / market_value

    def check_margin_call(
        self,
        proceeds: float,
        margin: float,
        cur_price: float,
        volume: int,
    ) -> bool:
        """檢查是否已跌破維持率門檻（需追繳／斷頭）"""

        return (
            self.maintenance_ratio(proceeds, margin, cur_price, volume)
            < self.config.maintenance_ratio
        )

    # === 損益（方向統一入口）===
    def realized_pnl(
        self,
        position_type: PositionType,
        entry_price: float,
        exit_price: float,
        volume: int,
        entry_cost: int = 0,
        exit_cost: int = 0,
        carry_cost: int = 0,
    ) -> float:
        """
        - Description: 計算已實現損益（多空統一入口）
        - Parameters:
            - position_type: PositionType
                部位方向
            - entry_price: float
                開倉價（LONG 為買進價、SHORT 為放空賣出價）
            - exit_price: float
                平倉價（LONG 為賣出價、SHORT 為回補買進價）
            - volume: int
                張數（Unit: Lots）
            - entry_cost: int
                開倉成本（手續費 + 稅 + 一次性券費）
            - exit_cost: int
                平倉成本（手續費 + 稅）
            - carry_cost: int
                持有期間淨成本（券費支出 − 利息收入），可為負值
        - Return:
            - pnl: float
                已實現損益
        """

        shares: int = StockUtils.convert_lot_to_share(volume)

        # SHORT 為先賣後買，價差方向與 LONG 相反
        if position_type == PositionType.SHORT:
            gross: float = (entry_price - exit_price) * shares
        else:
            gross = (exit_price - entry_price) * shares

        return round(gross - entry_cost - exit_cost - carry_cost, 2)

    def roi(
        self,
        position_type: PositionType,
        entry_price: float,
        exit_price: float,
        volume: int,
        entry_cost: int = 0,
        exit_cost: int = 0,
        carry_cost: int = 0,
    ) -> float:
        """
        - Description: 名目報酬率（%），分母一律為「開倉價金 + 開倉成本」
        - Return:
            - roi: float
                報酬率（%）
        - Notes:
            多空、當沖與留倉共用同一基準，analyzer 的所有聚合統計都應使用本值
        """

        shares: int = StockUtils.convert_lot_to_share(volume)
        notional: float = entry_price * shares + entry_cost
        if notional <= 0:
            return 0.0

        pnl: float = self.realized_pnl(
            position_type=position_type,
            entry_price=entry_price,
            exit_price=exit_price,
            volume=volume,
            entry_cost=entry_cost,
            exit_cost=exit_cost,
            carry_cost=carry_cost,
        )
        return round(pnl / notional * 100, 2)

    def roi_on_capital(
        self,
        position_type: PositionType,
        entry_price: float,
        exit_price: float,
        volume: int,
        entry_cost: int = 0,
        exit_cost: int = 0,
        carry_cost: int = 0,
        margin: float = 0.0,
    ) -> float:
        """
        - Description: 資金效率（%），分母為實際佔用的資金
        - Notes:
            LONG = 買進價金 + 手續費；SHORT/MARGIN = 保證金 + 開倉成本；
            SHORT/DAY_TRADE = 開倉成本（幾乎不佔資金，數值會很大，僅供參考）
        """

        shares: int = StockUtils.convert_lot_to_share(volume)

        if position_type == PositionType.SHORT:
            capital: float = margin + entry_cost
        else:
            capital = entry_price * shares + entry_cost

        if capital <= 0:
            return 0.0

        pnl: float = self.realized_pnl(
            position_type=position_type,
            entry_price=entry_price,
            exit_price=exit_price,
            volume=volume,
            entry_cost=entry_cost,
            exit_cost=exit_cost,
            carry_cost=carry_cost,
        )
        return round(pnl / capital * 100, 2)


@dataclass
class FuturesCostConfig:
    """
    台期貨交易成本設定

    **與股票的 `CostConfig` 沒有一個欄位可以共用**（Phase2-1 明載「不可複用證交稅」）：

    | 項目 | 股票 | 期貨 |
    |------|------|------|
    | 交易稅 | 證交稅 0.3%，**只課賣出** | 期交稅十萬分之二，**買賣各課一次** |
    | 稅基 | 成交金額 | **契約價值**（價格 × 乘數 × 口數） |
    | 手續費 | 費率 × 折扣、有最低收費 | **每口固定金額**，無最低收費 |

    **`tax_rate` 是法規值、`commission_per_lot` 是市場常見值**，兩者的可信度不同
    （見 `FuturesCost`）。手續費由券商議定，要精確模擬請用
    `commission_per_lot_by_product` 逐商品指定——小型契約（MTX／TMF）的實務行情
    明顯低於大台，用同一個數字會高估小台的成本。

    **本設定不含滑價**：滑價屬「成交假設」不是「費用」，與台股同一種切法放在
    `FuturesFillConfig`（`core/backtest/models/fill_model.py`），
    且期貨以**跳動點**表達而非基點。
    """

    commission_per_lot: float = float(
        FuturesCost.CommissionPerLot
    )  # 每口手續費（單邊）
    tax_rate: float = float(FuturesCost.TaxRate)  # 期交稅率（對契約價值課徵）
    # 逐商品的每口手續費；未列的商品沿用 `commission_per_lot`
    commission_per_lot_by_product: Optional[Dict[str, float]] = None

    @staticmethod
    def default() -> "FuturesCostConfig":
        """預設設定：期交稅為法規值、手續費取市場常見值（見 class docstring）"""

        return FuturesCostConfig()

    @staticmethod
    def free() -> "FuturesCostConfig":
        """
        零成本設定：**只用於驗證引擎接線**

        此時 PnL 恰好等於「價格變動 × 乘數 × 口數」，任何偏差都必定來自記帳本身。
        **不可拿來評估策略績效**——期貨的成本佔比在短線策略上不小，
        零成本回測會系統性高估。
        """

        return FuturesCostConfig(commission_per_lot=0.0, tax_rate=0.0)

    def get_commission_per_lot(self, product: Optional[str] = None) -> float:
        """取得該商品的每口手續費；未逐商品指定時沿用共用值"""

        if product is None or not self.commission_per_lot_by_product:
            return self.commission_per_lot

        return self.commission_per_lot_by_product.get(product, self.commission_per_lot)


class TwFuturesCostModel(BaseCostModel):
    """
    台期貨成本模型

    費率的唯一來源是 `FuturesCostConfig`，且 `FuturesPositionManager` 與本 model
    **共用同一個實例**（由 factory 注入）——兩處各算一份必然漂移。

    取整規則與 `StockCostModel` 一致：費用無條件捨去（`int()`），損益與報酬率
    round 至小數點後 2 位。**期交稅捨去到元是刻意的**：TX 一口的期交稅約
    20000 × 200 × 0.00002 ＝ 80 元，捨去的誤差在 1 元以內；用浮點數留小數只會讓
    交易明細出現 79.9999 這種數字。

    與 `StockCostModel` 的三個結構差異：

    1. **稅基是契約價值**（價格 × 乘數 × 口數），故 `tax()` 需要 `multiplier`。
    2. **買賣都要課稅**：`tax()` 不看 `action`，這正是「不可複用證交稅」的核心。
    3. **報酬率的分母是保證金**，不是契約價值——期貨投入的資金就是保證金，
       用契約價值當分母會把槓桿效果整個抹掉，故 `roi()` 與 `roi_on_capital()`
       在期貨是同一個數字。
    """

    def __init__(self, config: Optional[FuturesCostConfig] = None):
        self.config: FuturesCostConfig = config or FuturesCostConfig.default()

    def commission(
        self,
        price: float = 0.0,
        volume: int = 0,
        product: Optional[str] = None,
    ) -> int:
        """
        - Description:
            單邊手續費 ＝ 每口金額 × 口數

            **與價格無關**，`price` 只為對齊 `BaseCostModel` 的介面；
            期貨手續費是每口固定金額，沒有費率、折扣，也沒有最低收費。
        - Parameters:
            - price: float
                成交價（不參與計算）
            - volume: int
                口數
            - product: Optional[str]
                契約代碼；有逐商品費率時據此取值
        - Return:
            - int
                手續費
        """

        return int(self.config.get_commission_per_lot(product) * volume)

    def tax(
        self,
        price: float,
        volume: int,
        multiplier: int = 1,
        **kwargs,
    ) -> int:
        """
        - Description:
            期交稅 ＝ 契約價值 × 稅率，**買賣各課一次**

            股票的證交稅只課賣出，期貨兩邊都課——複用股票那套會讓開倉少收一次稅。
        - Parameters:
            - price: float
                成交價
            - volume: int
                口數
            - multiplier: int
                契約乘數（元／點）；預設 1 僅為對齊介面，實務上一定要帶
        - Return:
            - int
                期交稅
        """

        return int(price * multiplier * volume * self.config.tax_rate)

    def round_trip_cost(
        self,
        entry_price: float,
        exit_price: float,
        volume: int,
        multiplier: int,
        product: Optional[str] = None,
    ) -> int:
        """
        一口來回的總成本（開倉手續費 ＋ 開倉稅 ＋ 平倉手續費 ＋ 平倉稅）

        用來回答「這筆交易至少要賺幾點才不虧」：把本值除以
        `multiplier × volume` 即為損益兩平所需的點數。
        """

        return (
            self.commission(entry_price, volume, product)
            + self.tax(entry_price, volume, multiplier)
            + self.commission(exit_price, volume, product)
            + self.tax(exit_price, volume, multiplier)
        )

    def breakeven_points(
        self,
        price: float,
        volume: int,
        multiplier: int,
        product: Optional[str] = None,
    ) -> float:
        """
        損益兩平所需的價格變動（點）

        期貨的成本以「幾點」表達最直觀：TX 在 20,000 點、每口手續費 50 元時
        來回成本約 260 元／口，換算約 1.3 點——低於這個幅度的訊號一律是負期望值。
        """

        if multiplier <= 0 or volume <= 0:
            return 0.0

        cost: int = self.round_trip_cost(price, price, volume, multiplier, product)
        return round(cost / (multiplier * volume), 4)

    def realized_pnl(
        self,
        entry_price: float = 0.0,
        exit_price: float = 0.0,
        volume: int = 0,
        multiplier: int = 0,
        position_type: PositionType = PositionType.LONG,
        transaction_cost: float = 0.0,
        **kwargs,
    ) -> float:
        """
        已實現損益 ＝ 價格變動 × 乘數 × 口數 − 交易成本

        **不含逐日盯市已結算的各段**：那由 `FuturesPositionManager` 依平倉口數
        等比例攤提，見 `close_single_position()`。本方法只算單一段落的價格損益。
        """

        direction: int = 1 if position_type == PositionType.LONG else -1
        pnl: float = (exit_price - entry_price) * multiplier * volume * direction
        return round(pnl - transaction_cost, 2)

    def roi(self, realized_pnl: float = 0.0, margin: float = 0.0, **kwargs) -> float:
        """名目報酬率（%）：**分母是保證金**，保證金為 0 時回傳 0"""

        if not margin:
            return 0.0
        return round(realized_pnl / margin * 100, 2)

    def roi_on_capital(
        self, realized_pnl: float = 0.0, margin: float = 0.0, **kwargs
    ) -> float:
        """
        資金效率報酬率（%）

        期貨實際投入的資金就是保證金，故與 `roi()` 相同——台股兩者不同是因為
        放空的名目報酬率以賣出價款為分母，實際佔用的卻是保證金。
        """

        return self.roi(realized_pnl=realized_pnl, margin=margin)

    def margin_required(
        self,
        price: float = 0.0,
        volume: int = 0,
        multiplier: int = 0,
        **kwargs,
    ) -> int:
        """
        開倉所需保證金

        **本模型不算保證金**：期貨的原始保證金是交易所公告的每口固定金額，
        不是任何比率算得出來的（見 `FuturesMarginConfig`），一律走
        `FuturesPositionManager.calculate_margin()` 查表。此處維持 0 並保留簽章，
        是為了不讓呼叫端誤以為成本模型有第二套保證金口徑。
        """

        return 0
