from pathlib import Path
import datetime
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional, Any, Union

from trader.data import Data, Chip, Tick, QXData
from trader.models import (
    StockAccount, 
    TickQuote,
    StockQuote, 
    StockOrder,
    StockTradeRecord
)
from trader.utils import (
    StockTools,
    Commission,
    Market,
    Scale,
    PositionType, 
    Units
)
from trader.strategies.stock import Strategy


class StockQuoteAdapter:
    """
    將不同資料型態（Tick Data 或 Day Data）轉換為統一格式的 StockQuote 物件
    - 支援 Scale.TICK：從 tick dataframe 建立 TickQuote
    - 支援 Scale.DAY：從每日價格 dict 建立 StockQuote
    - 適用於回測框架中資料與策略之間的適配轉換
    """
    
    
    @staticmethod
    def convert_to_tick_quotes(data: Tick, date: datetime.date) -> List[StockQuote]:
        """ 將指定日期的 Tick 資料轉換為 StockQuote 物件列表，用於 Tick 級回測 """
        
        # 一次取一天的 tick 資料，避免資料量太大 RAM 爆掉    
        ticks: pd.DataFrame = data.get_ordered_ticks(date, date)
    
        return StockQuoteAdapter.generate_stock_quotes(ticks, date, Scale.TICK)
    
    
    @staticmethod
    def convert_to_day_quotes(data: QXData, date: datetime.date) -> List[StockQuote]:
        """ 將指定日期的 QXData 日資料轉換為 StockQuote 物件列表，用於日級回測 """
        
        data.date = date
        
        day_data: Dict[str, pd.Series] = {
            'open': data.get('price', '開盤價', 1).iloc[0],
            'high': data.get('price', '最高價', 1).iloc[0],
            'low': data.get('price', '最低價', 1).iloc[0],
            'close': data.get('price', '收盤價', 1).iloc[0],
            'volume': data.get('price', '成交股數', 1).iloc[0],
        }
        
        return StockQuoteAdapter.generate_stock_quotes(day_data, date, Scale.DAY)
        
        
    @staticmethod
    def generate_stock_quotes(
        data: Union[Dict[str, pd.Series], pd.DataFrame], 
        date: datetime.date, 
        scale: Scale, 
    ) -> List[StockQuote]:
        """ 
        根據當日資料建立有效的 StockQuote 清單
        - 支援 Scale.DAY（從價格欄位 Dict 建立）
        - 支援 Scale.TICK（從 tick dataframe 建立）
        """
        
        if scale == Scale.TICK:
            if data.empty:
                return []
            
            return [
                StockQuoteAdapter.generate_stock_quote(tick.stock_id, scale, date, tick) 
                for tick in data.itertuples(index=False)
            ]
        
        elif scale == Scale.DAY:
            codes: List[str] = StockTools.filter_common_stocks(list(data['open'].index))
            
            return [
                StockQuoteAdapter.generate_stock_quote(code, scale, date, data)
                for code in codes
                if code in data['open'].index
            ]
    
    
    @staticmethod
    def generate_stock_quote(
        data: Union[Dict[str, pd.Series], Any], 
        code: str,
        date: datetime.date,
        scale: Scale
    ) -> StockQuote:
        """ 建立個股的 Stock Quote """
        
        if scale == Scale.TICK:
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
                scale=scale,
                date=date,
                tick=tick_quote
            )
                        
        elif scale == Scale.DAY:
            return StockQuote(
                code=code,
                scale=scale,
                date=date,
                cur_price=data['close'][code],
                volume=data['volume'][code],
                open=data['open'][code],
                high=data['high'][code],
                low=data['low'][code],
                close=data['close'][code]
            )

        raise ValueError(f"Unsupported scale: {scale.name}")