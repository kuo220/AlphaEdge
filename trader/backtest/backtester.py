from pathlib import Path
import datetime
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional, Any, Union

# Add parent directory to path
import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))

# Local imports
from data import Data, Chip, Tick, QXData
from models import (
    StockAccount, 
    TickQuote,
    StockQuote, 
    StockOrder,
    StockTradeRecord
)
from utils import (
    StockTools,
    Commission,
    Market,
    Scale,
    PositionType, 
    Units
)
from strategies.stock import Strategy


"""
Backtesting engine that simulates trading based on strategy signals.

Includes:
- Tick/day backtest flow
- Position and account management
- Order execution logic
- Strategy integration for various financial instruments
"""


class Backtester:
    """ 
    Backtest Framework
    - Time Interval：
        1. Ticks
        2. Daily price
    """
    
    # === Init & Data Loading ===
    def __init__(self, strategy: Strategy):
        """ === Strategy & Account information === """
        self.strategy: Strategy = strategy                                      # 要回測的策略
        self.account: StockAccount = self.account                               # 虛擬帳戶資訊
        
        """ === Datasets === """
        self.data: Data = Data()                                                
        self.tick: Optional[Tick] = None                                        # Ticks data
        self.chip: Optional[Chip] = None                                        # Chips data
        self.qx_data: Optional[QXData] = None                                   # Day price data, Financial data, etc
        
        """ === Backtest Parameters === """
        self.scale: str = self.strategy.scale                                   # 回測 KBar 級別
        self.max_positions: Optional[int] = self.strategy.max_positions         # 最大持倉檔數
        self.start_date: datetime.date = self.strategy.start_date               # 回測起始日
        self.cur_date: datetime.date = self.strategy.start_date                 # 回測當前日
        self.end_date: datetime.date = self.strategy.end_date                   # 回測結束日
        
    
    def load_datasets(self):
        """ 從資料庫載入資料 """
        
        self.chip = self.data.Chip
        if self.scale == Scale.TICK:
            self.tick = self.data.Tick
        elif self.scale == Scale.DAY:
            self.qx_data = self.data.QXData
        elif self.scale == Scale.MIX:
            self.tick = self.data.Tick
            self.qx_data = self.data.QXData
            
    
    # === Main Backtest Loop ===
    def run(self):
        """ 執行 Backtest (目前只有全tick回測) """
        
        print("========== Backtest Start ==========")
        print(f"* Strategy Name: {self.strategy.strategy_name}")
        print(f"* {self.start_date.strftime('%Y/%m/%d')} ~ {self.end_date.strftime('%Y/%m/%d')}")
        print(f"* Initial Capital: {self.strategy.init_capital}")
        print(f"* Backtest Scale: {self.scale}")
        
        # load backtest dataset
        self.load_datasets()
        
        while self.cur_date <= self.end_date:
            print(f"--- {self.cur_date.strftime('%Y/%m/%d')} ---")
            
            if not StockTools.check_market_open(self.qx_data, self.cur_date):
                print("* Stock Market Close\n")
                continue
            
            if self.scale == Scale.TICK:
                self.run_tick_backtest()

            elif self.scale == Scale.DAY:
                self.run_day_backtest()
            
            elif self.scale == Scale.MIX:
                self.run_mix_backtest()
            
            self.cur_date += datetime.timedelta(days=1)
    
        self.account.update_account_status()
    
    
    def run_tick_backtest(self):
        """ Tick 級別的回測架構 """
        
        # 一次取一天的 tick 資料，避免資料量太大 RAM 爆掉
        ticks: pd.DataFrame = self.tick.get_ordered_ticks(self.cur_date, self.cur_date)
        
        stock_quotes: List[StockQuote] = self.generate_valid_stock_quotes(ticks)
            
        self.execute_close_signal(stock_quotes)
        self.execute_open_signal(stock_quotes)
            
            
    def run_day_backtest(self):
        """ Day 級別的回測架構 """
        
        self.qx_data.date = self.cur_date
        data = {
            'open': self.qx_data.get('price', '開盤價', 1).iloc[0],
            'high': self.qx_data.get('price', '最高價', 1).iloc[0],
            'low': self.qx_data.get('price', '最低價', 1).iloc[0],
            'close': self.qx_data.get('price', '收盤價', 1).iloc[0],
            'volume': self.qx_data.get('price', '成交股數', 1).iloc[0]
        }
        
        # Stock Quotes
        stock_quotes: List[StockQuote] = self.get_valid_stock_quotes(data)
    
        self.execute_close_signal(stock_quotes)
        self.execute_open_signal(stock_quotes)
                
            
    def run_mix_backtest(self):
        """ Tick & Day 級別的回測架構 """
        pass
    
    
    # === Signal Execution ===
    def execute_open_signal(self, stock_quotes: List[StockQuote]):
        """ 若倉位數量未達到限制且有開倉訊號，則執行開倉 """
        
        open_orders: List[StockOrder] = self.strategy.check_open_signal(stock_quotes)
        if self.max_positions is not None:
            remaining_positions: int = max(0, self.max_positions - self.account.get_position_count())
            open_orders = open_orders[:remaining_positions]
            
        for order in open_orders:
            self.place_open_order(order)
            
    
    def execute_close_signal(self, stock_quotes: List[StockQuote]):
        """ 執行平倉邏輯：先判斷停損訊號，後判斷一般平倉 """
        
        # 先找出有持倉的股票
        positions: List[StockQuote] = [sq for sq in stock_quotes if self.account.check_has_position(sq.code)]
        
        if not positions:
            return
            
        stop_loss_orders: List[StockOrder] = self.strategy.check_stop_loss_signal(positions)
        for order in stop_loss_orders:
            self.place_close_order(order)
        
        # 停損執行後重新確認剩下的持倉
        remaining_positions: List[StockQuote] = [sq for sq in stock_quotes if self.account.check_has_position(sq.code)]
        
        close_orders: List[StockOrder] = self.strategy.check_close_signal(remaining_positions)
        for order in close_orders:
            self.place_close_order(order)

    
    # === Order Placement ===
    def place_open_order(self, stock: StockOrder) -> Optional[StockTradeRecord]:
        """ 
        - Description: 開倉下單股票
        - Parameters:
            - stock: StockOrder
                目標股票的訂單資訊
        - Return:
            - position: StockTradeRecord
        """
        
        position: Optional[StockTradeRecord] = None
        
        position_value = stock.price * stock.volume * Units.LOT
        open_cost = StockTools.calculate_transaction_commission(buy_price=stock.price, volume=stock.volume)
        
        if stock.position_type == PositionType.LONG:
            if self.account.balance >= (position_value + open_cost):
                print(f"* Place Open Order: {stock.code}")
                
                self.account.trade_id_counter += 1
                self.account.balance -= (position_value + open_cost)
                
                position = StockTradeRecord(id=self.account.trade_id_counter, code=stock.code, date=stock.date,
                                            position_type=stock.position_type,
                                            buy_price=stock.price, volume=stock.volume, 
                                            commission=open_cost, transaction_cost=open_cost,
                                            position_value=position_value)
                
                self.account.positions.append(position)
                self.account.trade_records[position.id] = position

        return position


    def place_close_order(self, stock: StockOrder) -> Optional[StockTradeRecord]:
        """
        - Description: 下單平倉股票
        - Parameters:
            - stock: StockOrder
                目標股票的訂單資訊
        - Return:
            - position: StockTradeRecord
        """

        position_value = stock.price * stock.volume * Units.LOT
        close_cost = StockTools.calculate_transaction_commission(sell_price=stock.price, volume=stock.volume)
        
        # 根據 stock.code 找出庫存中最早買進的該檔股票（FIFO）
        position: Optional[StockTradeRecord] = self.account.get_first_open_position(stock.code)
        
        if position is not None and not position.is_closed:
            print(f"* Place Close Order: {stock.code}")
            
            if position.position_type == PositionType.LONG:
                position.date = stock.date
                position.is_closed = True
                position.sell_price = stock.price
                position.commission += close_cost
                position.tax = StockTools.calculate_transaction_tax(stock.price, stock.volume)
                position.transaction_cost = position.commission + position.tax
                position.realized_pnl = StockTools.calculate_net_profit(position.buy_price, position.sell_price, position.volume)
                position.roi = StockTools.calculate_roi(position.buy_price, position.sell_price, position.volume)
                
                self.account.balance += (position_value - close_cost)
                self.account.trade_records[position.id] = position                                     # 根據 position.id 更新 trade_records 中對應到的 position                
                self.account.positions = [p for p in self.account.positions if p.id != position.id]    # 每一筆開倉的部位都會記錄一個 id，因此這邊只會刪除對應到 id 的部位

        return position
    
    
    def generate_valid_stock_quotes(self, data: Union[Dict[str, pd.Series], pd.DataFrame]) -> List[StockQuote]:
        """ 
        根據當日資料建立有效的 StockQuote 清單
        - 支援 Scale.DAY（從價格欄位 Dict 建立）
        - 支援 Scale.TICK（從 tick dataframe 建立）
        """
        
        if self.scale == Scale.TICK:
            if data.empty:
                return []
            
            return [
                self.generate_stock_quote(tick.stock_id, tick) 
                for tick in data.itertuples(index=False)
            ]
        
        elif self.scale == Scale.DAY:
            codes: List[str] = StockTools.filter_common_stocks(list(data['open'].index))
            
            return [
                self.generate_stock_quote(code, data)
                for code in codes
                if code in data['close']  # 保險
            ]

    
    def generate_stock_quote(self, code: str, data: Union[Dict[str, pd.Series], Any]) -> StockQuote:
        """ 建立個股的 Stock Quote """
        
        if self.scale == Scale.TICK:
            tick_quote: TickQuote = TickQuote(
                code=data.stock_id,
                time=data.time,
                close=data.close,
                volume=data.volume,
                bid_price=data.bid_price,
                bid_volume=data.bid_volume,
                ask_price=data.ask_price,
                ask_volume=data.ask_volume,
                tick_type=data.tick_type
            )
            return StockQuote(
                code=data.stock_id,
                scale=self.scale,
                date=self.cur_date,
                tick=tick_quote
            )
                        
        elif self.scale == Scale.DAY:
            return StockQuote(
                code=code,
                scale=self.scale,
                date=self.cur_date,
                cur_price=data['close'][code],
                volume=data['volume'][code],
                open=data['open'][code],
                high=data['high'][code],
                low=data['low'][code],
                close=data['close'][code]
            )

        raise ValueError(f"Unsupported scale: {self.scale}")
    
    
    # === Report ===
    def generate_backtest_report(self):
        """ 生產回測報告 """
        pass