# Standard library imports
import datetime
import os
import sqlite3
from pathlib import Path
import pandas as pd
try:
    import dolphindb as ddb
except ModuleNotFoundError:
    print("Warning: dolphindb module is not installed.")

from .chip import Chip
from .tick import Tick
from .qx_data import QXData
    

class Data:
    """ 股市資料 API """
    
    def __init__(self):
        self.chip: Chip = Chip()
        
        """ Ensure dolphinDB server has been opened """
        try:
            self.tick: Tick = Tick()
        except Exception as e:
            print(e)
            
        self.qx_data: QXData = QXData()