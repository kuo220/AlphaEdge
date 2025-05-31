# Standard library imports
import sys
import os
import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any

# Third-party packages
import numpy as np
import pandas as pd
import requests

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[2]))

# Local imports
from models import (
    StockAccount,
    StockQuote, 
    StockOrder,
    StockTradeRecord
)
from utils import (
    Data,
    Market,
    Scale,
    PositionType
)
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
    
    
    def check_open_signal(self, stock: StockQuote) -> Optional[StockOrder]:
        """ 開倉策略（Long & Short） """
        
        print(f"* Open Position: {stock.code}")


    def check_close_signal(self, stock: StockQuote) -> Optional[StockOrder]:
        """ 平倉策略（Long & Short） """
        
        print(f"* Close Position: {stock.code}")
    
    
    def check_stop_loss_signal(self, stock: StockQuote) ->Optional[StockOrder]:
        """ 停損策略 """
        pass
        
        