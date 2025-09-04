import datetime

import pandas as pd
import shioaji as sj
from shioaji.data import Ticks

from trader.api import StockPriceAPI


class MarketCalendar:
    """Market Calendar"""

    @staticmethod
    def check_stock_market_open(data_api: StockPriceAPI, date: datetime.date) -> bool:
        """
        - Description: 判斷指定日期是否為台股開盤日
        - Parameters:
            - date: 要確認是否為開盤日的日期
        -Return:
            - bool
        """

        df: pd.DataFrame = data_api.get(date)
        return True if not df.empty else False

    @staticmethod
    def get_last_trading_date(
        api: sj.Shioaji | StockPriceAPI, date: datetime.date
    ) -> datetime.date:
        """取得前一個交易日日期"""

        stock_test: str = "2330"  # 以 2330 判斷前一天是否有開盤
        last_trading_date: datetime.date = date - datetime.timedelta(days=1)

        if isinstance(api, sj.Shioaji):
            tick: Ticks = api.ticks(
                contract=api.Contracts.Stocks[stock_test],
                date=last_trading_date.strftime("%Y-%m-%d"),
                query_type=sj.constant.TicksQueryType.LastCount,
                last_cnt=1,
            )

            while len(tick.close) == 0:
                last_trading_date = last_trading_date - datetime.timedelta(days=1)
                tick = api.ticks(
                    contract=api.Contracts.Stocks[stock_test],
                    date=last_trading_date.strftime("%Y-%m-%d"),
                    query_type=sj.constant.TicksQueryType.LastCount,
                    last_cnt=1,
                )
            return last_trading_date

        elif isinstance(api, StockPriceAPI):
            price_df: pd.DataFrame = api.get(last_trading_date)

            while price_df.empty:
                last_trading_date = last_trading_date - datetime.timedelta(days=1)
                price_df = api.get(last_trading_date)
            return last_trading_date

        else:
            raise ValueError("Invalid API type")
