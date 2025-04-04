import pandas as pd
import datetime
from typing import List, Dict
from utils.constant import Commission, Scale, PositionType


""" 
* This section mainly serves as utilities for quote representation and event recording in the backtesting phase.
"""


class StockAccount:
    """ 庫存及餘額資訊 """
    
    def __init__(self, init_capital: float=0.0):
        # TODO: add total_cost, realized_pnl, unrealized_pnl, total_equity, cumulative_roi, total_commission 
        
        self.init_capital: float = init_capital                          # 初始本金
        self.balance: float = init_capital                               # 餘額
        self.market_value: float = 0.0                                   # 庫存股票市值
        self.total_equity: float = 0.0                                   # 總資產 = 餘額 + 庫存市值
        self.realized_pnl: float = 0.0                                   # 總已實現損益（profit and loss）
        self.unrealized_pnl: float = 0.0                                 # 總未實現損益
        self.roi: float = 0.0                                            # 帳戶總報酬率
        self.positions: List[StockTradeRecord] = []                      # 持有股票庫存
        self.trade_records: Dict[int, StockTradeRecord] = {}             # 股票歷史交易紀錄

         
    def get_position_count(self):
        """ 取得庫存股票檔數 """    
        return len(self.positions)
    
    
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
        


class TickQuote:
    """  Tick 報價資訊（即時報價） """
    
    def __init__(self, code: str="", time: pd.Timestamp=None,
                 close: float=0.0, volume: int=0,
                 bid_price: float=0.0, bid_volume: int=0, ask_price: float=0.0, ask_volume: int=0,
                 tick_type: int=0
                 ):
        self.code: str = code                               # Stock code
        self.time: pd.Timestamp = time                      # Quote timestamp
        self.close: float = close                           # 成交價
        self.volume: int = volume                           # 成交量
        self.bid_price: float = bid_price                   # 委買價
        self.bid_volume: int = bid_volume                   # 委買量
        self.ask_price: float = ask_price                   # 委賣價
        self.ask_volume: int = ask_volume                   # 委賣量
        self.tick_type = tick_type                          # 內外盤別{1: 外盤, 2: 內盤, 0: 無法判定}


class StockQuote:
    """ 個股報價資訊 """
    
    def __init__(self, id: int=0, code: str="", scale: Scale=None, date: datetime.datetime=None, 
                 cur_price: float=0.0, volume: float=0.0,
                 open: float=0.0, high: float=0.0, low: float=0.0, close: float=0.0,
                 tick: TickQuote=None):
        self.id: int = id                                   # Quote id
        self.code: str = code                               # Stock code
        self.scale: Scale = scale                           # Quote scale (DAY or TICK or ALL)
        self.date: datetime.datetime = date                 # Current date
        self.cur_price: float = cur_price                   # Current price
        self.volume: int = volume                           # order's volume
        self.open: float = open                             # Open price
        self.high: float = high                             # High price
        self.low: float = low                               # Low price
        self.close: float = close                           # Close price
        self.tick_quote: TickQuote = tick                   # tick quote data


class StockOrder:
    """ 個股買賣的訂單 """
    
    def __init__(self, id: int=0, code: str="", date: datetime.datetime=None,
                 price: float=0.0, volume: float=0.0, position_type: PositionType=None):
        self.id: int = id                                   # 每一筆買入就是一個id
        self.code: str = code                               # 股票代號
        self.date: datetime.datetime = date                 # 交易日期（Tick會是Timestamp）
        self.price: float = price                           # 交易價位
        self.volume: float = volume                         # 交易數量
        self.position_type: PositionType = position_type    # 持倉方向（Long or Short）
    

class StockTradeRecord:
    """ 單筆股票交易紀錄 """
    
    def __init__(self, id: int=0, is_closed: bool=False, code: str="", date: datetime.datetime=None, 
                 volume: float=0.0, buy_price: float=0.0, sell_price: float=0.0, 
                 position_type: PositionType=None, position_value: float=0.0,
                 commission: float=0.0, tax: float=0.0,
                 realized_pnl: float=0.0, roi: float=0.0):
        self.id: int = id                                    # 每一筆買入就是一個id
        self.is_closed: bool = is_closed                     # 是否已經平倉
        self.code: str = code                                # 股票代號
        self.date: datetime.datetime = date                  # 交易日期（Tick會是Timestamp）
        self.volume: float = volume                          # 交易股數
        self.buy_price: float = buy_price                    # 買入價位
        self.sell_price: float = sell_price                  # 賣出價位
        self.position_type: PositionType = position_type     # 持倉方向（Long or Short）
        self.position_value: float = position_value          # 股票市值（目前是買入才有）（未扣除手續費及交易稅等摩擦成本）
        self.commission: float = commission                  # 交易手續費
        self.tax: float = tax                                # 交易稅
        self.friction_cost: float = 0.0
        self.realized_pnl: float = realized_pnl              # 已實現損益
        self.roi: float = roi                                # 報酬率