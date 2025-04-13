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
from utils import (Data, Market, Scale, PositionType,
                   Market, Scale, PositionType)
from models import StockAccount, StockQuote, StockOrder, StockTradeRecord



"""
base.py

Defines abstract base classes for performance-related modules.

This file provides reusable interfaces for backtest performance analysis and report generation.
Typical use cases include customizing analyzers or reports for different financial instruments
(e.g. stocks, futures, options).

Classes:
- BaseAnalyzer: Interface for computing backtest metrics
- BaseReport: Interface for generating performance reports
"""


class BaseBacktestAnalyzer:
    """ Backtest Performance Analyzer Framework (Base Template) """
    
    def __init__(self, account: Any):
        self.account = account