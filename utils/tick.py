import sqlite3
import pandas as pd
import datetime


class TickTool:
    @staticmethod
    def format_ticks_data(df: pd.DataFrame, stock_id: str) -> pd.DataFrame:
        """ 統一 tick data 的格式 """
        df.rename(columns={'ts': 'time'}, inplace=True)
        df['stock_id'] = stock_id
        new_columns_order = ['stock_id','time', 'close', 'volume', 'bid_price', 'bid_volume', 'ask_price', 'ask_volume', 'tick_type']
        df = df[new_columns_order]

        return df
    
    @staticmethod
    def create_sql(db_path: str):
        """ 創建 tick db """
        conn = sqlite3.connect(db_path)
        create_table_query = """ 
        CREATE TABLE IF NOT EXISTS ticks (
            stock_id INTEGER NOT NULL,
            time TEXT NOT NULL,
            close REAL NOT NULL,
            volume INTEGER NOT NULL,
            bid_price REAL NOT NULL,
            bid_volume INTEGER NOT NULL,
            ask_price REAL NOT NULL,
            ask_volume INTEGER NOT NULL,
            tick_type INTEGER NOT NULL
        )
        """
        conn.execute(create_table_query)
        
    @staticmethod
    def add_to_sql(df, db_path: str):
        """ 更新 tick db """
        conn = sqlite3.connect(db_path)
        df.to_sql('ticks', conn, if_exists='append', index=False)
    

class Tick:
    def __init__(self):
        # open the db
        self.db_path = './tick.db'
        self.conn = sqlite3.connect(self.db_path)

    def get(self, table_name: str, stock_id: str, start_time: datetime.date, end_time: datetime.date) -> pd.DataFrame:
        if start_time == end_time:
            start_time = datetime.datetime(start_time.year, start_time.month, start_time.day, 0, 0, 0).strftime('%Y-%m-%d %H:%M:%S')
        else:
            start_time = start_time.strftime('%Y-%m-%d %H:%M:%S')
        end_time = datetime.datetime(end_time.year, end_time.month, end_time.day, 23, 59, 59).strftime('%Y-%m-%d %H:%M:%S')
        
        cursor = self.conn.cursor()

        stock_query = f""" 
        SELECT * FROM {table_name}
        WHERE stock_id={stock_id} 
        AND time BETWEEN '{start_time}' AND '{end_time}'
        """
        cursor.execute(stock_query)
        
        ticks = cursor.fetchall()
        ticks = pd.DataFrame(ticks, columns=['stock_id','time', 'close', 'volume', 'bid_price', 'bid_volume', 'ask_price', 'ask_volume', 'tick_type'])
        return ticks
    
    def get_last_tick(self, table_name: str, stock_id: str, start_time: datetime.date, end_time: datetime.date) -> pd.DataFrame:
        ticks = self.get(table_name, stock_id, start_time, end_time)
        return ticks.iloc[-1:]
    
    def db_close(self):
        self.conn.close()
    
