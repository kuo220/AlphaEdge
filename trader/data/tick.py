import sqlite3
import os
import pandas as pd
import datetime
from pathlib import Path
try:
    import dolphindb as ddb
except ModuleNotFoundError:
    print("Warning: dolphindb module is not installed.")
    
    
class Tick:
    """ Tick data API """
    
    def __init__(self, db_path: str="dfs://tickDB", db_name: str="tickDB", table_name: str="tick"):
        self.db_path = db_path
        self.db_name = db_name
        self.table_name = table_name
        
        self.session = ddb.session() 
        self.session.connect("localhost", 8848, "admin", "123456")
        
        if (self.session.existsDatabase(self.db_path)):
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
        db = database("{self.db_path}")
        table = loadTable(db, "{self.table_name}")
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
        db = database("{self.db_path}")
        table = loadTable(db, "{self.table_name}")
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
        db = database("{self.db_path}")
        table = loadTable(db, "{self.table_name}")
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