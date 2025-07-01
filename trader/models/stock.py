import datetime
from typing import Dict, List, Optional, Union
import pandas as pd

from trader.utils import Commission, PositionType, Scale


"""
* This section mainly serves as utilities for quote representation and event recording in the backtesting phase.
"""


class TickQuote:
    """  Tick 報價資訊（即時報價） """
    
    def __init__(
        self,
        code: str="",
        time: pd.Timestamp=None,
        close: float=0.0,
        volume: int=0,
        bid_price: float=0.0,
        bid_volume: int=0,
        ask_price: float=0.0,
        ask_volume: int=0,
        tick_type: int=0
    ):
        # Basic Info
        self.code: str = code                               # Stock code
        self.time: pd.Timestamp = time                      # Quote timestamp
        
        # Current Price & Volume
        self.close: float = close                           # 成交價
        self.volume: float = volume                         # 成交量（Unit: Lot）
        
        # Bid & Ask Price & Volume
        self.bid_price: float = bid_price                   # 委買價
        self.bid_volume: int = bid_volume                   # 委買量
        self.ask_price: float = ask_price                   # 委賣價
        self.ask_volume: int = ask_volume                   # 委賣量
        
        # Tick Info
        self.tick_type: int = tick_type                     # 內外盤別{1: 外盤, 2: 內盤, 0: 無法判定}


class StockQuote:
    """ 個股報價資訊 """
    
    def __init__(
        self,
        code: str="",
        scale: Scale=None,
        date: datetime.datetime=None,
        cur_price: float=0.0,
        volume: float=0.0,
        open: float=0.0,
        high: float=0.0,
        low: float=0.0,
        close: float=0.0,
        tick: TickQuote=None
    ):
        # Basic Info
        self.code: str = code                                            # Stock code
        self.scale: Scale = scale                                        # Quote scale (DAY or TICK or ALL)
        self.date: Union[datetime.date, datetime.datetime] = date        # Current date
        
        # Current Price & Volume
        self.cur_price: float = cur_price                                # Current price
        self.volume: float = volume                                      # order's volume (Unit: Lots)
        
        # OHLC Info
        self.open: float = open                                          # Open price
        self.high: float = high                                          # High price
        self.low: float = low                                            # Low price
        self.close: float = close                                        # Close price
        
        # Tick Data
        self.tick_quote: TickQuote = tick                                # tick quote data


class StockOrder:
    """ 個股買賣的訂單 """
    
    def __init__(
        self,
        code: str="",
        date: datetime.datetime=None,
        price: float=0.0,
        volume: float=0.0,
        position_type: PositionType=PositionType.LONG
     ):
        # Basic Info
        self.code: str = code                               # 股票代號
        self.date: datetime.datetime = date                 # 交易日期（Tick會是Timestamp）
        
        # Order Info
        self.price: float = price                           # 交易價位
        self.volume: float = volume                         # 交易數量（Unit: Lot）
        self.position_type: PositionType = position_type    # 持倉方向（Long or Short）
        

class StockTradeRecord:
    """ 單筆股票交易紀錄 """
    
    def __init__(
        self,
        id: int=0,
        code: str="",
        date: datetime.datetime=None,
        is_closed: bool=False,
        position_type: PositionType=PositionType.LONG,
        buy_price: float=0.0,
        sell_price: float=0.0,
        volume: float=0.0,
        commission: float=0.0,
        tax: float=0.0,
        transaction_cost: float=0.0,
        position_value: float=0.0,
        realized_pnl: float=0.0,
        roi: float=0.0
    ):

        # Basic Info
        self.id: int = id                                                # 每一筆買入就是一個id
        self.code: str = code                                            # 股票代號
        self.date: Union[datetime.date, datetime.datetime] = date        # 交易日期（Tick會是Timestamp）
        
        # Position Status
        self.is_closed: bool = is_closed                     # 是否已經平倉
        self.position_type: PositionType = position_type     # 持倉方向（Long or Short）
        
        # Price & Quantity
        self.buy_price: float = buy_price                    # 買入價位
        self.sell_price: float = sell_price                  # 賣出價位
        self.volume: float = volume                          # 交易股數
        
        # Transaction Costs
        self.commission: float = commission                  # 交易手續費
        self.tax: float = tax                                # 交易稅
        self.transaction_cost: float = transaction_cost      # 總交易成本 = 交易手續費 + 交易稅
        
        # Transaction Performance
        self.position_value: float = position_value          # 股票市值（目前是買入才有）（未扣除手續費及交易稅等摩擦成本）
        self.realized_pnl: float = realized_pnl              # 已實現損益
        self.roi: float = roi                                # 報酬率
        
        
class StockAccount:
    """ 庫存及餘額資訊 """
    
    def __init__(self, init_capital: float=0.0):
        # Initial Setup
        self.init_capital: float = init_capital                          # 初始本金

        # Account Balances
        self.balance: float = init_capital                               # 餘額
        self.market_value: float = 0.0                                   # 庫存股票市值
        self.total_equity: float = 0.0                                   # 總資產 = 餘額 + 庫存市值
        
        # Account Performance
        self.realized_pnl: float = 0.0                                   # 總已實現損益（profit and loss）
        self.roi: float = 0.0                                            # 帳戶總報酬率
        
        # Transaction Costs
        self.total_commission: float = 0.0                               # 總手續費
        self.total_tax: float = 0.0                                      # 總交易稅
        self.total_transaction_cost: float = 0,0                         # 總交易成本
        
        # Trade ID
        self.trade_id_counter: int = 0                                   # 交易編號（每筆交易唯一編號）
        
        # Positions & Trading History
        self.positions: List[StockTradeRecord] = []                      # 持有未平倉的股票庫存
        self.trade_records: Dict[int, StockTradeRecord] = {}             # 股票歷史交易紀錄


    def get_position_count(self) -> int:
        """ 取得庫存股票檔數 """
        return len(self.positions)
    
    
    def get_first_open_position(self, code: str) -> Optional[StockTradeRecord]:
        """ 根據股票代號取得庫存中該股票最早開倉的部位（FIFO）"""
        
        for position in self.positions:
            if position.code == code and not position.is_closed:
                return position
        return None
        

    def get_last_open_position(self, code: str) -> Optional[StockTradeRecord]:
        """ 根據股票代號取得庫存中該股票最晚開倉的部位（LIFO） """
        
        for position in reversed(self.positions):
            if position.code == code and not position.is_closed:
                return position
        return None
    
    
    def check_has_position(self, code: str) -> bool:
        """ 檢查指定的股票是否有在庫存 """
        return any(position.code == code for position in self.positions)


    def update_market_value(self):
        """ 更新庫存市值（目前只有股票） """
        
        self.market_value = 0
        for position in self.positions:
            if position.position_type == PositionType.LONG:
                self.market_value += position.position_value
                
    
    def update_total_equity(self):
        """ 更新總資產 """
        
        self.update_market_value()
        self.total_equity = self.balance + self.market_value
    

    def update_realized_pnl(self):
        """ 更新已實現損益 """
        self.realized_pnl = sum(position.realized_pnl for position in self.positions if position.is_closed)
    
    
    def update_roi(self):
        """ 更新 ROI(Return On Investment) """
        return (self.total_equity - self.total_transaction_cost) / self.init_capital - 1
    
    
    def update_transaction_cost(self):
        """ 更新交易成本 """
        
        self.total_commission = sum(position.commission for position in self.positions)
        self.total_tax = sum(position.tax for position in self.positions)
        self.total_transaction_cost = self.total_commission + self.total_tax
    
    
    def update_account_status(self):
        """ 更新帳戶資訊 """
        
        self.update_market_value()
        self.update_total_equity()
        self.update_realized_pnl()
        self.update_roi()
        self.update_transaction_cost()