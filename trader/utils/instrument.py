import numpy as np
import datetime
import shioaji as sj
from typing import Tuple
from utils.data import Data
from utils.time import TimeTools
from utils.constant import Commission


"""
instrument.py

Utility functions for asset trading calculations, including support for stocks, futures, and options.

Features:
- Retrieve close prices and price changes (via Shioaji API)
- Calculate commission, tax, net profit, and ROI
- Check if the market was open on a given date

Designed for use in backtesting and trading performance analysis.
"""


class StockTools:
    """ Stock Related Tools """
    
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
        last_trading_date = TimeTools.get_last_trading_date(api, date)
        
        # 計算指定交易日股票的漲幅
        cur_close_price = StockTools.get_close_price(api, stock_id, date)
        prev_close_price = StockTools.get_close_price(api, stock_id, last_trading_date)
        
        # if cur_close_price or prev_close_price is np.nan, then function will return np.nan
        return round((cur_close_price / prev_close_price - 1) * 100, 2)
    
    
    @staticmethod
    def calculate_transaction_commission(price: float, volume: float) -> float:
        """ 計算股票買賣時的手續費 """
        """
        For long position, the commission costs:
            - buy fee (券買手續費 = 成交價 x 成交股數 x 手續費率 x discount)
            - sell fee (券賣手續費 = 成交價 x 成交股數 x 手續費率 x discount)
        """
        return max(price * volume * Commission.CommRate * Commission.Discount, Commission.MinFee)
    
    
    @staticmethod
    def calculate_transaction_tax(price: float, volume: float) -> float:
        """ 計算股票賣出時的交易稅 """
        """ 
        For long position, the tax cost:
            - sell tax (券賣證交稅 = 成交價 x 成交股數 x 證交稅率)
        """
        return price * volume * Commission.TaxRate
        
    
    @staticmethod
    def calculate_transaction_cost(buy_price: float, sell_price: float, volume: float) -> Tuple[float, float]:
        """ 計算股票買賣的手續費、交易稅等摩擦成本 """
        """
        For long position, the transaction costs should contains:
            - buy fee (券買手續費 = 成交價 x 成交股數 x 手續費率 x discount)
            - sell fee (券賣手續費 = 成交價 x 成交股數 x 手續費率 x discount)
            - sell tax (券賣證交稅 = 成交價 x 成交股數 x 證交稅率)
        """

        # 買入 & 賣出的交易成本
        buy_transaction_cost = StockTools.calculate_transaction_commission(buy_price, volume)
        sell_transaction_cost = StockTools.calculate_transaction_commission(sell_price, volume) + StockTools.calculate_transaction_tax(sell_price, volume)
        return (buy_transaction_cost, sell_transaction_cost)
    

    @staticmethod
    def calculate_net_profit(buy_price: float, sell_price: float, volume: float) -> float:
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
        buy_comm, sell_comm = StockTools.calculate_transaction_cost(buy_price, sell_price, volume)
        
        profit = (sell_value - buy_value) - (buy_comm + sell_comm)
        return round(profit, 2)
    
    
    @staticmethod
    def calculate_roi(buy_price: float, sell_price: float, volume: float) -> float:
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
        buy_comm, _ = StockTools.calculate_transaction_cost(buy_price, sell_price, volume)
        
        # 計算投資成本
        investment_cost = buy_value + buy_comm
        if investment_cost == 0:
            return 0.0
        
        roi = (StockTools.calculate_net_profit(buy_price, sell_price, volume) / investment_cost) * 100
        return round(roi, 2)
    
    
    @staticmethod
    def check_market_open(data: Data, date: datetime.date) -> bool:
        """ 
        - Description: 判斷是否指定日期是否開盤
        - Parameters:
            - data: QuantX Data
            - date: 欲確認是否開盤之日期
        -Return:
            - bool
        """
        
        data.date = date
        close_price = data.get('price', '收盤價', 1)
        
        return True if close_price.index.date == date else False