import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from loguru import logger

from core.api.tw.stock_price_api import StockPriceAPI
from core.api.tw.stock_tick_api import StockTickAPI
from core.models import StockQuote, TickQuote
from core.utils import Scale
from core.utils.instrument import StockUtils


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
        data_api: StockPriceAPI,
        date: datetime.date,
        adjusted: bool = False,
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

        # 還原價只掛在 adj_close，OHLC 一律維持原始成交價；
        # 未啟用時 adj_close 為 None，StockQuote.signal_close 會退回 close，行為零改變
        adjusted_close_map: Dict[str, Any] = (
            data_api.get_adjusted_close_map(date) if adjusted else {}
        )

        # Type: Pandas(date='2025-07-01', stock_id='0050', 證券名稱='元大台灣50', 開盤價=48.38, 最高價=49.15, 最低價=48.38, 收盤價=48.64, 漲跌價差=0.28, 成交股數=77081298, 成交金額=3767256390, 成交筆數=50311, 最後揭示買價=48.63, 最後揭示買量=89, 最後揭示賣價=48.64, 最後揭示賣量=104, 本益比=0.0)
        # Ex: [Pandas(date='2025-07-01', stock_id='0050',...), Pandas(date='2025-07-01', stock_id='0051',...), ...]
        price_rows: List[Any] = [row for row in price_df.itertuples(index=False)]

        return StockQuoteAdapter.generate_stock_quotes(
            price_rows, date, Scale.DAY, adjusted_close_map
        )

    @staticmethod
    def generate_stock_quotes(
        data: pd.DataFrame | List[Any],
        date: datetime.date,
        scale: Scale,
        adjusted_close_map: Optional[Dict[str, Any]] = None,
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

            adjusted_close_map = adjusted_close_map or {}

            tradable: List[Any] = [
                stock
                for stock in data
                if stock.stock_id in filtered_stock_ids
                and StockQuoteAdapter.has_valid_price(stock)
            ]

            skipped: int = len(
                [stock for stock in data if stock.stock_id in filtered_stock_ids]
            ) - len(tradable)
            if skipped:
                logger.debug(f"{date}: 略過 {skipped} 檔無成交價的個股（無成交日）")

            quotes: List[StockQuote] = [
                StockQuoteAdapter.generate_stock_quote(
                    stock,
                    stock.stock_id,
                    date,
                    scale,
                    adjusted_close_map.get(stock.stock_id),
                )
                for stock in tradable
            ]

            StockQuoteAdapter.warn_duplicate_symbols(quotes, date)
            return quotes

    @staticmethod
    def warn_duplicate_symbols(quotes: List[StockQuote], date: datetime.date) -> None:
        """
        - Description:
            同一根 bar 內出現重複 symbol 時發出警告

            重複代表資料層無法唯一識別商品——例如上市股與上櫃 ETF 共用同一個
            4 碼代號。引擎後續會以 `{q.symbol: q for q in quotes}` 建對照表，
            重複的只會留下最後一筆，**成交價與訊號都可能取到另一檔商品**，
            而且整個過程不會有任何錯誤。

            這裡只警告不排除：要留哪一筆屬資料修正的範疇，靜默挑一筆才是更糟的選擇。
        - Parameters:
            - quotes: List[StockQuote]
                當根 bar 的報價
            - date: datetime.date
                當前交易日（僅供訊息辨識）
        """

        seen: Dict[str, int] = {}
        for quote in quotes:
            seen[quote.symbol] = seen.get(quote.symbol, 0) + 1

        duplicates: List[str] = [symbol for symbol, n in seen.items() if n > 1]
        if duplicates:
            logger.warning(
                f"[Quote] {date} 有 {len(duplicates)} 個代號對應多筆報價："
                f"{sorted(duplicates)[:10]}；建對照表時只會留下最後一筆，"
                f"請確認該代號是否被不同商品共用"
            )

    @staticmethod
    def has_valid_price(stock: Any) -> bool:
        """
        - Description:
            該列是否有可交易的成交價

            **無成交日的 OHLC 是 NULL（或歷史資料裡的 0）**：來源給的是 `--`，
            舊版 cleaner 填成 0 之後就變成「當天成交價是 0 元」，回測會照著它成交
            （健檢 F-037）。cleaner 已改為保留 NULL，這裡把兩種形態一起濾掉，
            讓尚未執行修復腳本的資料庫也不會拿 0 元價去成交。
        - Parameters:
            - stock: Any
                `price` 表的一列
        - Return:
            - bool
                收盤價存在且大於 0 為 True
        """

        close: Any = stock.收盤價
        if close is None or pd.isna(close):
            return False
        return float(close) > 0

    @staticmethod
    def generate_stock_quote(
        data: Any,
        stock_id: str,
        date: datetime.date,
        scale: Scale,
        adj_close: Optional[float] = None,
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
        - Notes:
            - Volume:
                - Scale.TICK: Unit 資料原本就是 Lot
                - Scale.DAY: Unit: Shares
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
                volume=StockUtils.convert_share_to_lot(data.成交股數),
                open=data.開盤價,
                high=data.最高價,
                low=data.最低價,
                close=data.收盤價,
                adj_close=adj_close,
            )

        raise ValueError(f"Unsupported scale: {scale.name}")
