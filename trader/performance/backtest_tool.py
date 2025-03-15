import sys
import os
from pathlib import Path
import requests
import numpy as np
import pandas as pd
import datetime
from typing import List, Dict, Tuple, Any
sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import Data, Stock, Commission, Account, StockQuote, StockTradeEntry
from scripts import Strategy


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
        stock_value = stock.cur_price * stock.volume
        buy_cost = max(stock_value * Commission.CommRate * Commission.Discount, Commission.MinFee)
        if account.balance >= buy_cost:
            account.balance -= (stock_value + buy_cost)
            position = StockTradeEntry(id=stock.id, code=stock.code, volume=stock.volume, buy_date=stock.date, buy_price=stock.cur_price)
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
        
        stock_value = stock.cur_price * stock.volume
        sell_cost = max(stock_value * Commission.CommRate * Commission.Discount, Commission.MinFee) + stock_value * Commission.TaxRate
        
        # 每一筆買入都記錄一個 id，因此這邊只會刪除對應到買入的 id
        account.positions = [entry for entry in account.positions if entry.id != stock.id]
        position = account.stock_trade_history.get(stock.id)
        if position:
            position.sell_date = stock.date
            position.sell_price = stock.cur_price
            position.profit = Stock.get_net_profit(position.buy_price, position.sell_price, position.volume)
            position.ROI = Stock.get_roi(position.buy_price, position.sell_price, position.volume)
            account.balance += (stock_value - sell_cost)
            account.stock_trade_history[stock.id] = position
        return position
    
    
class BackTester:
    """ Backtest Framework
    - Time Interval：
        1. Ticks
        2. Daily price
    """
    
    def __init__(self):
        self.strategy: Strategy = Strategy()
        self.account: Account = Account(self.strategy.capital)
        self.data: Data = Data()
        
        self.scale: str = self.strategy.scale
        self.max_positions: int = self.strategy.max_positions
        self.start_date: datetime.date = self.strategy.start_date
        self.end_date: datetime.date = self.strategy.end_date
        

    def simulate_market_ticks(self):
        """ 模擬盤中 tick-by-tick 報價（適用tick回測）"""
        """ 每次取出一個月份量且排序好的的 ticks """
        pass
        

    def run(self):
        """ 執行 Backtest (目前只有全tick回測) """
        
        print(f"* Start backtesting {self.strategy.strategy_name} strategy...")
        
        # load backtest dataset
        data = self.data.QXData
        tick = self.data.Tick
        chip = self.data.Chip
        
        cur_date = self.start_date
        
        while cur_date <= self.end_date:
            print(f"--- {cur_date.strftime('%Y/%m/%d')} ---")
            cur_date += datetime.timedelta(days=1)