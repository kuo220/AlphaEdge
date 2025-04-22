import sys
import pandas as pd
import os
from pathlib import Path
try:
    import dolphindb as ddb
except ModuleNotFoundError:
    print("Warning: dolphindb module is not installed.")
sys.path.append(str(Path(__file__).resolve().parents[1]))
from config import (TICK_DOWNLOADS_PATH, TICK_DB_PATH, TICK_TABLE_NAME, 
                    DDB_PATH, DDB_HOST, DDB_PORT, DDB_USER, DDB_PASSWORD)


class TickDBTools:
    """ Tick DolphinDB Tools """
    
    @staticmethod
    def format_tick_data(df: pd.DataFrame, stock_id: str) -> pd.DataFrame:
        """ 統一 tick data 的格式 """
        
        df.rename(columns={'ts': 'time'}, inplace=True)
        df['stock_id'] = stock_id
        new_columns_order = ['stock_id','time', 'close', 'volume', 'bid_price', 'bid_volume', 'ask_price', 'ask_volume', 'tick_type']
        df = df[new_columns_order]

        return df
    
    
    @staticmethod
    def format_csv_time_to_microsec(csv_path: str):
        """ 將 tick csv 檔案時間格式格式化至微秒（才能存進 dolphinDB） """
        
        df = pd.read_csv(csv_path)
        
        # 若 time 欄位沒有精確到微秒則格式化
        if not df['time'].astype(str).str.match(r'.*\.\d{6}$').all():
            csv_name = Path(csv_path).name
            print(f"{csv_name} start formatting...")
            
            # 將 'time' 欄位轉換為 datetime 格式，並補足到微秒，同時加上年月日
            df['time'] = pd.to_datetime(df['time'], errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S.%f')
            
            # 將處理後的 DataFrame 保存回 CSV
            df.to_csv(csv_path, index=False)
            print(f"{csv_name} finish formatting!")