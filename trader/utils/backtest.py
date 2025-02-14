import datetime
from typing import List


""" 
* This section mainly consists of tools used for backtesting.
"""


class TradeRecord():
    """ 單筆交易紀錄 """
    
    def __init__(self, stock_id: str, stock_share: float, stock_volume: float, 
                 buy_date: datetime.date, buy_price: float, 
                 sell_date: datetime.date=None, sell_price: float=None, 
                 profit: float=0.0, roi: float=0.0):  
        self.stock_id = stock_id
        self.stock_share = stock_share
        self.stock_volume = stock_volume
        self.buy_date = buy_date
        self.buy_price = buy_price
        self.sell_date = sell_date
        self.sell_price = sell_price
        self.profit = profit
        self.ROI = roi