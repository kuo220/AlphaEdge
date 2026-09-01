import datetime
import math
from typing import Any, List, Optional

import pandas as pd

from core.api.futures_price_api import FuturesPriceAPI
from core.models import FuturesQuote
from core.pipeline.utils.constant import FuturesPriceColumn
from core.utils import FuturesSession, Scale
from core.utils.constant import FUTURES_MULTIPLIER

"""
FuturesQuoteAdapter: 把 `FuturesPriceAPI` 的查詢結果轉成回測吃的 `FuturesQuote`

**只做型別轉換，不做任何選擇**。單日單商品會有多個到期月，本 adapter 一律**全部**
轉出，要哪一個由呼叫端決定——換月是政策，屬 Phase1-7（連續合約）與 Phase2-4
（換月規則參數化），寫進 adapter 會讓兩處各有一套換月邏輯。

與 `StockQuoteAdapter` 的差異：
- 沒有 `filter_common_stocks()` 這類過濾：期貨的商品清單由設定檔決定，不是從
  代號規則推出來的。
- 沒有還原價：期貨沒有除權息還原的概念。
- **同一根 bar 內出現重複 symbol 是正常的**——同一契約的日盤與夜盤是兩筆；
  因此 `session` 混用時不發重複警告，而是要求呼叫端指定時段。
"""


class FuturesQuoteAdapter:
    """將 `futures_price_daily` 的查詢結果轉換為統一格式的 `FuturesQuote` 物件"""

    @staticmethod
    def to_optional_float(value: Any) -> Optional[float]:
        """
        NULL／NaN 一律轉成 None，不轉成 0

        夜盤沒有結算價與未沖銷契約量，補成 0 會讓「沒有」與「等於 0」混為一談，
        而後者在逐日盯市與保證金計算裡是完全不同的意思。
        """

        if value is None:
            return None
        if isinstance(value, float) and math.isnan(value):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def to_optional_int(value: Any) -> Optional[int]:
        """同 `to_optional_float`，但用於未沖銷契約量這類整數欄位"""

        as_float: Optional[float] = FuturesQuoteAdapter.to_optional_float(value)
        return None if as_float is None else int(as_float)

    @staticmethod
    def convert_to_day_quotes(
        data_api: FuturesPriceAPI,
        date: datetime.date,
        product: Optional[str] = None,
        session: Optional[FuturesSession] = FuturesSession.DAY,
    ) -> List[FuturesQuote]:
        """
        - Description:
            將指定日期的行情轉為 `FuturesQuote` 清單（日級回測用）

            **當日所有到期月都會轉出**，不挑近月；`session` 的語意與
            `FuturesPriceAPI.get()` 相同（預設日盤）。
        - Parameters:
            - data_api: FuturesPriceAPI
                行情 API
            - date: datetime.date
                要轉換的日期
            - product: Optional[str]
                商品代碼；None 表示所有商品
            - session: Optional[FuturesSession]
                交易時段；None 表示日夜盤都取
        - Return:
            - List[FuturesQuote]
                轉換後的報價清單；查無資料時為空 list
        """

        price_df: pd.DataFrame = data_api.get(date, product=product, session=session)
        return FuturesQuoteAdapter.generate_futures_quotes(price_df, date, Scale.DAY)

    @staticmethod
    def generate_futures_quotes(
        data: pd.DataFrame,
        date: datetime.date,
        scale: Scale = Scale.DAY,
    ) -> List[FuturesQuote]:
        """
        - Description:
            由行情 DataFrame 建立 `FuturesQuote` 清單

            **乘數未登錄的商品直接跳過並不是選項**：`FUTURES_MULTIPLIER[product]`
            會 KeyError 當場中斷，理由見該常數的說明——乘數猜錯只會讓 PnL
            靜默偏掉。
        - Parameters:
            - data: pd.DataFrame
                行情資料（欄位為 `futures_price_daily` 的 schema）
            - date: datetime.date
                報價日期
            - scale: Scale
                報價級別；目前僅日線（Tick 屬 Phase5-1）
        - Return:
            - List[FuturesQuote]
                報價清單
        """

        if data is None or data.empty:
            return []

        return [
            FuturesQuoteAdapter.generate_futures_quote(row, date, scale)
            for row in data.itertuples(index=False)
        ]

    @staticmethod
    def generate_futures_quote(
        row: Any,
        date: datetime.date,
        scale: Scale = Scale.DAY,
    ) -> FuturesQuote:
        """
        - Description:
            由單列行情建立一個 `FuturesQuote`

            `cur_price` 取收盤價，與 `StockQuoteAdapter` 的日線行為一致。
        - Parameters:
            - row: Any
                `itertuples()` 產出的單列
            - date: datetime.date
                報價日期
            - scale: Scale
                報價級別
        - Return:
            - FuturesQuote
                報價物件
        """

        close: float = getattr(row, FuturesPriceColumn.CLOSE.value)
        product: str = str(row.product)

        return FuturesQuote(
            product=product,
            expiry=str(row.expiry),
            scale=scale,
            date=date,
            cur_price=close,
            volume=int(getattr(row, FuturesPriceColumn.VOLUME.value) or 0),
            open=getattr(row, FuturesPriceColumn.OPEN.value),
            high=getattr(row, FuturesPriceColumn.HIGH.value),
            low=getattr(row, FuturesPriceColumn.LOW.value),
            close=close,
            session=FuturesSession(row.session),
            settlement_price=FuturesQuoteAdapter.to_optional_float(
                getattr(row, FuturesPriceColumn.SETTLEMENT.value)
            ),
            open_interest=FuturesQuoteAdapter.to_optional_int(
                getattr(row, FuturesPriceColumn.OPEN_INTEREST.value)
            ),
            multiplier=FUTURES_MULTIPLIER[product],
        )
