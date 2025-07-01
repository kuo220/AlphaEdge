import datetime
from typing import List, Optional, Any
import ipywidgets as widgets
from IPython.display import display

from trader.crawler.crawlers.tick_crawler import StockTickCrawler
from trader.crawler.handlers.stock_tick_handler import StockTickHandler
from trader.crawler.utils.crawler_tools import CrawlerTools
from trader.crawler.utils.stock_tick_tools import StockTickTools

from trader.config import TICK_TABLE_NAME


class StockTickManager:
    """ 管理上市與上櫃股票的三大法人 tick 資料，整合爬取、清洗與寫入資料庫等流程 """

    def __init__(self):
        # Tick Crawler
        self.crawler: StockTickCrawler = StockTickCrawler()

        # Tick Handler
        self.handler: StockTickHandler = StockTickHandler()


    def update_table(self, dates: List[datetime.date]) -> None:
        """ Tick Database 資料更新（Multi-threading） """

        self.crawler.crawl_ticks_multithreaded(dates)
        self.handler.add_to_ddb()


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

        label: widgets.Label = widgets.Label(f"""{TICK_TABLE_NAME} (from {StockTickTools.get_table_earliest_date()} to
                              {StockTickTools.get_table_latest_date()})
                              """)
        items: List[widgets.Widget] = [date_picker_from, date_picker_to, btn]
        display(widgets.VBox([label, widgets.HBox(items)]))