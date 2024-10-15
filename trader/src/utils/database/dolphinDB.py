import pandas as pd
import os
import re
from pathlib import Path
import dolphindb as ddb


class DolphinDB:
    
    def __init__(self, db_path: str, db_name: str, table_name: str):
        self.db_path = db_path          # ex: "dfs://tickDB"
        self.db_name = db_name          # ex: "tickDB"
        self.table_name = table_name    # ex: "tick"
        
        self.session = ddb.session()
        self.session.connect("localhost", 8848, "admin", "123456")  
        
        if (self.session.existsDatabase(db_path)):
            print("Database exists!")
            
            # set TSDBCacheEngineSize to 5GB (must < 8(maxMemSize) * 0.75 GB)
            script = """ 
            memSize = 2
            setTSDBCacheEngineSize(memSize)
            print("TSDBCacheEngineSize: " + string(getTSDBCacheEngineSize() / pow(1024, 3)) + "GB")
            """
            self.session.run(script)
        else:
            print("Database doesn't exist!")
        
            
    @staticmethod
    def create_dolphinDB(db_name: str, table_name: str):
        """ 創建 dolphinDB """
    
        session = ddb.session()
        session.connect("localhost", 8848, "admin", "123456")
        
        start_time = '2020.03.01'
        end_time = '2030.12.31'
        
        if session.existsDatabase(f"dfs://{db_name}"):
            print("Database exists!")
        else:
            print("Database doesn't exist!\nCreating a database...")
            script = f"""
            create database "dfs://{db_name}"
            partitioned by VALUE({start_time}..{end_time}), HASH([SYMBOL, 25]) 
            engine='TSDB'
            create table "dfs://{db_name}"."{table_name}"(
                stock_id SYMBOL
                time NANOTIMESTAMP
                close FLOAT
                volume INT
                bid_price FLOAT
                bid_volume INT
                ask_price FLOAT
                ask_volume INT
                tick_type INT
            )
            partitioned by time, stock_id,
            sortColumns=[`stock_id, `time],
            keepDuplicates=ALL
            """
            try:
                session.run(script)
                if session.existsDatabase(f"dfs://{db_name}"):
                    print("dolphinDB create successfully!")
                else:
                    print("dolphinDB create unsuccessfully!")
            except Exception as e:
                print(f"dolphinDB create unsuccessfully!\n{e}")
            
       
    def add_csv_to_dolphinDB(self, csv_path: str):
        """ 將單個 .csv 檔案存入創建好的 database """
        
        script = f"""
        db = database("{self.db_path}")
        schemaTable = table(
            ["stock_id", "time", "close", "volume", "bid_price", "bid_volume", "ask_price", "ask_volume", "tick_type"] as columnName,
            ["SYMBOL", "NANOTIMESTAMP", "FLOAT", "INT", "FLOAT", "INT", "FLOAT", "INT", "INT"] as columnType
        )
        loadTextEx(
            dbHandle=db,
            tableName="{self.table_name}",
            partitionColumns=["time", "stock_id"], 
            filename="{csv_path}",
            delimiter=",",
            schema=schemaTable,
            containHeader=true
        )
        """
        try:
            self.session.run(script)
            print("The csv file successfully save into database and table!")

        except Exception as e:
            print(f"The csv file fail to save into database and table!\n{e}")    
    

    def add_all_csv_to_dolphinDB(self, dir_path: str):
        """ 將多個 .csv 檔案存入建好的 database """
        
        # read all csv files in dir_path (.replace is for windows os)
        csv_files = [str(dir_path / csv).replace('\\', '/') for csv in os.listdir(dir_path)]
        print(f"* Total csv files: {len(csv_files)}")
        
        script = f""" 
        db = database("{self.db_path}")
        schemaTable = table(
            ["stock_id", "time", "close", "volume", "bid_price", "bid_volume", "ask_price", "ask_volume", "tick_type"] as columnName,
            ["SYMBOL", "NANOTIMESTAMP", "FLOAT", "INT", "FLOAT", "INT", "FLOAT", "INT", "INT"] as columnType
        )
        
        total_csv = {len(csv_files)}
        csv_cnt = 0
        
        for (csv_path in {csv_files}) {{
            loadTextEx(
                dbHandle=db,
                tableName="{self.table_name}",
                partitionColumns=["time", "stock_id"],
                filename=csv_path,
                delimiter=",",
                schema=schemaTable,
                containHeader=true
            )
            csv_cnt += 1
            print("* Status: " + string(csv_cnt) + "/" + string(total_csv))
        }}
        """
        try:
            self.session.run(script)
            print("All csv files successfully save into database and table!")

        except Exception as e:
            print(f"All csv files fail to save into database and table!\n{e}")

    
    @staticmethod
    def clear_all_cache():
        """ 清除 Cache Data """
        
        session = ddb.session()
        session.connect("localhost", 8848, "admin", "123456")
        
        script = """ 
        clearAllCache()
        """
        session.run(script)
    
    
    @staticmethod
    def delete_dolphinDB(db_path: str):
        """ 刪除資料庫 """
        
        print("Start deleting database...")

        session = ddb.session()
        session.connect("localhost", 8848, "admin", "123456")
        
        script = f"""
        if (existsDatabase("{db_path}")) {{
            dropDatabase("{db_path}")
        }}
        """
        session.run(script)

        if (session.existsDatabase(db_path)):
            print("Delete database unsuccessfully!")
        else:
            print("Delete database successfully!")
            
    
    @staticmethod
    def format_tick_data(df: pd.DataFrame, stock_id: str) -> pd.DataFrame:
        """ 將 tick data 的欄位格式化 """
        
        df.rename(columns={'ts': 'time'}, inplace=True)
        df['stock_id'] = stock_id
        new_columns_order = ['stock_id','time', 'close', 'volume', 'bid_price', 'bid_volume', 'ask_price', 'ask_volume', 'tick_type']
        df = df[new_columns_order]

        return df
    
    
    @staticmethod
    def format_tick_time_to_microsec(csv_path: dir):
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