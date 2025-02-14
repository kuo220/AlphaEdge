import numpy as np
import datetime
import shioaji as sj
from utils.time import TimeTool


class Stock:
    """ 以 Shioaji 為基礎建立的 API Tool """
    
    @staticmethod
    def get_close_price(api: sj.Shioaji, stock_id: str, date: datetime.date) -> float:
        """ 取得指定股票在特定日期的收盤價 """
        
        tick = api.ticks(
            contract=api.Contracts.Stocks[stock_id],
            date=date.strftime("%Y-%m-%d"),
            query_type=sj.constant.TicksQueryType.LastCount,
            last_cnt=1
        )
        return tick.close[0] if len(tick.close) != 0 else np.nan
    

    @staticmethod
    def get_price_chg(api: sj.Shioaji, stock_id: str, date: datetime.date) -> float:
        """ 取得指定股票在指定日期的漲跌幅 """
        
        # 取得前一個交易日的日期
        last_trading_date = TimeTool.get_last_trading_date(api, date)
        
        # 計算指定交易日股票的漲幅
        cur_close_price = Stock.get_close_price(api, stock_id, date)
        prev_close_price = Stock.get_close_price(api, stock_id, last_trading_date)
        
        # if cur_close_price or prev_close_price is np.nan, then function will return np.nan
        return round((cur_close_price / prev_close_price - 1) * 100, 2)