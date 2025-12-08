from typing import List, Optional

from loguru import logger

from trader.managers.stock.position.base import BasePositionManager
from trader.models import StockAccount, StockOrder, StockPosition, StockTradeRecord
from trader.utils import Action, PositionType
from trader.utils.instrument import StockUtils


class StockPositionManager(BasePositionManager):
    """Stock Position Manager"""

    def __init__(self, account: StockAccount):
        super().__init__()
        self.account: StockAccount = account

    def setup(self, *args, **kwargs) -> None:
        """Set Up the Config of Stock Position Manager"""
        pass

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
            open_commission: int = StockUtils.calculate_transaction_commission(
                price=stock_order.price,
                volume=stock_order.volume,
            )
            open_tax: int = 0
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
        return position

    def close_position(self, stock_order: StockOrder) -> List[StockTradeRecord]:
        """
        - Description: 下單平倉股票（支援 FIFO 拆倉與部分平倉）
        - Parameters:
            - stock_order: StockOrder
                目標股票的訂單資訊
        - Return:
            - closed_positions: List[StockTradeRecord]
                實際被平倉的所有倉位（可能為多筆）
        """

        # 要平倉的倉位 List
        close_positions: List[StockTradeRecord] = []

        # 從帳戶抓出所有該股票未平倉的倉位（FIFO）
        open_positions: List[StockPosition] = [
            p
            for p in self.account.positions
            if p.stock_id == stock_order.stock_id and not p.is_closed
        ]

        # Calculate remaining close volume
        remaining_close_volume: int = stock_order.volume

        for position in open_positions:
            if remaining_close_volume <= 0:
                break

            # Sell Long Position
            if (
                position.position_type == PositionType.LONG
                and stock_order.action == Action.SELL
            ):
                logger.info(
                    f"* Close Long Position: {position.stock_id} ({position.volume} lots)"
                )

                # 這筆 position 要平倉的數量
                close_volume: int = min(position.volume, remaining_close_volume)

                # Calculate position value
                position_value: float = self.calculate_position_value(
                    price=stock_order.price,
                    volume=close_volume,
                )

                # Calculate sell commission & tax & total close cost
                sell_commission: int = StockUtils.calculate_transaction_commission(
                    price=stock_order.price,
                    volume=close_volume,
                )
                sell_tax: int = StockUtils.calculate_transaction_tax(
                    stock_order.price,
                    close_volume,
                )

                # Calculate proportional buy commission & total_transaction_cost
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
                    realized_pnl=StockUtils.calculate_net_profit(
                        buy_price=position.price,
                        sell_price=stock_order.price,
                        volume=close_volume,
                    ),
                    roi=StockUtils.calculate_roi(
                        buy_price=position.price,
                        sell_price=stock_order.price,
                        volume=close_volume,
                    ),
                )

                # Update position
                position.volume -= close_volume
                position.commission -= proportional_buy_commission
                position.transaction_cost -= proportional_buy_commission
                if position.volume == 0:
                    position.is_closed = True

                # Update account
                self.account.balance += position_value - total_transaction_cost
                self.account.realized_pnl += record.realized_pnl
                self.account.trade_records.append(record)

                close_positions.append(record)
                remaining_close_volume -= close_volume

            # Sell Short Position
            elif (
                position.position_type == PositionType.SHORT
                and stock_order.action == Action.BUY
            ):
                logger.info(
                    f"* Close Short Position: {position.stock_id} ({position.volume} lots)"
                )
                pass

        if remaining_close_volume > 0:
            logger.warning(
                f"[Close Position] Not enough holdings to close {stock_order.volume} lots of {stock_order.stock_id}, "
                f"only closed {stock_order.volume - remaining_close_volume} lots"
            )
            # 📌 業界常見做法：
            # ✔ 不會在 close_position() 內自動開空單（避免混淆職責）
            # ✔ 僅記錄已平倉的部分，對剩餘張數給出警告或拋出錯誤
            # ✔ 是否將剩餘張數視為新開空單，由上層策略層決定
            # 👉 若要嚴格限制，可改為 raise ValueError("Insufficient holdings to close position")

        # Remove closed positions
        self.account.remove_closed_positions()

        return close_positions

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
