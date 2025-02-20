import datetime
from typing import List, Dict, Tuple, Any
from utils.constant import Commission


""" 
* This section mainly consists of classes used for recording portfolio.
"""


class Account:
    """ 庫存及餘額資訊 """
    
    def __init__(self, balance: float=0.0):
        self.balance: float = balance
        self.position: List[StockTradeEntry] = []
        self.stock_trade_history: StockTradeHistory = StockTradeHistory()


class StockQuote:
    """ 個股資訊 """
    
    def __init__(self, code: str="", date: datetime.datetime=None, 
                 price: float=0.0, volume: float=0.0):
        self.code: str = code
        self.date: datetime.datetime = date
        self.price: float = price
        self.volume: float = volume


class StockTradeEntry:
    """ 單筆股票交易紀錄 """
    
    def __init__(self, id: int=0, code: str="", volume: float=0.0,
                 buy_date: datetime.datetime=None, buy_price: float=0.0, 
                 sell_date: datetime.datetime=None, sell_price: float=0.0, 
                 profit: float=0.0, roi: float=0.0):
        self.id: int = id
        self.code: str = code
        self.volume: float = volume
        self.buy_date: datetime.datetime = buy_date
        self.buy_price: float = buy_price
        self.sell_date: datetime.datetime = sell_date
        self.sell_price: float = sell_price
        self.profit: float = profit
        self.roi: float = roi
        
        
class StockTradeHistory:
    """ 每筆股票交易紀錄 """
    
    def __init__(self):
        self.trade_records: Dict[int, StockTradeEntry] = {} # key: id, value: StockTradeEntry