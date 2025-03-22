import pandas as pd
import datetime
from typing import List, Dict, Tuple, Any
from utils.constant import Commission, Scale, PositionType


""" 
* This section mainly consists of classes used for recording portfolio.
"""


class Account:
    """ 庫存及餘額資訊 """
    
    def __init__(self, balance: float=0.0):
        self.balance: float = balance
        self.positions: List[StockTradeEntry] = []
        self.stock_trade_history: Dict[int, StockTradeEntry] = {}


class TickQuote:
    """  Tick 資訊（即時報價） """
    
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
    """ 個股資訊 """
    
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


class StockTradeEntry:
    """ 單筆股票交易紀錄 """
    
    def __init__(self, id: int=0, code: str="", date: datetime.datetime=None,
                 volume: float=0.0, buy_price: float=0.0, sell_price: float=0.0, 
                 position_type: PositionType=None, position_value: float=0.0, 
                 profit: float=0.0, roi: float=0.0):
        self.id: int = id                                   # 每一筆買入就是一個id
        self.code: str = code                               # 股票代號
        self.date: datetime.datetime = date                 # 交易日期
        self.volume: float = volume                         # 交易股數
        self.buy_price: float = buy_price                   # 買入價位
        self.sell_price: float = sell_price                 # 賣出價位
        self.position_type: PositionType = position_type    # 持倉方向（Long or Short）
        self.position_value: float = position_value         # 股票市值（目前是買入才有）
        self.profit: float = profit                         # 淨獲利
        self.ROI: float = roi                               # 報酬率