import pandas as pd
import datetime
import dolphindb as ddb

class Tick:
    """ tick data API """
    
    def __init__(self, db_path: str, db_name: str, table_name: str):
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
    
    
    def get(self, stock_id: str, start_time: datetime.date, end_time: datetime.date) -> pd.DataFrame:
        """ 取得 tick 資料 """
    
        if start_time > end_time:
            return pd.DataFrame()
        
        start_time = start_time.strftime('%Y.%m.%d')
        end_time = (end_time + datetime.timedelta(days=1)).strftime('%Y.%m.%d')
        script = f""" 
        db = database("{self.db_path}")
        table = loadTable(db, "{self.table_name}")
        select * from table
        where stock_id=`{stock_id} and time between nanotimestamp({start_time}):nanotimestamp({end_time})
        """
        tick = self.session.run(script)
        return tick
    
    
    def get_last_tick(self, stock_id: str, date: datetime.date) -> pd.DataFrame:
        """ 取得當日最後一筆 tick """
        
        tick = self.get(stock_id, date, date)
        if len(tick) > 0:
            return tick.iloc[-1:]
        return pd.DataFrame
    

class TickTool:
    @staticmethod
    def format_ticks_data(df: pd.DataFrame, stock_id: str) -> pd.DataFrame:
        """ 統一 tick data 的格式 """
        
        df.rename(columns={'ts': 'time'}, inplace=True)
        df['stock_id'] = stock_id
        new_columns_order = ['stock_id','time', 'close', 'volume', 'bid_price', 'bid_volume', 'ask_price', 'ask_volume', 'tick_type']
        df = df[new_columns_order]

        return df
    

