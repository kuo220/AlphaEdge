import datetime
from typing import Dict, List, Optional, Union

import pandas as pd

from trader.utils import Commission, PositionType, Scale

from .position import StockPosition
from .record import StockTradeRecord

"""StockAccount: manages account-level state in backtesting (positions, balance, realized PnL, costs)"""


class StockAccount:
    """庫存及餘額資訊"""

    def __init__(self, init_capital: float = 0.0):
        # Initial Setup
        self.init_capital: float = init_capital  # 初始本金

        # Account Balances
        self.balance: float = init_capital  # 餘額

        # Account Performance
        self.realized_pnl: float = 0.0  # 總已實現損益（profit and loss）
        self.roi: float = 0.0  # 帳戶已實現總報酬率

        # Transaction Costs
        self.total_commission: float = 0.0  # 總手續費
        self.total_tax: float = 0.0  # 總交易稅
        self.total_transaction_cost: float = 0  # 總交易成本

        # Trade ID
        self.trade_id_counter: int = 0  # 交易編號（每筆交易唯一編號）

        # Positions & Trading History
        self.positions: List[StockPosition] = []  # 持有未平倉的股票庫存
        self.trade_records: List[StockTradeRecord] = []  # 股票歷史交易紀錄

    def generate_trade_id(self) -> int:
        """生成下一筆交易編號"""

        self.trade_id_counter += 1
        return self.trade_id_counter

    def get_position_count(self) -> int:
        """取得庫存股票檔數"""
        return len(self.positions)

    def get_first_open_position(self, stock_id: str) -> Optional[StockPosition]:
        """根據股票代號取得庫存中該股票最早開倉的部位（FIFO）"""

        for position in self.positions:
            if position.stock_id == stock_id and not position.is_closed:
                return position
        return None

    def get_last_open_position(self, stock_id: str) -> Optional[StockPosition]:
        """根據股票代號取得庫存中該股票最晚開倉的部位（LIFO）"""

        for position in reversed(self.positions):
            if position.stock_id == stock_id and not position.is_closed:
                return position
        return None

    def remove_positions_by_stock_id(self, stock_id: str) -> None:
        """根據股票代號移除庫存中的部位"""
        self.positions = [
            position for position in self.positions if position.stock_id != stock_id
        ]

    def remove_closed_positions(self) -> None:
        """移除已平倉的部位"""
        self.positions = [
            position for position in self.positions if not position.is_closed
        ]

    def check_has_position(self, stock_id: str) -> bool:
        """檢查指定的股票是否有在庫存"""
        return any(position.stock_id == stock_id for position in self.positions)

    def update_realized_pnl(self):
        """更新已實現損益"""
        self.realized_pnl = sum(
            record.realized_pnl for record in self.trade_records if record.is_closed
        )

    def update_roi(self):
        """更新已實現 ROI (Return On Investment)"""
        self.roi = round(self.realized_pnl / self.init_capital * 100, 2)

    def update_transaction_cost(self):
        """更新交易成本"""

        self.total_commission = sum(record.commission for record in self.trade_records)
        self.total_tax = sum(record.tax for record in self.trade_records)
        self.total_transaction_cost = self.total_commission + self.total_tax

    def update_account_status(self):
        """更新帳戶資訊"""

        self.update_realized_pnl()
        self.update_roi()
        self.update_transaction_cost()
