import sys
import os
from pathlib import Path
import requests
import numpy as np
import pandas as pd
import datetime
from typing import List, Dict, Tuple, Any
sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import (Data, Stock, Commission, Market, Scale, 
                   PositionType, Account, TickQuote, StockQuote, 
                   StockTradeEntry)
from scripts import Strategy


""" 
* This section mainly consists of tools used for backtesting.
"""


class Backtester:
    """ 
    Backtest Framework
    - Time Interval：
        1. Ticks
        2. Daily price
    """
    
    def __init__(self):
        """ === Strategy & Account information === """
        self.strategy: Strategy = Strategy()                                    # 欲回測的策略
        self.account: Account = Account(self.strategy.capital)                  # 虛擬帳戶資訊
        
        """ === Datasets === """
        self.data: Data = Data()
        self.QXData: Data = None
        self.tick: Data = None
        self.chip: Data = None
        
        """ === Backtest parameters === """
        self.scale: str = self.strategy.scale                                   # 回測 KBar 級別
        self.max_positions: int = self.strategy.max_positions                   # 最大持倉檔數
        self.start_date: datetime.date = self.strategy.start_date               # 回測起始日
        self.end_date: datetime.date = self.strategy.end_date                   # 回測結束日
    
    
    def load_datasets(self):
        """ 從資料庫取得資料 """
        
        self.chip = self.data.Chip
        if self.scale == Scale.TICK:
            self.tick = self.data.Tick
        elif self.scale == Scale.DAY:
            self.QXData = self.data.QXData
        elif self.scale == Scale.ALL:
            self.tick = self.data.Tick
            self.QXData = self.data.QXData
    
    
    # TODO: Method 前置操作(ex: 先篩選掉不需要訂閱的股票)
    
    def buy(self, stock: StockQuote, buy_price: float, buy_volume: int) -> StockTradeEntry:
        """ 
        - Description: 買入股票
        - Parameters:
            - stock: StockQuote
                目標股票的報價資訊
            - buy_price: float
                買入價位
            - buy_volume: float
                買入股數
        - Return:
            - position: StockTradeEntry
        """
        
        position: StockTradeEntry = None
        if stock.scale == Scale.DAY:
            stock_value = buy_price * buy_volume * 1000
            buy_cost, _ = Stock.get_friction_cost(buy_price=buy_price, volume=buy_volume)
            if self.account.balance >= buy_cost:
                self.account.balance -= (stock_value + buy_cost)
                position = StockTradeEntry(id=stock.id, code=stock.code, date=stock.date,
                                           volume=buy_volume, buy_price=buy_price, 
                                           position_type=PositionType.LONG, position_value=stock_value)
                self.account.positions.append(position)
                self.account.stock_trade_history[position.id] = position
        
        elif stock.scale == Scale.TICK:
            pass
        return position
    
    def sell(self, stock: StockQuote, sell_price: float, sell_volume: int) -> StockTradeEntry:
        """ 
        - Description: 賣出股票
        - Parameters:
            - stock: StockQuote
                目標股票的報價資訊
            - sell_price: float
                賣出價位
            - sell_volume: float
                賣出股數
        - Return:
            - position: StockTradeEntry
        """
        
        position: StockTradeEntry = None
        if stock.scale == Scale.DAY:
            stock_value = sell_price * sell_volume * 1000
            _, sell_cost = Stock.get_friction_cost(sell_price=sell_price, volume=sell_volume)
            # 每一筆買入都記錄一個 id，因此這邊只會刪除對應到買入的 id
            self.account.positions = [entry for entry in self.account.positions if entry.id != stock.id]
            position = self.account.stock_trade_history.get(stock.id)
            if position:
                position.date = stock.date
                position.sell_price = sell_price
                position.profit = Stock.get_net_profit(position.buy_price, position.sell_price, position.volume)
                position.ROI = Stock.get_roi(position.buy_price, position.sell_price, position.volume)
                self.account.balance += (stock_value - sell_cost)
                self.account.stock_trade_history[stock.id] = position
    
            elif stock.scale == Scale.TICK:
                pass
            return position
            
            
    # TODO: Method 判斷買入賣出的量
    
        
    def run(self):
        """ 執行 Backtest (目前只有全tick回測) """
        
        print(f"* Start backtesting {self.strategy.strategy_name} strategy...")
        
        # load backtest dataset
        self.load_datasets()
        
        id: int = 0 # Trade id
        cur_date = self.start_date
        
        while cur_date <= self.end_date:
            print(f"--- {cur_date.strftime('%Y/%m/%d')} ---")
            
            if self.scale == Scale.TICK:
                ticks = self.tick.get_ordered_ticks(cur_date, cur_date)
                
                for tick in ticks.itertuples(index=False):
                    id += 1
                    # TODO: volume 是自己要買的量
                    tick_quote = TickQuote(code=tick.stock_id, time=tick.time, 
                                           close=tick.close, volume=1,
                                           bid_price=tick.bid_price, bid_volume=tick.bid_volume,
                                           ask_price=tick.ask_price, ask_volume=tick.ask_volume,
                                           tick_type=tick.tick_type)
                    stock_quote = StockQuote(id=id, code=tick.stock_id, scale=self.scale, date=cur_date,
                                             cur_price=tick.close, volume=1,
                                             tick=tick_quote)
                    
                    # TODO: FULL-TICK Backtest
            
            
            
            cur_date += datetime.timedelta(days=1) 