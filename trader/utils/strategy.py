import sys
import os
from pathlib import Path
import requests
import numpy as np
import pandas as pd
import datetime
from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Any
from utils.data import Data
from utils.records import Account, StockQuote, StockTradeEntry


class Strategy(ABC):
    """ Strategy Framework (Base Template) """
    
    def __init__(self):
        self.strategy_name: str = ""                # Strategy name
        self.market: str = 'Stock'                  # Stock or Future
        self.strategy_direction: str = 'Long'       # Long or Short
        self.day_trade: bool = True
        self.capital: float = 0                     # Initial capital
        self.max_positions: int = 0                 # max limit numbers of positions
        
        """ === Backtest Setting === """
        self.is_backtest: bool = True               # Whether it's used for backtest or not
        self.scale: str = 'Day'                     # Backtest scale: Day/Tick
        self.dataset: Dict[str, bool] = {           # Dataset used in the strategy   
            'QXData': True,
            'Tick': True,
            'Chip': True
        }
        self.start_time: datetime.date = None       # Optional: if is_backtest == True, then set start date in backtest
        self.end_time: datetime.date = None         # Optional: if is_backtest == True, then set end date in backtest

    
    @abstractmethod
    def open_position(self, stock: StockQuote):
        """ 開倉策略（Long & Short） """
        
        pass


    @abstractmethod
    def close_position(self, stock: StockQuote):
        """ 平倉策略（Long & Short） """
        
        pass