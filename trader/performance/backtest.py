import sys
import os
from pathlib import Path
import requests
import numpy as np
import pandas as pd
import datetime
from typing import List, Dict, Tuple, Optional, Any 
sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import (Data, StockTool, Commission, Market, Scale, 
                   PositionType, Units)
from models import (StockAccount, TickQuote, StockQuote, StockOrder, StockTradeRecord)
from strategies.stock import Strategy


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
        self.account: StockAccount = StockAccount(self.strategy.init_capital)    # 虛擬帳戶資訊
        
        """ === Datasets === """
        self.data: Data = Data()                                                
        self.QXData: Data = None                                                # Day price data, Financial data, etc
        self.tick: Data = None                                                  # Ticks data
        self.chip: Data = None                                                  # Chips data
        
        """ === Backtest Parameters === """
        self.scale: str = self.strategy.scale                                   # 回測 KBar 級別
        self.max_positions: int = self.strategy.max_positions                   # 最大持倉檔數
        self.start_date: datetime.date = self.strategy.start_date               # 回測起始日
        self.cur_date: datetime.date = self.strategy.start_date                 # 回測當前日
        self.end_date: datetime.date = self.strategy.end_date                   # 回測結束日
        
    
    def load_datasets(self):
        """ 從資料庫載入資料 """
        
        self.chip = self.data.Chip
        if self.scale == Scale.TICK:
            self.tick = self.data.Tick
        elif self.scale == Scale.DAY:
            self.QXData = self.data.QXData
        elif self.scale == Scale.MIX:
            self.tick = self.data.Tick
            self.QXData = self.data.QXData 
    
    
    def place_open_position(self, stock: StockOrder) -> Optional[StockTradeRecord]:
        """ 
        - Description: 開倉下單股票
        - Parameters:
            - stock: StockOrder
                目標股票的訂單資訊
        - Return:
            - position: StockTradeRecord
        """
        
        position: Optional[StockTradeRecord] = None
        
        position_value = stock.price * stock.volume * Units.LOT
        open_cost = StockTool.calculate_transaction_commission(buy_price=stock.price, volume=stock.volume)
        
        if stock.position_type == PositionType.LONG:
            if self.account.balance >= (position_value + open_cost):
                self.account.trade_id_counter += 1
                self.account.balance -= (position_value + open_cost)
                
                position = StockTradeRecord(id=self.account.trade_id_counter, code=stock.code, date=stock.date,
                                            position_type=stock.position_type,
                                            buy_price=stock.price, volume=stock.volume, 
                                            commission=open_cost, transaction_cost=open_cost,
                                            position_value=position_value)
                
                self.account.positions.append(position)
                self.account.trade_records[position.id] = position

        return position


    def place_close_position(self, stock: StockOrder) -> Optional[StockTradeRecord]:
        """
        - Description: 下單平倉股票
        - Parameters:
            - stock: StockOrder
                目標股票的訂單資訊
        - Return:
            - position: StockTradeRecord
        """

        position_value = stock.price * stock.volume * Units.LOT
        close_cost = StockTool.calculate_transaction_commission(sell_price=stock.price, volume=stock.volume)
        
        # 根據 stock.code 找出庫存中最早買進的該檔股票（FIFO）
        position: Optional[StockTradeRecord] = self.account.get_fifo_position(stock.code)
        
        if position is not None and not position.is_closed:
            if position.position_type == PositionType.LONG:
                position.date = stock.date
                position.is_closed = True
                position.sell_price = stock.price
                position.commission += close_cost
                position.tax = StockTool.calculate_transaction_tax(stock.price, stock.volume)
                position.transaction_cost = position.commission + position.tax
                position.realized_pnl = StockTool.calculate_net_profit(position.buy_price, position.sell_price, position.volume)
                position.roi = StockTool.calculate_roi(position.buy_price, position.sell_price, position.volume)
                
                self.account.balance += (position_value - close_cost)
                self.account.trade_records[position.id] = position                                     # 根據 position.id 更新 trade_records 中對應到的 position                
                self.account.positions = [p for p in self.account.positions if p.id != position.id]    # 每一筆開倉的部位都會記錄一個 id，因此這邊只會刪除對應到 id 的部位

        return position

    
    # TODO: Method => run tick backtest
    def run_tick_backtest(self):
        """ Tick 級別的回測架構 """
        
        ticks = self.tick.get_ordered_ticks(self.cur_date, self.cur_date)
        
        for tick in ticks.itertuples(index=False):
            tick_quote = TickQuote(code=tick.stock_id, time=tick.time, 
                                    close=tick.close, volume=1,
                                    bid_price=tick.bid_price, bid_volume=tick.bid_volume,
                                    ask_price=tick.ask_price, ask_volume=tick.ask_volume,
                                    tick_type=tick.tick_type)
            
            stock_quote = StockQuote(code=tick.stock_id, scale=self.scale, 
                                     date=self.cur_date, tick=tick_quote)
            
            #TODO: 判斷庫存是否有股票要停損 or 停利
            # Execute strategy of opening position
            stock_order: Optional[StockOrder] = self.strategy.check_open_position(stock_quote)
            
            if stock_order:
                self.place_open_position(stock_order)
            
            
    def run_day_backtest(self):
        pass
    
    
    def run_mix_backtest(self):
        pass
    
        
    def run(self):
        """ 執行 Backtest (目前只有全tick回測) """
        
        print(f"* Start backtesting {self.strategy.strategy_name} strategy...")
        
        # load backtest dataset
        self.load_datasets()
        
        
        while self.cur_date <= self.end_date:
            print(f"--- {self.cur_date.strftime('%Y/%m/%d')} ---")
            
            if not StockTool.check_market_open(self.QXData, self.cur_date):
                print("* Stock Market Close\n")
                continue
            
            if self.scale == Scale.TICK:
                self.run_tick_backtest()

            elif self.scale == Scale.DAY:
                self.run_day_backtest
            
            elif self.scale == Scale.MIX:
                self.run_mix_backtest()
            
            self.cur_date += datetime.timedelta(days=1) 