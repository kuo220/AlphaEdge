import datetime
import shutil
from pathlib import Path
from typing import List, Optional
import ipywidgets as widgets
from IPython.display import display
try:
    import dolphindb as ddb
except ModuleNotFoundError:
    print("Warning: dolphindb module is not installed.")
from trader.data_pipeline.crawlers.tick_crawler import StockTickCrawler
from trader.data_pipeline.utils.crawler_tools import CrawlerTools
from trader.data_pipeline.utils.stock_tick_tools import StockTickTools

from trader.config import (
    TICK_DOWNLOADS_PATH,
    TICK_DB_PATH,
    TICK_DB_NAME,
    TICK_TABLE_NAME,
    DDB_PATH,
    DDB_HOST,
    DDB_PORT,
    DDB_USER,
    DDB_PASSWORD
)


class StockTickManager:
    """ 管理上市與上櫃股票的三大法人 tick 資料，整合爬取、清洗與寫入資料庫等流程 """

    def __init__(self):
        self.session: ddb.session = ddb.session()
        self.session.connect(DDB_HOST, DDB_PORT, DDB_USER, DDB_PASSWORD)

        if (self.session.existsDatabase(TICK_DB_PATH)):
            print("Database exists!")

            # Set TSDBCacheEngineSize to 5GB (must < 8(maxMemSize) * 0.75 GB)
            script: str = """
            memSize = 2
            setTSDBCacheEngineSize(memSize)
            print("TSDBCacheEngineSize: " + string(getTSDBCacheEngineSize() / pow(1024, 3)) + "GB")
            """
            self.session.run(script)
        else:
            print("Database doesn't exist!")

        # Tick Crawler
        self.crawler: StockTickCrawler = StockTickCrawler()


    def update_table(self, dates: List[datetime.date]) -> None:
        """ Tick Database 資料更新（Multi-threading） """

        self.crawler.crawl_ticks_multithreaded(dates)
        self.add_to_ddb()


    def widget(self) -> None:
        """ Tick Database 資料更新 UI """

        # Set update date
        date_picker_from: widgets.DatePicker = widgets.DatePicker(description='from', disabled=False)
        date_picker_to: widgets.DatePicker = widgets.DatePicker(description='to', disabled=False)

        date_picker_from.value = StockTickTools.get_table_latest_date() + datetime.timedelta(days=1)
        date_picker_to.value = datetime.date.today()

        # Set update button
        btn: widgets.Button = widgets.Button(description='update')

        # Define update button behavior
        def onupdate(_):
            start_date: Optional[datetime.date] = date_picker_from.value
            end_date: Optional[datetime.date] = date_picker_to.value

            if not start_date or not end_date:
                print("Please select both start and end dates.")
                return

            dates: List[datetime.date] = CrawlerTools.generate_date_range(start_date, end_date)

            if not dates:
                print("Date range is empty. Please check if the start date is earlier than the end date.")
                return

            print(f"Updating data for table '{TICK_TABLE_NAME}' from {dates[0]} to {dates[-1]}...")
            self.update_table(dates)

        btn.on_click(onupdate)

        label: widgets.Label = widgets.Label(
            f"""
            {TICK_TABLE_NAME} (from {StockTickTools.get_table_earliest_date()} to
            {StockTickTools.get_table_latest_date()})
            """
        )
        items: List[widgets.Widget] = [date_picker_from, date_picker_to, btn]
        display(widgets.VBox([label, widgets.HBox(items)]))


    def create_tick_dolphinDB(self) -> None:
        """ 創建 dolphinDB """

        start_time: str = '2020.03.01'
        end_time: str = '2030.12.31'

        if self.session.existsDatabase(TICK_DB_PATH):
            print("Database exists!")
        else:
            print("Database doesn't exist!\nCreating a database...")
            script: str = f"""
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


    def append_csv_to_dolphinDB(self, csv_path: str) -> None:
        """ 將單一 CSV 資料添加到已建立的 DolphinDB 資料表 """

        script: str = f"""
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


    def append_all_csv_to_dolphinDB(self, dir_path: Path) -> None:
        """ 將資料夾內所有 CSV 檔案附加到已建立的 DolphinDB 資料表 """

        # read all csv files in dir_path (.as_posix => replace \\ with / (for windows os))
        csv_files: List[str] = [str(csv.as_posix()) for csv in dir_path.glob("*.csv")]
        print(f"* Total csv files: {len(csv_files)}")

        script: str = f"""
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


    def add_to_ddb(self) -> None:
        """ 將資料夾中的所有 CSV 檔存入 tick 的 DolphinDB 中 """

        self.append_all_csv_to_dolphinDB(TICK_DOWNLOADS_PATH)
        shutil.rmtree(TICK_DOWNLOADS_PATH)


    def clear_all_cache(self) -> None:
        """ 清除 Cache Data """

        script: str = """
        clearAllCache()
        """
        self.session.run(script)


    def delete_dolphinDB(self, db_path: str) -> None:
        """ 刪除資料庫 """

        print("Start deleting database...")

        script: str = f"""
        if (existsDatabase("{db_path}")) {{
            dropDatabase("{db_path}")
        }}
        """
        self.session.run(script)

        if (self.session.existsDatabase(db_path)):
            print("Delete database unsuccessfully!")
        else:
            print("Delete database successfully!")