# Python standard library
import sys
import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any

# Third-party packages
import numpy as np
import pandas as pd

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[2]))

# Local imports
from data import Data, Chip, Tick, QXData
from models import (
    StockAccount,
    StockQuote,
    StockOrder,
    StockTradeRecord
)
from utils import Action, Market, Scale, PositionType
from strategies.stock import BaseStockStrategy


class Strategy(BaseStockStrategy):
    """ Strategy """
    
    def __init__(self):
        super().__init__()
        self.strategy_name = "Momentum"
        self.init_capital = 1000000.0
        self.max_positions = 10
        self.scale = Scale.DAY 
        
        self.start_time = datetime.date(2020, 4, 1)
        self.end_time = datetime.date(2024, 5, 10)
    
    
    def calculate_position_size(self, action: Action, stock: StockQuote) -> int:
        """ 計算 Open or Close 的部位大小 """
        pass
    
    
    def check_open_signal(self, stock: StockQuote) -> List[StockOrder]:
        """ 開倉策略（Long & Short） """
        
        print(f"* Open Position: {stock.code}")
        
        if self.max_positions == 0:
            return None
        
        # Condition 1: 當日漲 > 9% 的股票
        yesterday = stock.date - datetime.timedelta(days=1)
        self.qx_data.date = yesterday
        close_price_yesterday = self.qx_data.get('price', '收盤價', 1)
        price_chg = (stock.close / close_price_yesterday[stock.code][0] - 1) * 100
        
        if price_chg < 9:
            return []
        
        
        
        


    def check_close_signal(self, stock: StockQuote) -> List[StockOrder]:
        """ 平倉策略（Long & Short） """
        
        print(f"* Close Position: {stock.code}")
     
    
    def check_stop_loss_signal(self, stock: StockQuote) -> List[StockOrder]:
        """ 停損策略 """
        pass
    
    
    # Open Conditions
    def check_is_strong_momentum(self, )