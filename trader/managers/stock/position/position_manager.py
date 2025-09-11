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
        if stock_order.position_type == PositionType.LONG and stock_order.action == Action.BUY:
            open_cost: int = 0
            open_cost, _ = StockUtils.calculate_transaction_cost(
                buy_price=stock_order.price,
                volume=stock_order.volume,
            )

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
                    commission=open_cost,
                    tax=0,
                    transaction_cost=open_cost,
                    unrealized_pnl=0,
                    unrealized_roi=0,
                )

                self.account.balance -= position_value + open_cost
                self.account.positions.append(position)
        # Open Short & Sell Position
        elif stock_order.position_type == PositionType.SHORT and stock_order.action == Action.SELL:
            pass
        return position

    def close_position(self, stock_order: StockOrder) -> List[StockPosition]:
        """
        - Description: 下單平倉股票（支援 FIFO 拆倉與部分平倉）
        - Parameters:
            - stock_order: StockOrder
                目標股票的訂單資訊
        - Return:
            - closed_positions: List[StockPosition]
                實際被平倉的所有倉位（可能為多筆）
        """
        # 要平倉的倉位 List
        close_positions: List[StockPosition] = []

        # 從帳戶抓出所有該股票未平倉的倉位（FIFO）
        open_positions: List[StockPosition] = [
            p
            for p in self.account.positions
            if p.stock_id == stock_order.stock_id and not p.is_closed
        ]

        # Calculate total open volume
        total_open_volume: int = sum(p.volume for p in open_positions)

        # Check if the open volume is enough
        if stock_order.volume > total_open_volume:
            logger.warning(
                f"[Place Close Order] Insufficient holdings! {stock_order.stock_id} has {total_open_volume} lots available, attempted to sell {stock_order.volume} lots"
            )


        # Execute close order
        for position in open_positions:
            # Close Long & Sell Position
            if (
                position.position_type == PositionType.LONG
                and stock_order.action == Action.SELL
            ):
                # Case 1: 倉位張數 == 要平倉張數 -> 直接平倉（直接移除該倉位）
                if position.volume == stock_order.volume:
                    logger.info(f"* Place Close Order: {stock_order.stock_id}")

                    # Calculate position value
                    position_value: float = self.calculate_position_value(
                        price=stock_order.price,
                        volume=stock_order.volume,
                    )
                    # Calculate close cost
                    close_cost: int = 0
                    _, close_cost = StockUtils.calculate_transaction_cost(
                        sell_price=stock_order.price,
                        volume=stock_order.volume,
                    )

                    # Create stock trade record
                    stock_trade_record: StockTradeRecord = StockTradeRecord(
                        id=position.id,
                        stock_id=stock_order.stock_id,
                        is_closed=True,
                        position_type=position.position_type,
                        buy_date=position.date,
                        buy_price=position.price,
                        buy_volume=position.volume,
                        sell_date=stock_order.date,
                        sell_price=stock_order.price,
                        sell_volume=stock_order.volume,
                        commission=position.commission + StockUtils.calculate_transaction_commission(
                            price=stock_order.price,
                            volume=stock_order.volume,
                        ),
                        tax=StockUtils.calculate_transaction_tax(
                            stock_order.price,
                            stock_order.volume,
                        ),
                        transaction_cost=position.transaction_cost + close_cost,
                        realized_pnl=StockUtils.calculate_net_profit(
                            buy_price=position.price,
                            sell_price=stock_order.price,
                            volume=stock_order.volume,
                        ),
                        roi=StockUtils.calculate_roi(
                            buy_price=position.price,
                            sell_price=stock_order.price,
                            volume=stock_order.volume,
                        ),
                    )

                    # Update position
                    position.is_closed = True
                    position.volume = 0

                    # Update account
                    self.account.balance += position_value - close_cost
                    self.account.realized_pnl += stock_trade_record.realized_pnl
                    self.account.trade_records.append(stock_trade_record)
                    self.account.remove_closed_positions()

                    close_positions.append(position)


                # Case 2: 倉位張數 > 要平倉張數 -> 部分平倉
                elif position.volume > stock_order.volume:
                    pass
                # Case 3: 倉位張數 < 要平倉張數 -> 直接平倉
                else:
                    pass

        return close_positions

    def split_position(self, stock_order: StockOrder) -> None:
        """Split Stock Position"""
        pass

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