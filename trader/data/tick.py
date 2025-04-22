import sys
import sqlite3
import os
import pandas as pd
import datetime
import json
from typing import Optional
from pathlib import Path
try:
    import dolphindb as ddb
except ModuleNotFoundError:
    print("Warning: dolphindb module is not installed.")
sys.path.append(str(Path(__file__).resolve().parents[1]))
from config import (TICK_DB_PATH, TICK_TABLE_NAME, TICK_METADATA_PATH,
                    DDB_HOST, DDB_PORT, DDB_USER, DDB_PASSWORD)


class Tick:
    """ Tick data API """
    
    def __init__(self):
        self.default_stock_id: str = "2330"
        self.query_start_date: str = "2024.05.10"
        self.query_end_date: str = "2024.05.10"
        
        self.session: ddb.session = ddb.session() 
        self.session.connect(DDB_HOST, DDB_PORT, DDB_USER, DDB_PASSWORD)
        
        if (self.session.existsDatabase(TICK_DB_PATH)):
            print("* Database exists!")
            
            # set TSDBCacheEngineSize to 5GB (must < 8(maxMemSize) * 0.75 GB)
            script = """ 
            memSize = 2
            setTSDBCacheEngineSize(memSize)
            print("TSDBCacheEngineSize: " + string(getTSDBCacheEngineSize() / pow(1024, 3)) + "GB")
            """
            self.session.run(script)
        else:
            print("* Database doesn't exist!")
    
    
    def get(self, start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame:
        """ 取得所有個股各自排序好 tick 資料（個股沒有混在一起排序） """
        
        if start_date > end_date:
            return pd.DataFrame()
        
        start_date = start_date.strftime('%Y.%m.%d')
        end_date = (end_date + datetime.timedelta(days=1)).strftime('%Y.%m.%d')
        script = f""" 
        db = database("{TICK_DB_PATH}")
        table = loadTable(db, "{TICK_TABLE_NAME}")
        select * from table
        where time between nanotimestamp({start_date}):nanotimestamp({end_date})
        """
        tick = self.session.run(script)
        return tick


    def get_ordered_ticks(self, start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame:
        """ 取得排序好的 tick 資料（所有個股混在一起以時間排序） """
        """ 模擬市場盤中情形 """
        
        if start_date > end_date:
            return pd.DataFrame()
        
        start_date = start_date.strftime('%Y.%m.%d')
        end_date = (end_date + datetime.timedelta(days=1)).strftime('%Y.%m.%d')
        script = f""" 
        db = database("{TICK_DB_PATH}")
        table = loadTable(db, "{TICK_TABLE_NAME}")
        select * from table
        where time between nanotimestamp({start_date}):nanotimestamp({end_date}) order by time
        """
        tick = self.session.run(script)
        return tick
    
    
    def get_stock_ticks(self, stock_id: str, start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame:
        """ 取得個股 tick 資料 """
    
        if start_date > end_date:
            return pd.DataFrame()
        
        start_date = start_date.strftime('%Y.%m.%d')
        end_date = (end_date + datetime.timedelta(days=1)).strftime('%Y.%m.%d')
        script = f""" 
        db = database("{TICK_DB_PATH}")
        table = loadTable(db, "{TICK_TABLE_NAME}")
        select * from table
        where stock_id=`{stock_id} and time between nanotimestamp({start_date}):nanotimestamp({end_date})
        """
        tick = self.session.run(script)
        return tick
    
    
    def get_last_tick(self, stock_id: str, date: datetime.date) -> pd.DataFrame:
        """ 取得當日最後一筆 tick """
        
        tick = self.get_stock_tick(stock_id, date, date)
        if len(tick) > 0:
            return tick.iloc[-1:]
        return pd.DataFrame
    
    
    def get_table_earliest_date(self) -> datetime.date:
        """ 從 tick_time_range.json 中取得 tick table 的最早日期 """
        
        with open(TICK_METADATA_PATH, "r", encoding="utf-8") as data:
            time_data = json.load(data)
            earliest_date = datetime.date.fromisoformat(time_data["earliest_date"])
        return earliest_date
    
    
    def get_table_latest_date(self) -> datetime.date:
        """ 從 tick_time_range.json 中取得 tick table 的最新日期 """
        
        with open(TICK_METADATA_PATH, "r", encoding="utf-8") as data:
            time_data = json.load(data)
            latest_date = datetime.date.fromisoformat(time_data["latest_date"])
        return latest_date
        