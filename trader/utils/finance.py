import numpy as np
import datetime
import shioaji as sj
from typing import Tuple
from utils.time import TimeTool
from utils.constant import Commission


class Stock:
    """ Stock Related Tool """
    
    @staticmethod
    def get_close_price(api: sj.Shioaji, stock_id: str, date: datetime.date) -> float:
        """ Shioaji: 取得指定股票在特定日期的收盤價 """
        
        tick = api.ticks(
            contract=api.Contracts.Stocks[stock_id],
            date=date.strftime("%Y-%m-%d"),
            query_type=sj.constant.TicksQueryType.LastCount,
            last_cnt=1
        )
        return tick.close[0] if len(tick.close) != 0 else np.nan
    

    @staticmethod
    def get_price_chg(api: sj.Shioaji, stock_id: str, date: datetime.date) -> float:
        """ Shioaji: 取得指定股票在指定日期的漲跌幅 """
        
        # 取得前一個交易日的日期
        last_trading_date = TimeTool.get_last_trading_date(api, date)
        
        # 計算指定交易日股票的漲幅
        cur_close_price = Stock.get_close_price(api, stock_id, date)
        prev_close_price = Stock.get_close_price(api, stock_id, last_trading_date)
        
        # if cur_close_price or prev_close_price is np.nan, then function will return np.nan
        return round((cur_close_price / prev_close_price - 1) * 100, 2)
    
    
    @staticmethod
    def get_friction_cost(buy_price: float, sell_price: float, volume: float) -> Tuple[float, float]:
        """ 計算股票買賣的手續費、交易稅等摩擦成本 """
        """
        For long position, the friction costs should contains:
            - buy fee (券買手續費 = 成交價 x 成交股數 x 手續費率 x discount)
            - sell fee (券賣手續費 = 成交價 x 成交股數 x 手續費率 x discount)
            - sell tax (券賣證交稅 = 成交價 x 成交股數 x 證交稅率)
        """
        # 買入 & 賣出手續費
        buy_comm = max(buy_price * volume * Commission.CommRate * Commission.Discount, Commission.MinFee)
        sell_comm = max(sell_price * volume * Commission.CommRate * Commission.Discount, Commission.MinFee) + sell_price * volume * Commission.TaxRate
        
        return (buy_comm, sell_comm)
    

    @staticmethod
    def get_net_profit(buy_price: float, sell_price: float, volume: float) -> float:
        """ 
        - Description: 計算股票交易的淨收益（扣除手續費和交易稅）（目前只有做多）
        - Parameters:
            - buy_price: float
                股票買入價格
            - sell_price: float
                股票賣出價格
            - volume: float
                股數
        - Return:
            - profit: float
        """
        
        buy_value = buy_price * volume
        sell_value = sell_price * volume
        
        # 買入 & 賣出手續費
        buy_comm, sell_comm = Stock.get_friction_cost(buy_price, sell_price, volume)
        
        profit = (sell_value - buy_value) - (buy_comm + sell_comm)
        return round(profit, 2)
    
    
    @staticmethod
    def get_roi(buy_price: float, sell_price: float, volume: float) -> float:
        """ 
        - Description: 計算股票投資報酬率（ROI）（目前只有做多）
        - Parameters:
            - buy_price: float
                股票買入價格
            - sell_price: float
                股票賣出價格
            - volume: float
                股數
        - Return:
            - roi: float
                投資報酬率（%）
        """
        
        buy_value = buy_price * volume
        buy_comm, _ = Stock.get_friction_cost(buy_price, sell_price, volume)
        
        # 計算投資成本
        investment_cost = buy_value + buy_comm
        if investment_cost == 0:
            return 0.0
        
        roi = (Stock.get_net_profit(buy_price, sell_price, volume) / investment_cost) * 100
        return round(roi, 2)
        
        
        
        