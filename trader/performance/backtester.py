import sys
import os
from pathlib import Path
import requests
import numpy as np
import pandas as pd
import datetime
sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import AccountBacktest, Stock, TradeEntry, Trade
from utils import Commission


class BackTester:
    """ Backtest Framework
    - Time Interval：
        1. Ticks
        2. Daily price
    """
    
    def __init__(self):
        pass
    
    
    def run(self):
        """ 執行 Backtest """
        pass
    

