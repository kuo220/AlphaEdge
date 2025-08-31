import datetime
from typing import Dict, List, Optional, Union

import pandas as pd

from trader.utils import Commission, PositionType, Scale

from .record import StockTradeRecord

"""
This module defines the StockAccount class, which manages account-level state in backtesting,
including positions, balances, realized PnL, and transaction costs.
"""


class StockAccount:
    """庫存及餘額資訊"""

    def __init__(self, init_capital: float = 0.0):
        # Initial Setup
        self.init_capital: float = init_capital  # 初始本金

        # Account Balances
        self.balance: float = init_capital  # 餘額
        self.market_value: float = 0.0  # 庫存股票市值
        self.total_equity: float = 0.0  # 總資產 = 餘額 + 庫存市值

        # Account Performance
        self.realized_pnl: float = 0.0  # 總已實現損益（profit and loss）
        self.roi: float = 0.0  # 帳戶總報酬率

        # Transaction Costs
        self.total_commission: float = 0.0  # 總手續費
        self.total_tax: float = 0.0  # 總交易稅
        self.total_transaction_cost: float = 0, 0  # 總交易成本

        # Trade ID
        self.trade_id_counter: int = 0  # 交易編號（每筆交易唯一編號）

        # Positions & Trading History
        self.positions: List[StockTradeRecord] = []  # 持有未平倉的股票庫存
        self.trade_records: Dict[int, StockTradeRecord] = {}  # 股票歷史交易紀錄

    def get_position_count(self) -> int:
        """取得庫存股票檔數"""
        return len(self.positions)

    def get_first_open_position(self, stock_id: str) -> Optional[StockTradeRecord]:
        """根據股票代號取得庫存中該股票最早開倉的部位（FIFO）"""

        for position in self.positions:
            if position.stock_id == stock_id and not position.is_closed:
                return position
        return None

    def get_last_open_position(self, stock_id: str) -> Optional[StockTradeRecord]:
        """根據股票代號取得庫存中該股票最晚開倉的部位（LIFO）"""

        for position in reversed(self.positions):
            if position.stock_id == stock_id and not position.is_closed:
                return position
        return None

    def check_has_position(self, stock_id: str) -> bool:
        """檢查指定的股票是否有在庫存"""
        return any(position.stock_id == stock_id for position in self.positions)

    def update_market_value(self):
        """更新庫存市值（目前只有股票）"""

        self.market_value = 0
        for position in self.positions:
            if position.position_type == PositionType.LONG:
                self.market_value += position.position_value

    def update_total_equity(self):
        """更新總資產"""

        self.update_market_value()
        self.total_equity = self.balance + self.market_value

    def update_realized_pnl(self):
        """更新已實現損益"""
        self.realized_pnl = sum(
            position.realized_pnl for position in self.positions if position.is_closed
        )

    def update_roi(self):
        """更新 ROI(Return On Investment)"""
        return (self.total_equity - self.total_transaction_cost) / self.init_capital - 1

    def update_transaction_cost(self):
        """更新交易成本"""

        self.total_commission = sum(position.commission for position in self.positions)
        self.total_tax = sum(position.tax for position in self.positions)
        self.total_transaction_cost = self.total_commission + self.total_tax

    def update_account_status(self):
        """更新帳戶資訊"""

        self.update_market_value()
        self.update_total_equity()
        self.update_realized_pnl()
        self.update_roi()
        self.update_transaction_cost()
