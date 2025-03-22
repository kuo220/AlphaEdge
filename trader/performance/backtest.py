import sys
import os
from pathlib import Path
import requests
import numpy as np
import pandas as pd
import datetime
from typing import List, Dict, Tuple, Any
sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import (Data, StockTool, Commission, Market, Scale, 
                   PositionType, Account, TickQuote, StockQuote, 
                   StockOrder, StockTradeEntry)
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
        
        """ === Backtest Parameters === """
        self.scale: str = self.strategy.scale                                   # 回測 KBar 級別
        self.max_positions: int = self.strategy.max_positions                   # 最大持倉檔數
        self.start_date: datetime.date = self.strategy.start_date               # 回測起始日
        self.cur_date: datetime.date = self.strategy.start_date                 # 回測當前日
        self.end_date: datetime.date = self.strategy.end_date                   # 回測結束日
        
        """ === Trading Record """
        self.entry_id: int = 0                                                  # 單筆交易ID
        
    
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
    
    
    def buy(self, stock: StockOrder) -> StockTradeEntry:
        """ 
        - Description: 買入股票
        - Parameters:
            - stock: StockOrder
                目標股票的訂單資訊
        - Return:
            - position: StockTradeEntry
        """
        
        position: StockTradeEntry = None
        
        stock_value = stock.price * stock.volume * 1000
        buy_cost, _ = StockTool.get_friction_cost(buy_price=stock.price, volume=stock.volume)
        if self.account.balance >= buy_cost:
            self.account.balance -= (stock_value + buy_cost)
            position = StockTradeEntry(id=stock.id, code=stock.code, date=stock.date,
                                        volume=stock.volume, buy_price=stock.price, 
                                        position_type=PositionType.LONG, position_value=stock_value)
            self.account.positions.append(position)
            self.account.stock_trade_history[position.id] = position
        return position


    def sell(self, stock: StockOrder) -> StockTradeEntry:
        """ 
        - Description: 賣出股票
        - Parameters:
            - stock: StockOrder
                目標股票的訂單資訊
        - Return:
            - position: StockTradeEntry
        """
        
        position: StockTradeEntry = None

        stock_value = stock.price * stock.volume * 1000
        _, sell_cost = StockTool.get_friction_cost(sell_price=stock.price, volume=stock.volume)
        # 每一筆買入都記錄一個 id，因此這邊只會刪除對應到買入的 id
        self.account.positions = [entry for entry in self.account.positions if entry.id != stock.id]
        position = self.account.stock_trade_history.get(stock.id)
        if position:
            position.date = stock.date
            position.sell_price = stock.price
            position.profit = StockTool.get_net_profit(position.buy_price, position.sell_price, position.volume)
            position.ROI = StockTool.get_roi(position.buy_price, position.sell_price, position.volume)
            self.account.balance += (stock_value - sell_cost)
            self.account.stock_trade_history[stock.id] = position

            return position
    
    
    # TODO: Method => run tick backtest
    def run_tick_backtest(self):
        """ Tick 級別的回測架構 """
        
        ticks = self.tick.get_ordered_ticks(self.cur_date, self.cur_date)
        
        for tick in ticks.itertuples(index=False):
            # TODO: volume 是自己要買的量
            
            self.entry_id += 1
            tick_quote = TickQuote(code=tick.stock_id, time=tick.time, 
                                    close=tick.close, volume=1,
                                    bid_price=tick.bid_price, bid_volume=tick.bid_volume,
                                    ask_price=tick.ask_price, ask_volume=tick.ask_volume,
                                    tick_type=tick.tick_type)
            
            
            stock_quote = StockQuote(id=self.entry_id, code=tick.stock_id, scale=self.scale, 
                                     date=self.cur_date, tick=tick_quote)
            
            # TODO: FULL-TICK Backtest(maybe another function)
    
    
    def run_day_backtest(self):
        pass
    
    
    def run_all_backtest(self):
        pass
    
        
    def run(self):
        """ 執行 Backtest (目前只有全tick回測) """
        
        print(f"* Start backtesting {self.strategy.strategy_name} strategy...")
        
        # load backtest dataset
        self.load_datasets()
        
        
        while self.cur_date <= self.end_date:
            print(f"--- {self.cur_date.strftime('%Y/%m/%d')} ---")
            
            if self.scale == Scale.TICK:
                self.run_tick_backtest()

            elif self.scale == Scale.DAY:
                self.run_day_backtest
            
            elif self.scale == Scale.ALL:
                self.run_all_backtest()
            
            self.cur_date += datetime.timedelta(days=1) 