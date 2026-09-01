import datetime
from dataclasses import dataclass
from typing import Optional, Union

from loguru import logger

from core.managers.base.position_manager import BasePositionManager
from core.models import (
    FuturesAccount,
    FuturesOrder,
    FuturesPosition,
    FuturesTradeRecord,
)
from core.utils import Action, PositionType
from core.utils.constant import FUTURES_MULTIPLIER

"""
FuturesPositionManager: 期貨部位管理（口數、保證金、逐日盯市）

**與 `StockPositionManager` 的三個根本差異**：

1. **開倉只凍結保證金，不買下契約價值**。股票買進是把錢換成股票；期貨開倉只從
   可動用餘額移出保證金，契約價值本身不動用資金。
2. **逐日盯市**。每個交易日以結算價結清當日損益，現金當天就進出帳戶，
   部位的 `price` 隨之重設為結算價。`settle_daily()` 是 `BasePositionManager`
   早就留好的掛點（股票側為 no-op）。
3. **沒有證交稅、沒有股數換算**。PnL = 價格變動 × 乘數 × 口數，方向由多空決定。
"""


@dataclass
class FuturesCostConfig:
    """
    期貨交易成本設定

    **本階段一律為 0，是刻意的**：Phase2-1 才是期貨成本模型（期交稅、手續費、滑價）
    的所屬步驟，且該步驟明載「**不可複用證交稅**」。在查證到實際費率之前填任何
    數字都是憑空捏造，會讓 PnL 靜默偏掉。此處只把掛點準備好，
    讓 Phase2-1 有地方接上，並讓本階段的 PnL 恰好等於價格公式。
    """

    commission_per_lot: float = 0.0  # 每口手續費（買賣各收一次）
    tax_rate: float = 0.0  # 期交稅率（對契約價值課徵，買賣各收一次）

    @staticmethod
    def default() -> "FuturesCostConfig":
        """預設設定：全部為 0，見 class docstring"""

        return FuturesCostConfig()


@dataclass
class FuturesMarginConfig:
    """
    保證金設定（**簡化版**）

    真實的 TAIFEX 原始保證金是**每口固定金額**且會隨市場波動調整（有生效日的歷史
    序列），不是契約價值的固定比例。完整版屬 Phase2-2，資料落在
    `futures_margin_history` 表。

    本階段以「契約價值 × 比率」近似，理由是：**寧可用一個明顯是近似的公式，
    也不要寫死一個看起來很精確、實際上只在某個時點正確的金額**——後者會讓人
    以為保證金已經做對了。比率預設 0.1，可由呼叫端調整。

    ⚠️ **這個近似跨年份會系統性偏掉**：實際保證金由 TAIFEX 依波動度每日計算、
    達門檻就調（TX 在 2015~2026 調整 62 次，間隔最短 2 天、最長 372 天），
    且**調整後溯及既往**，未沖銷部位一併適用。改為查表的規劃見
    `backlog/台期貨保證金ETL.md`（S5 會把本 config 接上 `FuturesMarginAPI`）。
    """

    initial_margin_ratio: float = 0.1  # 原始保證金佔契約價值的比率

    @staticmethod
    def default() -> "FuturesMarginConfig":
        """預設設定：原始保證金 = 契約價值 × 10%"""

        return FuturesMarginConfig()


class FuturesPositionManager(BasePositionManager):
    """Futures Position Manager"""

    def __init__(
        self,
        account: FuturesAccount,
        cost_config: Optional[FuturesCostConfig] = None,
        margin_config: Optional[FuturesMarginConfig] = None,
    ):
        super().__init__(account)
        self.account: FuturesAccount = account
        self.cost_config: FuturesCostConfig = cost_config or FuturesCostConfig.default()
        self.margin_config: FuturesMarginConfig = (
            margin_config or FuturesMarginConfig.default()
        )

    def setup(self, *args, **kwargs) -> None:
        """Set Up the Config of Futures Position Manager"""
        pass

    # === 共用計算 ===
    @staticmethod
    def get_multiplier(product: str) -> int:
        """
        取得契約乘數

        **刻意用 `[]` 而非 `.get()`**：未登錄的商品讓它當場 KeyError，
        乘數猜錯不會有任何徵兆，只會讓整條 PnL 靜默偏掉（見 `FUTURES_MULTIPLIER`）。
        """

        return FUTURES_MULTIPLIER[product]

    def calculate_contract_value(
        self, price: float, volume: int, multiplier: int
    ) -> float:
        """契約價值 ＝ 價格 × 乘數 × 口數"""

        return price * multiplier * volume

    def calculate_margin(self, price: float, volume: int, multiplier: int) -> float:
        """原始保證金（簡化版：契約價值 × 比率，見 `FuturesMarginConfig`）"""

        contract_value: float = self.calculate_contract_value(price, volume, multiplier)
        return contract_value * self.margin_config.initial_margin_ratio

    def calculate_commission(self, volume: int) -> float:
        """手續費：每口固定金額"""

        return self.cost_config.commission_per_lot * volume

    def calculate_tax(self, price: float, volume: int, multiplier: int) -> float:
        """期交稅：對契約價值課徵（**不是證交稅**，費率見 `FuturesCostConfig`）"""

        contract_value: float = self.calculate_contract_value(price, volume, multiplier)
        return contract_value * self.cost_config.tax_rate

    def calculate_pnl(
        self,
        position_type: PositionType,
        entry_price: float,
        exit_price: float,
        volume: int,
        multiplier: int,
    ) -> float:
        """
        - Description:
            期貨損益：**價格變動 × 乘數 × 口數**，方向由多空決定

            這是本步驟的驗收公式；沒有股數換算、沒有證交稅。
        - Parameters:
            - position_type: PositionType
                部位方向
            - entry_price / exit_price: float
                進場價與出場價
            - volume: int
                口數
            - multiplier: int
                契約乘數（元／點）
        - Return:
            - float
                損益（未扣交易成本）
        """

        direction: int = 1 if position_type == PositionType.LONG else -1
        return (exit_price - entry_price) * multiplier * volume * direction

    @staticmethod
    def normalize_date(
        date: Union[datetime.date, datetime.datetime],
    ) -> Optional[datetime.date]:
        """Tick 級別的 date 會是 datetime，統一取其日期部分以計算持有曆日數"""

        if date is None:
            return None
        return date.date() if isinstance(date, datetime.datetime) else date

    def calculate_holding_days(
        self,
        entry_date: Union[datetime.date, datetime.datetime],
        exit_date: Union[datetime.date, datetime.datetime],
    ) -> int:
        """計算持有曆日數（非交易日），同日開平倉為 0 天"""

        entry: Optional[datetime.date] = self.normalize_date(entry_date)
        exit_: Optional[datetime.date] = self.normalize_date(exit_date)
        if entry is None or exit_ is None:
            return 0
        return (exit_ - entry).days

    # === 開倉 ===
    def open_position(self, order: FuturesOrder) -> Optional[FuturesPosition]:
        """
        - Description:
            開倉（多空皆走同一條路徑）

            **與股票不同，不檢查「餘額是否足以買下契約價值」**，而是檢查
            「可動用餘額是否足以繳出保證金與交易成本」。
        - Parameters:
            - order: FuturesOrder
                目標契約的訂單資訊
        - Return:
            - Optional[FuturesPosition]
                開倉成功的部位；保證金不足時為 None
        """

        # 開倉動作與方向必須一致：多單買進開倉、空單賣出開倉
        is_long_open: bool = (
            order.position_type == PositionType.LONG and order.action == Action.BUY
        )
        is_short_open: bool = (
            order.position_type == PositionType.SHORT and order.action == Action.SELL
        )
        if not (is_long_open or is_short_open):
            logger.warning(
                f"[Open Position] 方向與動作不一致：{order.contract_id} "
                f"{order.position_type} / {order.action}"
            )
            return None

        multiplier: int = self.get_multiplier(order.product)
        margin: float = self.calculate_margin(order.price, order.volume, multiplier)
        commission: float = self.calculate_commission(order.volume)
        tax: float = self.calculate_tax(order.price, order.volume, multiplier)
        open_cost: float = commission + tax

        if self.account.balance < margin + open_cost:
            logger.warning(
                f"[Open Position] 可動用餘額不足：{order.contract_id} "
                f"需要 {margin + open_cost:.0f}，實際 {self.account.balance:.0f}"
            )
            return None

        logger.info(
            f"* Open {order.position_type.value} Position: "
            f"{order.contract_id} ({order.volume} lots)"
        )

        position: FuturesPosition = FuturesPosition(
            id=self.account.generate_trade_id(),
            product=order.product,
            expiry=order.expiry,
            is_closed=False,
            position_type=order.position_type,
            date=order.date,
            price=order.price,
            volume=order.volume,
            commission=commission,
            tax=tax,
            transaction_cost=open_cost,
            unrealized_pnl=0.0,
            unrealized_roi=0.0,
            multiplier=multiplier,
            margin=margin,
        )

        # 保證金由可動用餘額移入佔用，交易成本則直接支出
        self.account.balance -= margin + open_cost
        self.account.margin_used += margin
        self.account.positions.append(position)

        return position

    # === 逐日盯市 ===
    def settle_daily(self, position: FuturesPosition, settle_price: float) -> None:
        """
        - Description:
            以結算價結清當日損益（逐日盯市）

            **這是期貨與股票最根本的記帳差異**：損益當天就進出帳戶，不等到平倉。
            結算後 `position.price` 重設為結算價，下一日的結算才不會重複計算同一段。
            累計金額記在 `position.settled_pnl`，平倉時併入交易紀錄的總損益。

            `settle_price` 為 None（夜盤沒有結算價）時**不做任何事**，
            不可當成 0 —— 那會讓部位在一天內被結算成歸零。
        - Parameters:
            - position: FuturesPosition
                待結算的部位
            - settle_price: float
                當日結算價
        """

        if settle_price is None or position.is_closed:
            return

        daily_pnl: float = self.calculate_pnl(
            position_type=position.position_type,
            entry_price=position.price,
            exit_price=settle_price,
            volume=position.volume,
            multiplier=position.multiplier,
        )

        position.settled_pnl += daily_pnl
        position.price = settle_price
        position.unrealized_pnl = position.settled_pnl

        self.account.balance += daily_pnl

    # === 平倉 ===
    def close_single_position(
        self,
        position: FuturesPosition,
        order: FuturesOrder,
        close_volume: int,
    ) -> Optional[FuturesTradeRecord]:
        """
        - Description:
            平掉單一部位的指定口數；FIFO 拆單主幹在 `BasePositionManager`

            **損益由兩段組成**：平倉前逐日盯市已結算的 `settled_pnl`（依平倉口數
            等比例攤提）＋ 最後一段（最近結算價 → 平倉價）。只算後者會漏掉前面
            所有交易日的損益。
        - Parameters:
            - position: FuturesPosition
                被平倉的部位
            - order: FuturesOrder
                平倉訂單
            - close_volume: int
                本次平倉口數
        - Return:
            - Optional[FuturesTradeRecord]
                本次平倉產生的交易紀錄
        """

        logger.info(
            f"* Close {position.position_type.value} Position: "
            f"{position.contract_id} ({close_volume} lots)"
        )

        close_ratio: float = close_volume / position.volume

        # 最後一段：最近一次結算價（未結算過則為開倉價）→ 平倉價
        final_leg_pnl: float = self.calculate_pnl(
            position_type=position.position_type,
            entry_price=position.price,
            exit_price=order.price,
            volume=close_volume,
            multiplier=position.multiplier,
        )
        # 先前各段：依平倉口數等比例攤提
        settled_pnl: float = position.settled_pnl * close_ratio

        # 開倉成本依平倉口數等比例攤提（與股票側同一套做法）
        proportional_open_commission: float = position.commission * close_ratio
        proportional_open_tax: float = position.tax * close_ratio
        close_commission: float = self.calculate_commission(close_volume)
        close_tax: float = self.calculate_tax(
            order.price, close_volume, position.multiplier
        )
        total_transaction_cost: float = (
            proportional_open_commission
            + proportional_open_tax
            + close_commission
            + close_tax
        )

        realized_pnl: float = settled_pnl + final_leg_pnl - total_transaction_cost
        released_margin: float = position.margin * close_ratio

        # LONG 是先買後賣、SHORT 是先賣後買
        is_long: bool = position.position_type == PositionType.LONG
        record: FuturesTradeRecord = FuturesTradeRecord(
            id=position.id,
            product=position.product,
            expiry=position.expiry,
            is_closed=True,
            position_type=position.position_type,
            buy_date=position.date if is_long else order.date,
            buy_price=position.entry_price if is_long else order.price,
            buy_volume=close_volume,
            sell_date=order.date if is_long else position.date,
            sell_price=order.price if is_long else position.entry_price,
            sell_volume=close_volume,
            commission=proportional_open_commission + close_commission,
            tax=proportional_open_tax + close_tax,
            transaction_cost=total_transaction_cost,
            realized_pnl=realized_pnl,
            roi=self.calculate_roi(realized_pnl, released_margin),
            multiplier=position.multiplier,
            margin=released_margin,
            settled_pnl=settled_pnl,
            holding_days=self.calculate_holding_days(position.date, order.date),
        )

        # Update position（等比例攤提後扣減）
        position.volume -= close_volume
        position.commission -= proportional_open_commission
        position.tax -= proportional_open_tax
        position.transaction_cost -= (
            proportional_open_commission + proportional_open_tax
        )
        position.settled_pnl -= settled_pnl
        position.margin -= released_margin
        if position.volume == 0:
            position.is_closed = True

        # Update account：釋回保證金、最後一段損益進帳、扣平倉成本
        self.account.margin_used -= released_margin
        self.account.balance += (
            released_margin + final_leg_pnl - (close_commission + close_tax)
        )
        self.account.realized_pnl += realized_pnl
        self.account.trade_records.append(record)

        return record

    @staticmethod
    def calculate_roi(realized_pnl: float, margin: float) -> float:
        """
        報酬率以**保證金**為分母，不是契約價值

        期貨是保證金交易，投入的資金就是保證金；用契約價值當分母會把槓桿效果抹掉。
        保證金為 0（例如比率設成 0）時回傳 0，不拋除零錯誤。
        """

        if margin == 0:
            return 0.0
        return round(realized_pnl / margin * 100, 2)
