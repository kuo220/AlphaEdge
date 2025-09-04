import datetime
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from trader.api.stock_tick_api import StockTickAPI
from trader.api.stock_price_api import StockPriceAPI
from trader.models import StockQuote, TickQuote
from trader.utils import Scale, StockUtils, Units


class StockQuoteAdapter:
    """
    將不同資料型態（Tick Data 或 Day Data）轉換為統一格式的 StockQuote 物件
    - 支援 Scale.TICK：從 tick dataframe 建立 TickQuote
    - 支援 Scale.DAY：從每日價格 dict 建立 StockQuote
    - 適用於回測框架中資料與策略之間的適配轉換
    """

    @staticmethod
    def convert_to_tick_quotes(
        data_api: StockTickAPI, date: datetime.date
    ) -> List[StockQuote]:
        """
        - Description:
            將指定日期的 Tick 資料轉換為 StockQuote 物件列表，用於 Tick 級回測
        - Parameters:
            - data_api: StockTickAPI
                StockTickAPI 物件
            - date: datetime.date
                要轉換的日期
        - Returns:
            - List[StockQuote]
                轉換後的 StockQuote 物件列表
        - Notes:
            一次取一天的 tick 資料，避免資料量太大 RAM 爆掉
        """

        # 一次取一天的 tick 資料，避免資料量太大 RAM 爆掉
        ticks: pd.DataFrame = data_api.get_ordered_ticks(date, date)

        return StockQuoteAdapter.generate_stock_quotes(ticks, date, Scale.TICK)

    @staticmethod
    def convert_to_day_quotes(
        data_api: StockPriceAPI, date: datetime.date
    ) -> List[StockQuote]:
        """
        - Description:
            將指定日期的 Stock Price API 日資料轉換為 StockQuote 物件列表，用於日級回測
        - Parameters:
            - data_api: StockPriceAPI
                StockPriceAPI 物件
            - date: datetime.date
                要轉換的日期
        - Returns:
            - List[StockQuote]
                轉換後的 StockQuote 物件列表
                Ex: [StockQuote(stock_id='0050', scale=Scale.DAY, date=datetime.date(2025, 7, 1), cur_price=48.64, volume=77081298, open=48.38, high=49.15, low=48.38, close=48.64, tick=None), StockQuote(stock_id='0051', scale=Scale.DAY, date=datetime.date(2025, 7, 1), cur_price=48.64, volume=77081298, open=48.38, high=49.15, low=48.38, close=48.64, tick=None), ...]
        """

        price_df: pd.DataFrame = data_api.get(date)

        # Type: Pandas(date='2025-07-01', stock_id='0050', 證券名稱='元大台灣50', 開盤價=48.38, 最高價=49.15, 最低價=48.38, 收盤價=48.64, 漲跌價差=0.28, 成交股數=77081298, 成交金額=3767256390, 成交筆數=50311, 最後揭示買價=48.63, 最後揭示買量=89, 最後揭示賣價=48.64, 最後揭示賣量=104, 本益比=0.0)
        # Ex: [Pandas(date='2025-07-01', stock_id='0050',...), Pandas(date='2025-07-01', stock_id='0051',...), ...]
        price_rows: List[Any] = [row for row in price_df.itertuples(index=False)]

        return StockQuoteAdapter.generate_stock_quotes(price_rows, date, Scale.DAY)

    @staticmethod
    def generate_stock_quotes(
        data: pd.DataFrame | List[Any],
        date: datetime.date,
        scale: Scale,
    ) -> List[StockQuote]:
        """
        - Description:
            根據當日資料建立有效的 StockQuote 清單
        - Parameters:
            - data: pd.DataFrame | List[Any]
                當日資料
            - date: datetime.date
                要轉換的日期
            - scale: Scale
                要轉換的 Scale
                1. 支援 Scale.DAY（從價格欄位 Dict 建立）
                2. 支援 Scale.TICK（從 tick dataframe 建立）
        - Returns:
            - List[StockQuote]
                轉換後的 StockQuote 物件列表
                Ex: [StockQuote(stock_id='0050', scale=Scale.DAY, date=datetime.date(2025, 7, 1), cur_price=48.64, volume=77081298, open=48.38, high=49.15, low=48.38, close=48.64, tick=None), StockQuote(stock_id='0051', scale=Scale.DAY, date=datetime.date(2025, 7, 1), cur_price=48.64, volume=77081298, open=48.38, high=49.15, low=48.38, close=48.64, tick=None), ...]
        """

        if scale == Scale.TICK:
            if data.empty:
                return []

            return [
                StockQuoteAdapter.generate_stock_quote(tick, tick.stock_id, date, scale)
                for tick in data.itertuples(index=False)
            ]

        elif scale == Scale.DAY:
            all_stock_ids: List[str] = [stock.stock_id for stock in data]

            # 過濾掉非一般股票（ETF、權證等）
            filtered_stock_ids: List[str] = StockUtils.filter_common_stocks(
                all_stock_ids
            )

            return [
                StockQuoteAdapter.generate_stock_quote(
                    stock, stock.stock_id, date, scale
                )
                for stock in data
                if stock.stock_id in filtered_stock_ids
            ]

    @staticmethod
    def generate_stock_quote(
        data: Any,
        stock_id: str,
        date: datetime.date,
        scale: Scale,
    ) -> StockQuote:
        """
        - Description:
            建立個股的 Stock Quote
        - Parameters:
            - data: Any
                當日資料
            - stock_id: str
                股票代號
            - date: datetime.date
                要轉換的日期
            - scale: Scale
                要轉換的 Scale
        - Returns:
            - StockQuote
                建立後的 StockQuote 物件
        """

        if scale == Scale.TICK:
            tick_quote: TickQuote = TickQuote(
                stock_id=data.stock_id,
                time=data.time,
                close=data.close,
                volume=data.volume,
                bid_price=data.bid_price,
                bid_volume=data.bid_volume,
                ask_price=data.ask_price,
                ask_volume=data.ask_volume,
                tick_type=data.tick_type,
            )
            return StockQuote(
                stock_id=data.stock_id, scale=scale, date=date, tick=tick_quote
            )

        elif scale == Scale.DAY:
            return StockQuote(
                stock_id=stock_id,
                scale=scale,
                date=date,
                cur_price=data.收盤價,
                volume=data.成交股數,
                open=data.開盤價,
                high=data.最高價,
                low=data.最低價,
                close=data.收盤價,
            )

        raise ValueError(f"Unsupported scale: {scale.name}")
