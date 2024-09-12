import numpy as np
import datetime
import shioaji as sj


class Stock:
    
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