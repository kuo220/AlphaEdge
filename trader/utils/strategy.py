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
        self.market: str = 'Stock'                  # Stock or Future
        self.strategy_direction: str = 'Long'       # Long or Short
        self.day_trade: bool = False                # Enable/Unable to day trade
        self.holding_limit: int = 0                 # Limit numbers of holdings
        self.dataset: Dict[str, bool] = {           # Dataset used in the strategy   
            'QXData': False,
            'Tick': False,
            'Chip': False
        }
        
        self.is_backtest: bool = True               # Whether it's used for backtest or not
        self.scale: str = 'Day'                     # kbar scale: Day/Tick
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