import datetime

import pandas as pd

from trader.api import StockPriceAPI


class MarketCalendar:
    """Market Calendar"""

    def __init__(self):
        pass

    def check_stock_market_open(self, date: datetime.date) -> bool:
        """
        - Description: 判斷指定日期是否為台股開盤日
        - Parameters:
            - date: 要確認是否為開盤日的日期
        -Return:
            - bool
        """

        price = StockPriceAPI()
        df: pd.DataFrame = price.get(date)

        return True if not df.empty else False
