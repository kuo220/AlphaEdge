import dolphindb as ddb


class DolphinDB:
    
    def __init__(self, db_path: str, db_name: str, table_name: str):
        self.db_path = db_path
        self.db_name = db_name
        self.table_name = table_name
        
        self.session = ddb.session()
        self.session.connect("localhost", 8848, "admin", "123456")        
        
        if (self.session.existsDatabase(db_path)):
            print("Database exist")
        else:
            print("Database doesn't exist")
        
            
    @staticmethod
    def create_dolphingDB(db_name: str, table_name: str):
        """ 創建 dolphinDB """
    
        session = ddb.session()
        session.connect("localhost", 8848, "admin", "123456")
        
        start_time = '2020.01.01'
        end_time = '2030.12.31'
        
        script = f"""
        if (!existsDatabase("dfs://{db_name}")) {{
           create database "dfs://{db_name}"
           partitioned by VALUE({start_time}..{end_time}), HASH([SYMBOL, 25]) 
           engine='TSDB'
        }}
        
        try {{
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
        }} catch (ex) {{
            dropDatabase("dfs://{db_name}")
            throw ex
        }}
        """
        
        try:
            session.run(script)
            print("dolphinDB create successfully!")
        except Exception as e:
            print(f"dolphinDB create unsuccessfully!\n{e}")
            
    


    def add_csv_to_dolphinDB(self, csv_path: str):
        """ 將 .csv 檔案存入創建好的 database """
        
        script = f"""
        db = database("{self.db_path}")
        schemaTable = table(
            ["stock_id","time","close","volume","bid_price","bid_volume","ask_price","ask_volume","tick_type"] as columnName,
            ["SYMBOL","NANOTIMESTAMP","FLOAT","INT","FLOAT","INT","FLOAT","INT","INT"] as columnType
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
            