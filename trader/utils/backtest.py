import datetime
from typing import List, Dict, Tuple, Any
from utils.records import Account, StockQuote, StockTradeEntry
from utils.constant import Commission



""" 
* This section mainly consists of tools used for backtesting.
"""


class Trade:
    """ 回測交易等工具 """
    
    @staticmethod
    def buy(account: Account, stock: StockQuote) -> StockTradeEntry:
        """ 
        - Description: 買入股票
        - Parameters:
            - stock: StockQuote
                目標股票的資訊
            - account: Account
                帳戶資訊
        - Return:
            - position: StockTradeEntry
        """
        
        position: StockTradeEntry = StockTradeEntry()
        stock_value = stock.price * stock.volume
        buy_cost = max(stock_value * Commission.CommRate * Commission.Discount, Commission.MinFee)
        if account.balance >= buy_cost:
            account.balance -= (stock_value + buy_cost)
            position = StockTradeEntry(id=stock.id, code=stock.code, volume=stock.volume, buy_date=stock.date, buy_price=stock.price)
            account.positions.append(position)
            account.stock_trade_history[position.id] = position
        return position
    
    
    @staticmethod
    def sell(account: Account, stock: StockQuote)-> StockTradeEntry:
        """ 
        - Description: 賣出股票
        - Parameters:
            - stock: StockQuote
                目標股票的資訊
            - account: Account
                帳戶資訊
        - Return:
            - position: StockTradeEntry
        """
        
        stock_value = stock.price * stock.volume
        sell_cost = max(stock_value * Commission.CommRate * Commission.Discount, Commission.MinFee) + stock_value * Commission.TaxRate
        account.balance += (stock_value - sell_cost)
        account.positions = [entry for entry in account.positions if entry.id != stock.id]
        account.stock_trade_history[stock.id].sell_date = stock.date
        account.stock_trade_history[stock.id].sell_price = stock.price
        return account.stock_trade_history[stock.id]