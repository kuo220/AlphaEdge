import sys
import datetime
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any
import numpy as np
import pandas as pd

from trader.data import Data, Chip, Tick, QXData
from trader.models import (
    StockAccount,
    StockQuote,
    StockOrder,
    StockTradeRecord
)
from trader.utils import (
    Action,
    Market,
    Scale,
    PositionType
)


class BaseStockStrategy(ABC):
    """ Stock Strategy Framework (Base Template) """
    
    def __init__(self):
        """ === Account Setting === """
        self.account: StockAccount = None               # 虛擬帳戶資訊
        
        """ === Strategy Setting === """
        self.strategy_name: str = ""                    # Strategy name
        self.market: str = Market.STOCK                 # Stock or Futures
        self.position_type: str = PositionType.LONG     # Long or Short
        self.enable_intraday: bool = True               # Allow day trade or not
        self.init_capital: float = 0                    # Initial capital
        self.max_holdings: Optional[int] = 0            # Maximum number of holdings allowed
        
        """ === Backtest Setting === """
        self.is_backtest: bool = True                   # Whether it's used for backtest or not
        self.scale: str = Scale.DAY                     # Backtest scale: Day/Tick/ALL
        self.start_date: datetime.date = None           # Optional: if is_backtest == True, then set start date in backtest
        self.end_date: datetime.date = None             # Optional: if is_backtest == True, then set end date in backtest
        
        """ === Datasets Setting=== """
        self.data: Data = Data()         
        self.chip: Chip = self.data.chip                # Chips data
        self.tick: Optional[Tick] = None                # Ticks data
        self.qx_data: QXData = self.data.qx_data        # Day price data, Financial data, etc

        if self.scale in (Scale.TICK, Scale.MIX):
            self.tick: Tick = self.data.tick 
    
    
    @abstractmethod
    def set_account(self, account: StockAccount):
        """ 
        - Description: 
            載入虛擬帳戶資訊
        """
        pass
    
    
    @abstractmethod
    def check_open_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        """ 
        - Description: 
            開倉策略（Long & Short） ，需要包含買賣的標的、價位和數量
        - Parameter:
            - account: StockAccount
                交易帳戶資訊
            - stock_quotes: List[StockQuote]
                目標股票的報價資訊
        - Return:
            - position: List[StockQuote]
                開倉訂單
        """
        pass


    @abstractmethod
    def check_close_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        """ 
        - Description: 
            平倉策略（Long & Short） ，需要包含買賣的標的、價位和數量
        - Parameter:
            - account: StockAccount
                交易帳戶資訊
            - stock_quotes: List[StockQuote]
                目標股票的報價資訊
        - Return:
            - position: List[StockQuote]
                平倉訂單
        """
        pass
        
        
    @abstractmethod
    def check_stop_loss_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        """ 
        - Description: 
            設定停損機制
        - Parameter:
            - account: StockAccount
                交易帳戶資訊
            - stock_quotes: List[StockQuote]
                目標股票的報價資訊
        - Return:
            - position: List[StockOrder]
                停損（平倉）訂單
        """
        pass

    
    @abstractmethod
    def calculate_position_size(
        self, 
        stock_quotes: List[StockQuote], 
        action: Action
    ) -> List[StockOrder]:
        """ 
        - Description: 
            計算下單股數，依據當前資金、價格、風控規則決定部位大小
        - Parameters:
            - account: StockAccount
                交易帳戶資訊
            - stock_quotes: List[StockQuote]
                目標股票的報價資訊
            - action: Action
                動作類型，例如 Action.OPEN 或 Action.CLOSE
        - Return:
            - List[StockOrder]
                建議下單的股數
        """
        pass
    
    