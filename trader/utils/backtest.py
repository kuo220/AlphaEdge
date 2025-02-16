import datetime
from typing import List, Dict, Tuple, Any
from utils.constant import Commission


""" 
* This section mainly consists of tools used for backtesting.
"""


class TradeRecord:
    """ 單筆交易紀錄 """
    
    def __init__(self, code: str="", volume: float=0.0,
                 buy_date: datetime.date=None, buy_price: float=0.0, 
                 sell_date: datetime.date=None, sell_price: float=0.0, 
                 profit: float=0.0, roi: float=0.0):
        self.code = code
        self.volume = volume
        self.buy_date = buy_date
        self.buy_price = buy_price
        self.sell_date = sell_date
        self.sell_price = sell_price
        self.profit = profit
        self.ROI = roi


class Stock:
    """ 個股資訊 """
    
    def __init__(self, code: str="", date: datetime.date=None, 
                 price: float=0.0, volume: float=0.0):
        self.code = code
        self.date = date
        self.price = price
        self.volume = price


class Account:
    """ 帳戶資訊 """
    
    def __init__(self, balance: float=0.0):
        self.balance = balance
    
    
class Trade:
    """ 回測交易等工具 """
    
    @staticmethod
    def buy(stock: Stock, account: Account) -> TradeRecord:
        """ 
        - Description: 買入股票
        - Parameters:
            - stock: Stock
                目標股票的資訊
            - account: Account
                帳戶資訊
        - Return:
            - record: TradeRecord
        """
        
        record: TradeRecord = TradeRecord()
        stock_cost = stock.price * stock.volume
        buy_cost = max(stock_cost * Commission.CommRate * Commission.Discount, Commission.MinFee)
        if account.balance >= buy_cost:
            account.balance -= (stock_cost + buy_cost)
            record = TradeRecord(code=stock.code, volume=stock.volume, buy_date=stock.date, buy_price=stock.price)    
        return record
    
    
    @staticmethod
    def sell(stock: Stock, account: Account)-> TradeRecord:
        """ 
        - Description: 賣入股票
        - Parameters:
            - stock: Dict[str, Any]
                目標股票的資訊
            - account: Dict[str, Any]
                帳戶資訊
        - Return:
            - record: TradeRecord
        """
        record: TradeRecord = TradeRecord()
        stock_cost = stock.price * stock.volume
        sell_cost = max(stock_cost * Commission.CommRate * Commission.Discount, Commission.MinFee) + stock_cost * Commission.TaxRate
        account.balance += (stock_cost - sell_cost)
        record = TradeRecord(code=stock.code, volume=stock.volume, sell_date=stock.date, sell_price=stock.price)
        return record