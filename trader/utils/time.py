import shioaji as sj
from shioaji.data import Ticks
import datetime


class TimeTools:
    """ 處理各式關於時間問題的工具 """
    
    @staticmethod
    def get_last_trading_date(api: sj.Shioaji, date: datetime.date) -> datetime.date:
        """ 取得前一個交易日日期 """
        
        stock_test: str = "2330" # 以 2330 判斷前一天是否有開盤
        last_trading_date: datetime.date = date - datetime.timedelta(days=1)
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
    
    
    @staticmethod
    def get_time_diff_in_sec(start_time: datetime.datetime, end_time: datetime.datetime) -> float:
        """ 計算兩時間的時間差（秒數） """
        
        time_diff: float = (end_time - start_time).total_seconds()
        time_diff = time_diff if time_diff >= 0 else 0
        return time_diff