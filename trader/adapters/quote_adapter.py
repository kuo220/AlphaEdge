from pathlib import Path
import datetime
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional, Any, Union

# Add parent directory to path
import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))

# Local imports
from data import Data, Chip, Tick, QXData
from models import (
    StockAccount, 
    TickQuote,
    StockQuote, 
    StockOrder,
    StockTradeRecord
)
from utils import (
    StockTools,
    Commission,
    Market,
    Scale,
    PositionType, 
    Units
)
from strategies.stock import Strategy


class StockQuoteAdapter:
    pass