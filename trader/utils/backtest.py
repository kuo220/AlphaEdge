import datetime
from typing import List, Dict, Tuple, Any
from utils.constant import Commission


""" 
* This section mainly consists of tools used for backtesting.
"""


class TradeRecord:
    """ 單筆交易紀錄 """
    
    def __init__(self, code: str="", volume: float=0.0,
                 buy_date: datetime.date=None, buy_price: float=0.0, 
                 sell_date: datetime.date=None, sell_price: float=0.0, 
                 profit: float=0.0, roi: float=0.0):
        self.code = code
        self.volume = volume
        self.buy_date = buy_date
        self.buy_price = buy_price
        self.sell_date = sell_date
        self.sell_price = sell_price
        self.profit = profit
        self.ROI = roi
        

class Trade:
    """ 回測交易等工具 """
    
    @staticmethod
    def buy(stock: Dict[str, Any], account: Dict[str, Any]) -> TradeRecord:
        """ 
        - Description: 買入股票
        - Parameters:
            - stock: Dict[str, Any]
                目標股票的資訊
            - account: Dict[str, Any]
                帳戶資訊
            - discount: float
                券商手續費折扣
            - lowest_fee: int
                券商最低手續費
        - Return:
            - record: TradeRecord
        """
        
        record: TradeRecord = TradeRecord()
        buy_cost = stock['price'] * stock['volume'] + max(stock['price'] * stock['volume'] * Commission.Rate * Commission.Discount, Commission.MinFee)
        if account['balance'] >= buy_cost:
            account['balance'] -= buy_cost
            record = TradeRecord(code=stock['code'], volume=stock['volume'], buy_date=stock['buy_date'], buy_price=stock['price'])    
        return record
        