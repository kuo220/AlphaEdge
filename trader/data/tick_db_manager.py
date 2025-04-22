import sys
import pandas as pd
import os
from pathlib import Path
try:
    import dolphindb as ddb
except ModuleNotFoundError:
    print("Warning: dolphindb module is not installed.")
sys.path.append(str(Path(__file__).resolve().parents[1]))
from config import (TICK_DOWNLOADS_PATH, TICK_DB_PATH, TICK_DB_NAME, TICK_TABLE_NAME, 
                    DDB_PATH, DDB_HOST, DDB_PORT, DDB_USER, DDB_PASSWORD)

    
class TickDBManager:
    
    def __init__(self):
        self.session = ddb.session()
        self.session.connect(DDB_HOST, DDB_PORT, DDB_USER, DDB_PASSWORD)  
        
        if (self.session.existsDatabase(TICK_DB_PATH)):
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
    
    
    def create_table_and_load_csv(self, csv_path: str):
        """ 創建 table 並將單個 .csv 檔案存入創建好的 database """
        
        script = f"""
        db = database("{TICK_DB_PATH}")
        schemaTable = table(
            ["stock_id", "time", "close", "volume", "bid_price", "bid_volume", "ask_price", "ask_volume", "tick_type"] as columnName,
            ["SYMBOL", "NANOTIMESTAMP", "FLOAT", "INT", "FLOAT", "INT", "FLOAT", "INT", "INT"] as columnType
        )
        loadTextEx(
            dbHandle=db,
            tableName="{TICK_TABLE_NAME}",
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
    

    def create_table_and_load_all_csv(self, dir_path: Path):
        """ 創建 table 並將多個 .csv 檔案存入建好的 database """
        
        # read all csv files in dir_path (.as_posix => replace \\ with / (for windows os))
        csv_files = [str(csv.as_posix()) for csv in dir_path.glob("*.csv")]
        print(f"* Total csv files: {len(csv_files)}")
        
        script = f""" 
        db = database("{TICK_DB_PATH}")
        schemaTable = table(
            ["stock_id", "time", "close", "volume", "bid_price", "bid_volume", "ask_price", "ask_volume", "tick_type"] as columnName,
            ["SYMBOL", "NANOTIMESTAMP", "FLOAT", "INT", "FLOAT", "INT", "FLOAT", "INT", "INT"] as columnType
        )
        
        total_csv = {len(csv_files)}
        csv_cnt = 0
        
        for (csv_path in {csv_files}) {{
            loadTextEx(
                dbHandle=db,
                tableName="{TICK_TABLE_NAME}",
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


    def append_csv_to_dolphinDB(self, csv_path: str):
        """ 將單一 CSV 資料添加到已建立的 DolphinDB 資料表 """
        pass
    
    
    def append_all_csv_to_dolphinDB(self, dir_path: str):
        """ 將資料夾內所有 CSV 檔案附加到已建立的 DolphinDB 資料表 """
        pass
    
    
    def create_tick_dolphinDB(self):
        """ 創建 dolphinDB """
        
        start_time = '2020.03.01'
        end_time = '2030.12.31'
        
        if self.session.existsDatabase(TICK_DB_PATH):
            print("Database exists!")
        else:
            print("Database doesn't exist!\nCreating a database...")
            script = f"""
            create database "{DDB_PATH}{TICK_DB_NAME}"
            partitioned by VALUE({start_time}..{end_time}), HASH([SYMBOL, 25]) 
            engine='TSDB'
            create table "{DDB_PATH}{TICK_DB_NAME}"."{TICK_TABLE_NAME}"(
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
                self.session.run(script)
                if self.session.existsDatabase(TICK_DB_PATH):
                    print("dolphinDB create successfully!")
                else:
                    print("dolphinDB create unsuccessfully!")
            except Exception as e:
                print(f"dolphinDB create unsuccessfully!\n{e}")
    
    
    @staticmethod
    def create_tick_db_metadata():
        """ 建立 tickDB 的 metatdata 以記錄 table 中資料的最早和最新的日期 """
        pass
       
    @staticmethod
    def clear_all_cache():
        """ 清除 Cache Data """
        
        session = ddb.session()
        session.connect(DDB_HOST, DDB_PORT, DDB_USER, DDB_PASSWORD)
        
        script = """ 
        clearAllCache()
        """
        session.run(script)
    
    
    @staticmethod
    def delete_dolphinDB(db_path: str):
        """ 刪除資料庫 """
        
        print("Start deleting database...")

        session = ddb.session()
        session.connect(DDB_HOST, DDB_PORT, DDB_USER, DDB_PASSWORD)
        
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