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
            - portfolio: Portfolio
                帳戶資訊
        - Return:
            - record: StockTradeEntry
        """
        
        record: StockTradeEntry = StockTradeEntry()
        stock_cost = stock.price * stock.volume
        buy_cost = max(stock_cost * Commission.CommRate * Commission.Discount, Commission.MinFee)
        if account.balance >= buy_cost:
            account.balance -= (stock_cost + buy_cost)
            record = StockTradeEntry(code=stock.code, volume=stock.volume, buy_date=stock.date, buy_price=stock.price)    
        return record
    
    
    @staticmethod
    def sell(stock: StockQuote, account: Account)-> StockTradeEntry:
        """ 
        - Description: 賣入股票
        - Parameters:
            - stock: StockQuote
                目標股票的資訊
            - portfolio: Portfolio
                帳戶資訊
        - Return:
            - record: StockTradeEntry
        """
        
        stock_cost = stock.price * stock.volume
        sell_cost = max(stock_cost * Commission.CommRate * Commission.Discount, Commission.MinFee) + stock_cost * Commission.TaxRate
        account.balance += (stock_cost - sell_cost)
        record = StockTradeEntry(code=stock.code, volume=stock.volume, sell_date=stock.date, sell_price=stock.price)
        return record