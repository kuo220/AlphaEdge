import datetime
from typing import Optional, Union

from loguru import logger

from core.backtest.models.cost_model import CostConfig, StockCostModel
from core.managers.base.position_manager import BasePositionManager
from core.models import StockAccount, StockOrder, StockPosition, StockTradeRecord
from core.utils import Action, PositionType, ShortMethod
from core.utils.instrument import StockUtils


class StockPositionManager(BasePositionManager):
    """
    Stock Position Manager

    多空的記帳差異全部收斂在此：
    - LONG 沿用既有 StockUtils 公式（確保與改動前的回測結果逐筆相同）
    - SHORT 一律走 StockCostModel，涵蓋保證金、借券費、融券利息與當沖稅率
    """

    def __init__(
        self,
        account: StockAccount,
        cost_model: Optional[StockCostModel] = None,
    ):
        super().__init__(account)
        self.cost_model: StockCostModel = cost_model or StockCostModel(
            CostConfig.default()
        )

    def setup(self, *args, **kwargs) -> None:
        """Set Up the Config of Stock Position Manager"""
        pass

    def normalize_date(
        self, date: Union[datetime.date, datetime.datetime]
    ) -> datetime.date:
        """Tick 級別的 date 會是 datetime，統一取其日期部分以計算持有曆日數"""

        return date.date() if isinstance(date, datetime.datetime) else date

    def calculate_holding_days(
        self,
        entry_date: Union[datetime.date, datetime.datetime],
        exit_date: Union[datetime.date, datetime.datetime],
    ) -> int:
        """計算持有曆日數（非交易日），同日開平倉為 0 天"""

        if entry_date is None or exit_date is None:
            return 0

        return (self.normalize_date(exit_date) - self.normalize_date(entry_date)).days

    def open_position(self, stock_order: StockOrder) -> Optional[StockPosition]:
        """
        - Description: 開倉下單股票
        - Parameters:
            - stock: StockOrder
                目標股票的訂單資訊
        - Return:
            - position: StockPosition
        """
        # Calculate position value
        position_value: float = self.calculate_position_value(
            price=stock_order.price,
            volume=stock_order.volume,
        )

        # Create position
        position: Optional[StockPosition] = None

        # Open Long & Buy Position
        if (
            stock_order.position_type == PositionType.LONG
            and stock_order.action == Action.BUY
        ):
            logger.info(
                f"* Open Long Position: {stock_order.stock_id} ({stock_order.volume} lots)"
            )

            # Calculate open commission & tax & total open cost
            open_commission: int = self.cost_model.commission(
                price=stock_order.price,
                volume=stock_order.volume,
            )
            # 做多的證交稅課在賣出端，開倉恆為 0（由成本模型依 action 判定）
            open_tax: int = self.cost_model.tax(
                price=stock_order.price,
                volume=stock_order.volume,
                action=Action.BUY,
            )
            open_cost: int = open_commission + open_tax

            # Check if the account has enough balance
            if self.account.balance >= position_value + open_cost:
                logger.info(f"* Place Open Order: {stock_order.stock_id}")

                position = StockPosition(
                    id=self.account.generate_trade_id(),
                    stock_id=stock_order.stock_id,
                    is_closed=False,
                    position_type=stock_order.position_type,
                    date=stock_order.date,
                    price=stock_order.price,
                    volume=stock_order.volume,
                    commission=open_commission,
                    tax=open_tax,
                    transaction_cost=open_cost,
                    unrealized_pnl=0,
                    unrealized_roi=0,
                )

                self.account.balance -= position_value + open_cost
                self.account.positions.append(position)
        # Open Short & Sell Position
        elif (
            stock_order.position_type == PositionType.SHORT
            and stock_order.action == Action.SELL
        ):
            logger.info(
                f"* Open Short Position: {stock_order.stock_id} ({stock_order.volume} lots)"
            )

            position = self.open_short_position(stock_order, position_value)

        return position

    def open_short_position(
        self,
        stock_order: StockOrder,
        position_value: float,
    ) -> Optional[StockPosition]:
        """
        - Description:
            開立放空部位（賣出）

            資金規則：賣出價款不計入可用餘額，先留作擔保品記在 position.short_proceeds，
            待回補平倉時才一次結算損益到 account.balance；帳戶當下只扣「保證金 + 開倉成本」。
            當沖（DAY_TRADE）不需保證金，僅扣開倉成本。
        - Parameters:
            - stock_order: StockOrder
                目標股票的訂單資訊
            - position_value: float
                開倉部位價值（賣出價金）
        - Return:
            - position: Optional[StockPosition]
                開倉成功回傳部位，被風控擋下則回傳 None
        """

        short_method: ShortMethod = (
            stock_order.short_method or self.cost_model.config.short_method
        )

        # 同一標的不允許同時持有反向部位
        if self.account.check_has_position(stock_order.stock_id, PositionType.LONG):
            logger.warning(
                f"[Open Short] {stock_order.stock_id} 已有做多部位，不允許同標的雙向持倉，拒絕開倉"
            )
            return None

        # Calculate open commission & tax & borrow fee & margin
        open_commission: int = self.cost_model.commission(
            price=stock_order.price, volume=stock_order.volume
        )
        open_tax: int = self.cost_model.tax(
            price=stock_order.price,
            volume=stock_order.volume,
            action=Action.SELL,
            is_day_trade=stock_order.is_day_trade,
        )
        borrow_fee: int = self.cost_model.borrow_fee(
            price=stock_order.price,
            volume=stock_order.volume,
            short_method=short_method,
        )
        margin: int = self.cost_model.margin_required(
            price=stock_order.price,
            volume=stock_order.volume,
            short_method=short_method,
        )
        open_cost: int = open_commission + open_tax + borrow_fee

        # Check if the account has enough balance for margin and costs
        if self.account.balance < margin + open_cost:
            logger.warning(
                f"[Open Short] {stock_order.stock_id} 餘額不足："
                f"需要 {margin + open_cost}，可用 {self.account.balance}，拒絕開倉"
            )
            return None

        # Check single position short exposure limit
        max_ratio: Optional[float] = (
            self.cost_model.config.short_constraint.max_short_exposure_ratio
        )
        if (
            max_ratio is not None
            and position_value > self.account.init_capital * max_ratio
        ):
            logger.warning(
                f"[Open Short] {stock_order.stock_id} 曝險 {position_value} 超過上限 "
                f"{self.account.init_capital * max_ratio}，拒絕開倉"
            )
            return None

        logger.info(f"* Place Open Order: {stock_order.stock_id}")

        position: StockPosition = StockPosition(
            id=self.account.generate_trade_id(),
            stock_id=stock_order.stock_id,
            is_closed=False,
            position_type=stock_order.position_type,
            date=stock_order.date,
            price=stock_order.price,
            volume=stock_order.volume,
            commission=open_commission,
            tax=open_tax,
            transaction_cost=open_cost,
            unrealized_pnl=0,
            unrealized_roi=0,
            short_method=short_method,
            is_day_trade=stock_order.is_day_trade,
            margin=margin,
            short_proceeds=position_value,
            borrow_fee=borrow_fee,
        )

        self.account.balance -= margin + open_cost
        self.account.margin_used += margin
        self.account.positions.append(position)

        return position

    def close_single_position(
        self,
        position: StockPosition,
        stock_order: StockOrder,
        close_volume: int,
    ) -> StockTradeRecord:
        """依部位方向分派記帳；FIFO 拆單主幹在 BasePositionManager"""

        if position.position_type == PositionType.SHORT:
            logger.info(
                f"* Close Short Position: {position.stock_id} ({position.volume} lots)"
            )
            return self.close_short_position(position, stock_order, close_volume)

        logger.info(
            f"* Close Long Position: {position.stock_id} ({position.volume} lots)"
        )
        return self.close_long_position(position, stock_order, close_volume)

    def settle_daily(self, position: StockPosition, settle_price: float) -> None:
        """股票沒有每日結算：損益於平倉才實現，故為 no-op（期貨的掛點）"""

        pass

    def close_long_position(
        self,
        position: StockPosition,
        stock_order: StockOrder,
        close_volume: int,
    ) -> StockTradeRecord:
        """平掉做多部位（賣出），支援部分平倉的等比例攤提"""

        # Calculate position value
        position_value: float = self.calculate_position_value(
            price=stock_order.price,
            volume=close_volume,
        )

        # Calculate sell commission & tax & total close cost
        sell_commission: int = self.cost_model.commission(
            price=stock_order.price,
            volume=close_volume,
        )
        sell_tax: int = self.cost_model.tax(
            price=stock_order.price,
            volume=close_volume,
            action=Action.SELL,
        )

        # 開倉成本依平倉張數等比例攤提。
        # **不可改為「以平倉張數重算手續費」**：那會讓最低手續費在部分平倉時被重複套用，
        # 使同一筆交易的 record.commission 與 realized_pnl 用到兩個不同的開倉手續費
        # （舊 StockUtils 路徑的既有瑕疵，見 tests/backtest/compare_cost_formula.py）
        proportional_buy_commission: int = int(
            position.commission * (close_volume / position.volume)
        )
        total_transaction_cost: int = (
            proportional_buy_commission + sell_commission + sell_tax
        )

        # Create stock trade record
        record: StockTradeRecord = StockTradeRecord(
            id=position.id,
            stock_id=position.stock_id,
            is_closed=True,
            position_type=position.position_type,
            buy_date=position.date,
            buy_price=position.price,
            buy_volume=close_volume,
            sell_date=stock_order.date,
            sell_price=stock_order.price,
            sell_volume=close_volume,
            commission=proportional_buy_commission + sell_commission,
            tax=sell_tax,
            transaction_cost=total_transaction_cost,
            realized_pnl=self.cost_model.realized_pnl(
                position_type=PositionType.LONG,
                entry_price=position.price,
                exit_price=stock_order.price,
                volume=close_volume,
                entry_cost=proportional_buy_commission,
                exit_cost=sell_commission + sell_tax,
            ),
            roi=self.cost_model.roi(
                position_type=PositionType.LONG,
                entry_price=position.price,
                exit_price=stock_order.price,
                volume=close_volume,
                entry_cost=proportional_buy_commission,
                exit_cost=sell_commission + sell_tax,
            ),
        )

        # Update position
        position.volume -= close_volume
        position.commission -= proportional_buy_commission
        position.transaction_cost -= proportional_buy_commission
        if position.volume == 0:
            position.is_closed = True

        # Update account
        self.account.balance += position_value - (sell_commission + sell_tax)
        self.account.realized_pnl += record.realized_pnl
        self.account.trade_records.append(record)

        return record

    def close_short_position(
        self,
        position: StockPosition,
        stock_order: StockOrder,
        close_volume: int,
    ) -> StockTradeRecord:
        """
        - Description:
            回補放空部位（買進），支援部分回補的等比例攤提

            保證金、擔保價款、借券費與股利補償一律依回補張數比例攤提；
            融券利息於此依 exit_date − entry_date 一次算出，
            不由 accrue_holding_cost() 重複計算。
        - Parameters:
            - position: StockPosition
                被回補的放空部位
            - stock_order: StockOrder
                回補訂單
            - close_volume: int
                本次回補張數（Unit: Lots）
        - Return:
            - record: StockTradeRecord
                本次回補產生的交易紀錄
        """

        # 依張數比例攤提開倉時的各項成本與擔保品
        ratio: float = close_volume / position.volume
        prop_margin: float = round(position.margin * ratio, 2)
        prop_proceeds: float = round(position.short_proceeds * ratio, 2)
        prop_open_commission: int = int(position.commission * ratio)
        prop_open_tax: int = int(position.tax * ratio)
        prop_borrow_fee: int = int(position.borrow_fee * ratio)
        prop_accrued_borrow_fee: int = int(position.accrued_borrow_fee * ratio)
        prop_dividend_compensation: int = int(position.dividend_compensation * ratio)

        # 回補手續費（買進不課證交稅）
        close_commission: int = self.cost_model.commission(
            price=stock_order.price, volume=close_volume
        )

        # 融券保證金利息（收入）
        holding_days: int = self.calculate_holding_days(position.date, stock_order.date)
        interest: int = self.cost_model.short_interest(
            proceeds=prop_proceeds,
            margin=prop_margin,
            holding_days=holding_days,
            short_method=position.short_method,
        )

        # 開倉成本、平倉成本與持有期間淨成本（借券費支出 + 股利補償 − 利息收入）
        entry_cost: int = prop_open_commission + prop_open_tax + prop_borrow_fee
        carry_cost: int = (
            prop_accrued_borrow_fee + prop_dividend_compensation - interest
        )

        realized_pnl: float = self.cost_model.realized_pnl(
            position_type=PositionType.SHORT,
            entry_price=position.price,
            exit_price=stock_order.price,
            volume=close_volume,
            entry_cost=entry_cost,
            exit_cost=close_commission,
            carry_cost=carry_cost,
        )
        roi: float = self.cost_model.roi(
            position_type=PositionType.SHORT,
            entry_price=position.price,
            exit_price=stock_order.price,
            volume=close_volume,
            entry_cost=entry_cost,
            exit_cost=close_commission,
            carry_cost=carry_cost,
        )
        roi_on_capital: float = self.cost_model.roi_on_capital(
            position_type=PositionType.SHORT,
            entry_price=position.price,
            exit_price=stock_order.price,
            volume=close_volume,
            entry_cost=entry_cost,
            exit_cost=close_commission,
            carry_cost=carry_cost,
            margin=prop_margin,
        )

        # Create stock trade record（sell_* 為放空開倉、buy_* 為回補）
        record: StockTradeRecord = StockTradeRecord(
            id=position.id,
            stock_id=position.stock_id,
            is_closed=True,
            position_type=position.position_type,
            sell_date=position.date,
            sell_price=position.price,
            sell_volume=close_volume,
            buy_date=stock_order.date,
            buy_price=stock_order.price,
            buy_volume=close_volume,
            commission=prop_open_commission + close_commission,
            tax=prop_open_tax,
            transaction_cost=entry_cost
            + close_commission
            + prop_accrued_borrow_fee
            + prop_dividend_compensation
            - interest,
            realized_pnl=realized_pnl,
            roi=roi,
            roi_on_capital=roi_on_capital,
            short_method=position.short_method,
            borrow_fee=prop_borrow_fee + prop_accrued_borrow_fee,
            interest=interest,
            dividend_compensation=prop_dividend_compensation,
            margin=prop_margin,
            holding_days=holding_days,
        )

        # Update position
        position.volume -= close_volume
        position.commission -= prop_open_commission
        position.tax -= prop_open_tax
        position.borrow_fee -= prop_borrow_fee
        position.accrued_borrow_fee -= prop_accrued_borrow_fee
        position.dividend_compensation -= prop_dividend_compensation
        position.transaction_cost -= entry_cost
        position.margin -= prop_margin
        position.short_proceeds -= prop_proceeds
        if position.volume == 0:
            position.is_closed = True

        # Update account：釋回保證金並結算損益
        # realized_pnl 已扣掉開倉成本，而開倉成本在開倉當下就從餘額扣過了，
        # 故此處加回 entry_cost，避免同一筆成本被扣兩次（與 LONG 的現金流口徑一致）。
        # 股利補償同理：除息當日就已從餘額扣款（`compensate_cash_dividend()`），
        # 這裡加回攤提進 realized_pnl 的那一份。
        # **與 accrued_borrow_fee 的差異**：借券費不動餘額、只在平倉時經損益扣一次；
        # 股利補償走即時扣款，除息日的價格跳空才會被同額的現金流出抵銷，
        # 逐日權益曲線不會憑空多出一段假獲利
        self.account.balance += (
            prop_margin + realized_pnl + entry_cost + prop_dividend_compensation
        )
        self.account.margin_used -= prop_margin
        self.account.realized_pnl += realized_pnl
        self.account.trade_records.append(record)

        return record

    def calculate_position_value(self, price: float, volume: int) -> float:
        """
        - Description: 計算股票部位價值
        - Parameters:
            - price: float
                股票價格
            - volume: int
                股票張數
        - Return:
            - position_value: float
                股票部位價值
        """
        return price * StockUtils.convert_lot_to_share(volume)
