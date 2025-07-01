from pathlib import Path
import datetime
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional, Any, Union

from trader.data import Data, Chip, Tick, QXData
from trader.adapters import StockQuoteAdapter
from trader.models import (
    StockAccount,
    TickQuote,
    StockQuote,
    StockOrder,
    StockTradeRecord
)
from trader.utils import (
    StockTools,
    Commission,
    Market,
    Scale,
    PositionType,
    Units
)
from trader.strategies.stock import BaseStockStrategy


"""
Backtesting engine that simulates trading based on strategy signals.

Includes:
- Tick/day backtest flow
- Position and account management
- Order execution logic
- Strategy integration for various financial instruments
"""


class Backtester:
    """
    Backtest Framework
    - Time Interval：
        1. Ticks
        2. Daily price
    """
    
    # === Init & Data Loading ===
    def __init__(self, strategy: BaseStockStrategy):
        
        """ === Strategy & Account Information === """
        self.strategy: BaseStockStrategy = strategy                                      # 要回測的策略
        self.account: StockAccount = StockAccount(self.strategy.init_capital)   # 虛擬帳戶資訊
        self.strategy.set_account(self.account)                                 # 設置虛擬帳戶資訊
        
        """ === Datasets === """
        self.data: Data = Data()
        self.tick: Optional[Tick] = None                                        # Ticks data
        self.chip: Optional[Chip] = None                                        # Chips data
        self.qx_data: Optional[QXData] = None                                   # Day price data, Financial data, etc
        
        """ === Backtest Parameters === """
        self.scale: str = self.strategy.scale                                   # 回測 KBar 級別
        self.max_holdings: Optional[int] = self.strategy.max_holdings         # 最大持倉檔數
        self.start_date: datetime.date = self.strategy.start_date               # 回測起始日
        self.cur_date: datetime.date = self.strategy.start_date                 # 回測當前日
        self.end_date: datetime.date = self.strategy.end_date                   # 回測結束日
        
    
    def load_datasets(self) -> None:
        """ 從資料庫載入資料 """
        
        self.chip = self.data.chip
        if self.scale == Scale.TICK:
            self.tick = self.data.tick
            
        elif self.scale == Scale.DAY:
            self.qx_data = self.data.qx_data
            
        elif self.scale == Scale.MIX:
            self.tick = self.data.tick
            self.qx_data = self.data.qx_data
            
    
    # === Main Backtest Loop ===
    def run(self) -> None:
        """ 執行 Backtest (目前只有全tick回測) """
        
        print("========== Backtest Start ==========")
        print(f"* Strategy Name: {self.strategy.strategy_name}")
        print(f"* Backtest Period: {self.start_date.strftime('%Y/%m/%d')} ~ {self.end_date.strftime('%Y/%m/%d')}")
        print(f"* Initial Capital: {self.strategy.init_capital}")
        print(f"* Backtest Scale: {self.scale}")
        
        # load backtest dataset
        self.load_datasets()
        
        while self.cur_date <= self.end_date:
            print(f"--- {self.cur_date.strftime('%Y/%m/%d')} ---")
            
            if not self.qx_data.check_market_open(self.cur_date):
                print("* Stock Market Close\n")
                continue
            
            if self.scale == Scale.TICK:
                self.run_tick_backtest()

            elif self.scale == Scale.DAY:
                self.run_day_backtest()
            
            elif self.scale == Scale.MIX:
                self.run_mix_backtest()
            
            self.cur_date += datetime.timedelta(days=1)
    
        self.account.update_account_status()
    
    
    def run_tick_backtest(self) -> None:
        """ Tick 級別的回測架構 """
        
        # Stock Quotes
        stock_quotes: List[StockQuote] = StockQuoteAdapter.convert_to_tick_quotes(self.tick, self.cur_date)
        
        if not stock_quotes:
            return
            
        self.execute_close_signal(stock_quotes)
        self.execute_open_signal(stock_quotes)
            
            
    def run_day_backtest(self) -> None:
        """ Day 級別的回測架構 """
        
        # Stock Quotes
        stock_quotes: List[StockQuote] = StockQuoteAdapter.convert_to_day_quotes(self.qx_data, self.cur_date)
        
        if not stock_quotes:
            return
    
        self.execute_close_signal(stock_quotes)
        self.execute_open_signal(stock_quotes)
                
            
    def run_mix_backtest(self) -> None:
        """ Tick & Day 級別的回測架構 """
        pass
    
    
    # === Signal Execution ===
    def execute_open_signal(self, stock_quotes: List[StockQuote]) -> None:
        """ 若倉位數量未達到限制且有開倉訊號，則執行開倉 """
        
        open_orders: List[StockOrder] = self.strategy.check_open_signal(stock_quotes)
        if self.max_holdings is not None:
            remaining_holding: int = max(0, self.max_holdings - self.account.get_position_count())
            open_orders = open_orders[:remaining_holding]
            
        for order in open_orders:
            self.place_open_order(order)
            
    
    def execute_close_signal(self, stock_quotes: List[StockQuote]) -> None:
        """ 執行平倉邏輯：先判斷停損訊號，後判斷一般平倉 """
        
        # 先找出有持倉的股票
        positions: List[StockQuote] = [sq for sq in stock_quotes if self.account.check_has_position(sq.code)]
        
        if not positions:
            return
            
        stop_loss_orders: List[StockOrder] = self.strategy.check_stop_loss_signal(positions)
        for order in stop_loss_orders:
            self.place_close_order(order)
        
        # 停損執行後重新確認剩下的持倉
        remaining_positions: List[StockQuote] = [sq for sq in stock_quotes if self.account.check_has_position(sq.code)]
        
        close_orders: List[StockOrder] = self.strategy.check_close_signal(remaining_positions)
        for order in close_orders:
            self.place_close_order(order)

    
    # === Order Placement ===
    def place_open_order(self, stock: StockOrder) -> Optional[StockTradeRecord]:
        """ 
        - Description: 開倉下單股票
        - Parameters:
            - stock: StockOrder
                目標股票的訂單資訊
        - Return:
            - position: StockTradeRecord
        """
        
        position_value: float = stock.price * stock.volume * Units.LOT
        open_cost: float = StockTools.calculate_transaction_commission(buy_price=stock.price, volume=stock.volume)
        position: Optional[StockTradeRecord] = None
        
        if stock.position_type == PositionType.LONG:
            if self.account.balance >= (position_value + open_cost):
                print(f"* Place Open Order: {stock.code}")
                
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


    def place_close_order(self, stock: StockOrder) -> Optional[StockTradeRecord]:
        """
        - Description: 下單平倉股票
        - Parameters:
            - stock: StockOrder
                目標股票的訂單資訊
        - Return:
            - position: StockTradeRecord
        """

        position_value: float = stock.price * stock.volume * Units.LOT
        close_cost: float = StockTools.calculate_transaction_commission(sell_price=stock.price, volume=stock.volume)
        
        # 根據 stock.code 找出庫存中最早買進的該檔股票（FIFO）
        position: Optional[StockTradeRecord] = self.account.get_first_open_position(stock.code)
        
        if position is not None and not position.is_closed:
            print(f"* Place Close Order: {stock.code}")
            
            if position.position_type == PositionType.LONG:
                position.date = stock.date
                position.is_closed = True
                position.sell_price = stock.price
                position.commission += close_cost
                position.tax = StockTools.calculate_transaction_tax(stock.price, stock.volume)
                position.transaction_cost = position.commission + position.tax
                position.realized_pnl = StockTools.calculate_net_profit(position.buy_price, position.sell_price, position.volume)
                position.roi = StockTools.calculate_roi(position.buy_price, position.sell_price, position.volume)
                
                self.account.balance += (position_value - close_cost)
                self.account.trade_records[position.id] = position                                     # 根據 position.id 更新 trade_records 中對應到的 position                
                self.account.positions = [p for p in self.account.positions if p.id != position.id]    # 每一筆開倉的部位都會記錄一個 id，因此這邊只會刪除對應到 id 的部位

        return position
    
     
    # === Report ===
    def generate_backtest_report(self) -> None:
        """ 生產回測報告 """
        pass