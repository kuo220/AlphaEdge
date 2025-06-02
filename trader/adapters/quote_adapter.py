from pathlib import Path
import datetime
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional, Any, Union

from trader.data import Data, Chip, Tick, QXData
from trader.models import (
    StockAccount, 
    TickQuote,
    StockQuote, 
    StockOrder,
    StockTradeRecord
)
from trader.utils import (
    StockTools,
    Commission,
    Market,
    Scale,
    PositionType, 
    Units
)
from trader.strategies.stock import Strategy


class StockQuoteAdapter:
    pass