import sys
import numpy as np
from pathlib import Path
import datetime
import shioaji as sj
from typing import Tuple, List, Optional

from .time import TimeUtils
from .constant import Commission


"""
instrument.py

Utility functions for asset trading calculations, including support for stocks, futures, and options.

Features:
- Retrieve close prices and price changes (via Shioaji API)
- Calculate commission, tax, net profit, and ROI
- Check if the market was open on a given date

Designed for use in backtesting and trading performance analysis.
"""


class StockUtils:
    """Stock Related Tools"""

    @staticmethod
    def get_close_price(
        api: sj.Shioaji,
        stock_id: str,
        date: datetime.date,
    ) -> float:
        """Shioaji: 取得指定股票在特定日期的收盤價"""

        tick: sj.Shioaji.ticks = api.ticks(
            contract=api.Contracts.Stocks[stock_id],
            date=date.strftime("%Y-%m-%d"),
            query_type=sj.constant.TicksQueryType.LastCount,
            last_cnt=1,
        )

        return tick.close[0] if len(tick.close) != 0 else np.nan

    @staticmethod
    def get_price_chg(
        api: sj.Shioaji,
        stock_id: str,
        date: datetime.date,
    ) -> float:
        """Shioaji: 取得指定股票在指定日期的漲跌幅"""

        # 取得前一個交易日的日期
        last_trading_date: datetime.date = TimeUtils.get_last_trading_date(api, date)

        # 計算指定交易日股票的漲幅
        cur_close_price: float = StockUtils.get_close_price(api, stock_id, date)
        prev_close_price: float = StockUtils.get_close_price(
            api, stock_id, last_trading_date
        )

        # if cur_close_price or prev_close_price is np.nan, then function will return np.nan
        return round((cur_close_price / prev_close_price - 1) * 100, 2)

    @staticmethod
    def calculate_transaction_commission(price: float, volume: float) -> float:
        """計算股票買賣時的手續費"""
        """
        For long position, the commission costs:
            - buy fee (券買手續費 = 成交價 x 成交股數 x 手續費率 x discount)
            - sell fee (券賣手續費 = 成交價 x 成交股數 x 手續費率 x discount)
        """
        return max(
            price * volume * Commission.CommRate * Commission.Discount,
            Commission.MinFee,
        )

    @staticmethod
    def calculate_transaction_tax(price: float, volume: float) -> float:
        """計算股票賣出時的交易稅"""
        """
        For long position, the tax cost:
            - sell tax (券賣證交稅 = 成交價 x 成交股數 x 證交稅率)
        """
        return price * volume * Commission.TaxRate

    @staticmethod
    def calculate_transaction_cost(
        buy_price: float,
        sell_price: float,
        volume: float,
    ) -> Tuple[float, float]:
        """計算股票買賣的手續費、交易稅等摩擦成本"""
        """
        For long position, the transaction costs should contains:
            - buy fee (券買手續費 = 成交價 x 成交股數 x 手續費率 x discount)
            - sell fee (券賣手續費 = 成交價 x 成交股數 x 手續費率 x discount)
            - sell tax (券賣證交稅 = 成交價 x 成交股數 x 證交稅率)
        """

        # 買入 & 賣出的交易成本
        buy_transaction_cost: float = StockUtils.calculate_transaction_commission(
            buy_price, volume
        )
        sell_transaction_cost: float = StockUtils.calculate_transaction_commission(
            sell_price, volume
        ) + StockUtils.calculate_transaction_tax(sell_price, volume)
        return (buy_transaction_cost, sell_transaction_cost)

    @staticmethod
    def calculate_net_profit(
        buy_price: float,
        sell_price: float,
        volume: float,
    ) -> float:
        """
        - Description: 計算股票交易的淨收益（扣除手續費和交易稅）（目前只有做多）
        - Parameters:
            - buy_price: float
                股票買入價格
            - sell_price: float
                股票賣出價格
            - volume: float
                股數
        - Return:
            - profit: float
        """

        buy_value: float = buy_price * volume
        sell_value: float = sell_price * volume

        # 買入 & 賣出手續費
        buy_comm, sell_comm = StockUtils.calculate_transaction_cost(
            buy_price, sell_price, volume
        )

        profit: float = (sell_value - buy_value) - (buy_comm + sell_comm)
        return round(profit, 2)

    @staticmethod
    def calculate_roi(
        buy_price: float,
        sell_price: float,
        volume: float,
    ) -> float:
        """
        - Description: 計算股票投資報酬率（ROI）（目前只有做多）
        - Parameters:
            - buy_price: float
                股票買入價格
            - sell_price: float
                股票賣出價格
            - volume: float
                股數
        - Return:
            - roi: float
                投資報酬率（%）
        """

        buy_value: float = buy_price * volume
        buy_comm, _ = StockUtils.calculate_transaction_cost(
            buy_price, sell_price, volume
        )

        # 計算投資成本
        investment_cost: float = buy_value + buy_comm
        if investment_cost == 0:
            return 0.0

        roi: float = (
            StockUtils.calculate_net_profit(buy_price, sell_price, volume)
            / investment_cost
        ) * 100
        return round(roi, 2)

    @staticmethod
    def filter_common_stocks(stock_ids: List[str]) -> List[str]:
        """
        - Description: 過濾出一般股票（排除 ETF、權證等），僅保留 4 位數且在 1001~9958 間的股票代號
        - Parameters:
            - stock_ids: 所有股票代號的 List[str]
        - Return:
            - List[str]：符合條件的一般股票代號清單
        """
        return [
            stock_id
            for stock_id in stock_ids
            if stock_id.isdigit() and len(stock_id) == 4 and 1001 <= int(stock_id) <= 9958
        ]
