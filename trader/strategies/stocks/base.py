import sys
import os
from pathlib import Path
import requests
import numpy as np
import pandas as pd
import datetime
from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Any
sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils import (Data, Market, Scale, PositionType,
                   Market, Scale, PositionType)
from models import StockAccount, StockQuote, StockOrder, StockTradeEntry

class BaseStockStrategy(ABC):
    """ Stock Strategy Framework (Base Template) """
    
    def __init__(self):
        """ === Strategy Setting === """
        self.strategy_name: str = ""                    # Strategy name
        self.market: str = Market.STOCK                 # Stock or Futures
        self.position_type: str = PositionType.LONG     # Long or Short
        self.day_trade: bool = True
        self.init_capital: float = 0                    # Initial capital
        self.max_positions: int = 0                     # max limit numbers of positions
        
        """ === Datasets === """
        self.data: Data = Data()                        
        self.QXData: Data = None                        # Day price data, Financial data, etc
        self.tick: Data = None                          # Ticks data
        self.chip: Data = None                          # Chips data
        
        """ === Backtest Setting === """
        self.is_backtest: bool = True                   # Whether it's used for backtest or not
        self.scale: str = Scale.DAY                     # Backtest scale: Day/Tick/ALL
        self.dataset: Dict[str, bool] = {               # Dataset used in the strategy   
            'QXData': True,
            'Tick': True,
            'Chip': True
        }
        self.start_date: datetime.date = None           # Optional: if is_backtest == True, then set start date in backtest
        self.end_date: datetime.date = None             # Optional: if is_backtest == True, then set end date in backtest

    
    def load_datasets(self):
        """ 從資料庫載入資料 """
        
        self.QXData = self.data.QXData
        self.tick = self.data.Tick
        self.chip = self.data.Chip
    
    
    @abstractmethod
    def check_open_signal(self, stock: StockQuote) -> StockOrder:
        """ 
        - Description: 開倉策略（Long & Short） ，需要包含買賣的標的、價位和數量
        - Parameter:
            - stock: StockQuote
                目標股票的報價資訊
        - Return:
            - position: StockOrder
                開倉訂單
        """
        
        print(f"* Open Position: {stock.code}")


    @abstractmethod
    def check_close_signal(self, stock: StockQuote) -> StockOrder:
        """ 
        - Description: 平倉策略（Long & Short） ，需要包含買賣的標的、價位和數量
        - Parameter:
            - stock: StockQuote
                目標股票的報價資訊
        - Return:
            - position: StockOrder
                平倉訂單
        """
        
        print(f"* Close Position: {stock.code}")
        
        
    @abstractmethod
    def check_stop_loss_signal(self, stock: StockQuote) -> StockOrder:
        """ 
        - Description: 設定停損機制
        - Parameter:
            - stock: StockQuote
                目標股票的報價資訊
        - Return:
            - position: StockOrder
                停損（平倉）訂單
        """
        pass