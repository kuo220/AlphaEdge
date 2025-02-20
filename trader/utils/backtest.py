import datetime
from typing import List, Dict, Tuple, Any
from trader.utils.records import Account, StockQuote, StockTradeEntry
from utils.constant import Commission



""" 
* This section mainly consists of tools used for backtesting.
"""


class Trade:
    """ 回測交易等工具 """
    
    @staticmethod
    def buy(stock: StockQuote, account: Account) -> StockTradeEntry:
        """ 
        - Description: 買入股票
        - Parameters:
            - stock: StockQuote
                目標股票的資訊
            - account: Account
                帳戶資訊
        - Return:
            - entry: StockTradeEntry
        """
        
        entry: StockTradeEntry = StockTradeEntry()
        stock_value = stock.price * stock.volume
        buy_cost = max(stock_value * Commission.CommRate * Commission.Discount, Commission.MinFee)
        if account.balance >= buy_cost:
            account.balance -= (stock_value + buy_cost)
            entry = StockTradeEntry(id=stock.id, code=stock.code, volume=stock.volume, buy_date=stock.date, buy_price=stock.price)
            account.positions.append(entry)
        return entry
    
    
    @staticmethod
    def sell(stock: StockQuote, account: Account)-> StockTradeEntry:
        """ 
        - Description: 賣入股票
        - Parameters:
            - stock: StockQuote
                目標股票的資訊
            - account: Account
                帳戶資訊
        - Return:
            - entry: StockTradeEntry
        """
        
        stock_value = stock.price * stock.volume
        sell_cost = max(stock_value * Commission.CommRate * Commission.Discount, Commission.MinFee) + stock_value * Commission.TaxRate
        account.balance += (stock_value - sell_cost)
        account.positions = [entry for entry in account.positions if entry.id != stock.id]
        entry = StockTradeEntry(id=stock.id, code=stock.code, volume=stock.volume, sell_date=stock.date, sell_price=stock.price)
        return entry