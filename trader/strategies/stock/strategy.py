import sys
import os
from pathlib import Path
import requests
import numpy as np
import pandas as pd
import datetime
from typing import List, Dict, Tuple, Any
sys.path.append(str(Path(__file__).resolve().parents[2]))
from models import(StockAccount, StockQuote, StockOrder, StockTradeRecord)
from utils import (Data, Market, Scale, PositionType,
                   Market, Scale, PositionType)
from strategies.stock import BaseStockStrategy

class Strategy(BaseStockStrategy):
    """ Strategy """
    
    def __init__(self):
        super().__init__()
        self.strategy_name = "Momentum"
        self.init_capital = 1000000.0
        self.max_positions = 10
        self.scale = Scale.TICK
        self.dataset = {
            'QXData': True,
            'Tick': True,
            'Chip': False
        }
        self.start_time = datetime.date(2020, 4, 1)
        self.end_time = datetime.date(2024, 5, 10)
    
    
    def check_open_position(self, stock: StockQuote) -> StockOrder:
        """ 開倉策略（Long & Short） """
        
        super().open_position(stock)
        

    def check_close_position(self, stock: StockQuote) -> StockOrder:
        """ 平倉策略（Long & Short） """
        
        super().close_position(stock)
        
        