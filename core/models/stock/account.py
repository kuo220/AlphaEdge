from typing import Dict, List, Optional

from loguru import logger

from core.models.base.account import BaseAccount
from core.utils import PositionType, Units

from .position import StockPosition
from .record import StockTradeRecord

"""StockAccount: manages account-level state in backtesting (positions, balance, realized PnL, costs)"""


class StockAccount(BaseAccount):
    """
    庫存及餘額資訊

    相對於 BaseAccount 多的是台股信用交易專屬的部分：保證金佔用、空頭曝險，
    以及把借券費與融券利息納入的總交易成本口徑。
    """

    def __init__(self, init_capital: float = 0.0):
        super().__init__(init_capital)

        # Short Positions
        self.margin_used: float = 0.0  # 放空部位佔用的保證金總額

        # Positions & Trading History（型別窄化為台股專屬 model）
        self.positions: List[StockPosition] = []  # 持有未平倉的股票庫存
        self.trade_records: List[StockTradeRecord] = []  # 股票歷史交易紀錄

    # === stock_id 關鍵字相容層 ===
    # 引擎內部一律以 symbol 為鍵，但既有策略與測試沿用 stock_id，故保留具名別名。
    def get_first_open_position(self, stock_id: str) -> Optional[StockPosition]:
        """根據股票代號取得庫存中該股票最早開倉的部位（FIFO）"""

        return super().get_first_open_position(symbol=stock_id)

    def get_last_open_position(self, stock_id: str) -> Optional[StockPosition]:
        """根據股票代號取得庫存中該股票最晚開倉的部位（LIFO）"""

        return super().get_last_open_position(symbol=stock_id)

    def remove_positions_by_stock_id(self, stock_id: str) -> None:
        """根據股票代號移除庫存中的部位"""

        self.remove_positions_by_symbol(symbol=stock_id)

    def get_positions(
        self,
        stock_id: Optional[str] = None,
        position_type: Optional[PositionType] = None,
    ) -> List[StockPosition]:
        """取得庫存中符合條件的未平倉部位；參數為 None 表示不限制該條件"""

        return super().get_positions(symbol=stock_id, position_type=position_type)

    def check_has_position(
        self,
        stock_id: str,
        position_type: Optional[PositionType] = None,
    ) -> bool:
        """檢查指定的股票是否有在庫存；position_type 為 None 時不分方向（維持既有行為）"""

        return super().check_has_position(symbol=stock_id, position_type=position_type)

    # === 台股信用交易專屬 ===
    def get_short_market_value(
        self,
        prices: Dict[str, float],
        prev_close: Optional[Dict[str, float]] = None,
    ) -> float:
        """
        - Description:
            依傳入的價格計算所有放空部位的市值（算維持率與空頭曝險用）

            **停牌時退回前收，而不是開倉價**（健檢 F-021）：開倉價是這檔停牌前
            可能已經漲了好幾成的**起點**，拿它當市值會把維持率算得比實際好看
            ——而停牌正是最需要正確維持率的時候。取價順序與
            `TwStockSettlementModel.get_mark_price()` 一致：當日價 → 前收 → 開倉價。
        - Parameters:
            - prices: Dict[str, float]
                當日價格
            - prev_close: Optional[Dict[str, float]]
                前一交易日收盤價；None 時直接退回開倉價（並記 warning）
        - Return:
            - float
                所有放空部位的市值
        """

        prev_close = prev_close or {}
        total: float = 0.0

        for position in self.get_positions(position_type=PositionType.SHORT):
            price: Optional[float] = prices.get(position.stock_id)
            if not price:
                price = prev_close.get(position.stock_id)
                if not price:
                    logger.warning(
                        f"[Short Market Value] {position.stock_id} 當日與前一交易日"
                        f"皆無報價，退回開倉價 {position.price} 計算市值"
                    )
                    price = position.price

            total += price * position.volume * Units.LOT.value

        return total

    def update_transaction_cost(self) -> None:
        """更新交易成本"""

        self.total_commission = sum(record.commission for record in self.trade_records)
        self.total_tax = sum(record.tax for record in self.trade_records)

        # 放空的借券費與股利補償為支出、融券利息為收入，一併計入總交易成本
        # （與 `StockTradeRecord.transaction_cost` 同一口徑，兩邊須一致）
        total_borrow_fee: float = sum(
            record.borrow_fee for record in self.trade_records
        )
        total_interest: float = sum(record.interest for record in self.trade_records)
        total_dividend_compensation: float = sum(
            record.dividend_compensation for record in self.trade_records
        )

        self.total_transaction_cost = (
            self.total_commission
            + self.total_tax
            + total_borrow_fee
            + total_dividend_compensation
            - total_interest
        )
