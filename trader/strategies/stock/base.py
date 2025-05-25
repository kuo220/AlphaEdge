import sys
import os
from pathlib import Path
import requests
import numpy as np
import pandas as pd
import datetime
from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Optional, Any
sys.path.append(str(Path(__file__).resolve().parents[2]))
from data import Data, Chip, Tick, QXData
from models import StockAccount, StockQuote, StockOrder, StockTradeRecord
from utils import Action, Market, Scale, PositionType


class BaseStockStrategy(ABC):
    """ Stock Strategy Framework (Base Template) """
    
    def __init__(self):
        """ === Strategy Setting === """
        self.strategy_name: str = ""                    # Strategy name
        self.market: str = Market.STOCK                 # Stock or Futures
        self.position_type: str = PositionType.LONG     # Long or Short
        self.day_trade: bool = True
        self.init_capital: float = 0                    # Initial capital
        self.max_positions: Optional[int] = 0           # max limit numbers of positions
        
        """ === Datasets === """
        self.data: Data = Data()         
        self.chip: Chip = self.data.chip                # Chips data
        self.tick: Tick = self.data.tick                # Ticks data
        self.qx_data: QXData = self.data.qx_data        # Day price data, Financial data, etc
                
        """ === Backtest Setting === """
        self.is_backtest: bool = True                   # Whether it's used for backtest or not
        self.scale: str = Scale.DAY                     # Backtest scale: Day/Tick/ALL
        self.start_date: datetime.date = None           # Optional: if is_backtest == True, then set start date in backtest
        self.end_date: datetime.date = None             # Optional: if is_backtest == True, then set end date in backtest

    
    @abstractmethod
    def calculate_position_size(self, action: Action, stock: StockQuote) -> int:
        """ 
        - Description: 計算下單股數，依據當前資金、價格、風控規則決定部位大小
        - Parameters:
            - action: Action
                動作類型，例如 Action.OPEN 或 Action.CLOSE
            - stock: StockQuote
                目標股票的報價資訊
        - Return:
            - size: int
                建議下單的股數
        """
        pass
    
    
    @abstractmethod
    def check_open_signal(self, stock: StockQuote) -> Optional[StockOrder]:
        """ 
        - Description: 開倉策略（Long & Short） ，需要包含買賣的標的、價位和數量
        - Parameter:
            - stock: StockQuote
                目標股票的報價資訊
        - Return:
            - position: StockOrder
                開倉訂單
        """
        pass


    @abstractmethod
    def check_close_signal(self, stock: StockQuote) -> Optional[StockOrder]:
        """ 
        - Description: 平倉策略（Long & Short） ，需要包含買賣的標的、價位和數量
        - Parameter:
            - stock: StockQuote
                目標股票的報價資訊
        - Return:
            - position: StockOrder
                平倉訂單
        """
        pass
        
        
    @abstractmethod
    def check_stop_loss_signal(self, stock: StockQuote) -> Optional[StockOrder]:
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