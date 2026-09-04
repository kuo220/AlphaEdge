import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd
from loguru import logger

"""
股票分割（拆股）的價格調整

**單獨成檔是為了讓 reporter 與 analyzer 用同一份**：分割調整表寫在誰身上，
另一邊就得再抄一次，而抄漏一次分割的代價是整段序列從那天起錯 N 倍
（0050 在 2025-06-18 一拆四，漏掉就是 −75% 的假跌幅）。

**為什麼不能只靠 `StockPriceAPI.get_adjusted_close_series()`**：還原價的累積因子
來自 `stock_dividend`，那張表記的是除權息，**不含分割**——實測 0050 在
2025-06-17 與 2025-06-18 的累積因子完全相同（1.4545），還原價因此在分割日
留下一個 −74.8% 的假跳空。修 ETL 是另一條線的工作，在那之前分割仍得由本表補上。
"""


# 股票分割配置：{股票代號: [(分割日期, 分割比例), ...]}
# 分割比例格式：1:4 表示 1 拆 4（1 股變成 4 股，調整因子為 4）
STOCK_SPLITS: Dict[str, List[Tuple[datetime.date, float]]] = {
    "0050": [(datetime.date(2025, 6, 18), 4.0)],  # 2025/06/18 1 拆 4
}

# 分割調整差異超過此 % 發出警告
SPLIT_ADJUSTMENT_WARNING_PCT: float = 5.0


def apply_split_adjustment(
    price_series: pd.Series,
    stock_id: str,
    warning_pct: float = SPLIT_ADJUSTMENT_WARNING_PCT,
) -> pd.Series:
    """
    - Description:
        計算調整後價格（處理股票分割，支援多次分割）

        對於股票分割（如 1 拆 4），分割日期及之後的價格需要乘以調整因子（4），
        這樣可以確保價格序列的連續性。

        範例（單次分割）：
        - 分割前 100 元（保持原樣）
        - 分割後 25 元 → 調整後 100 元（25 × 4）
        - 這樣可以確保價格序列連續：100 → 100，而不是 100 → 25

        範例（多次分割）：假設 2025/06/18 1 拆 4、2025/12/18 1 拆 2，
        則 2025/12/18 之後的累積調整因子為 4 × 2 = 8。

        實現邏輯：
        1. 對於每個日期，計算其累積調整因子（所有在該日期之前或當天的分割的累積）
        2. 將原始價格乘以對應的累積調整因子
        3. 這樣可以確保不同分割後的日期使用正確的調整因子
    - Parameters:
        - price_series: pd.Series
            原始價格序列（已排序）
        - stock_id: str
            股票代號
        - warning_pct: float
            分割當天與前一天的調整後價差超過此 % 時發出警告
    - Return:
        - pd.Series
            調整後價格序列；該股無分割紀錄時原樣回傳
    """

    if stock_id not in STOCK_SPLITS:
        return price_series

    adjusted_price: pd.Series = price_series.copy()
    splits: List[Tuple[datetime.date, float]] = STOCK_SPLITS[stock_id]

    # 確保索引是 date 類型，並排序
    if len(adjusted_price) > 0:
        # 轉換索引為 date 類型（如果還不是）
        if not isinstance(adjusted_price.index[0], datetime.date):
            adjusted_price.index = pd.to_datetime(adjusted_price.index).date  # type: ignore
        # 確保索引是 date 類型的列表
        index_dates: List[datetime.date] = [
            d if isinstance(d, datetime.date) else pd.to_datetime(d).date()
            for d in adjusted_price.index
        ]
        adjusted_price.index = pd.Index(index_dates)

    adjusted_price: pd.Series = adjusted_price.sort_index()

    # 按日期排序（從舊到新）
    splits_sorted: List[Tuple[datetime.date, float]] = sorted(
        splits, key=lambda x: x[0]
    )

    # 標準化分割日期為 date 類型
    splits_normalized: List[Tuple[datetime.date, float]] = []
    for split_date, split_ratio in splits_sorted:
        split_date_normalized: datetime.date
        if isinstance(split_date, datetime.datetime):
            split_date_normalized = split_date.date()
        elif isinstance(split_date, str):
            split_date_normalized = datetime.datetime.strptime(
                split_date, "%Y-%m-%d"
            ).date()
        else:
            split_date_normalized = split_date  # type: ignore
        splits_normalized.append((split_date_normalized, split_ratio))

    # 方法：為每個日期計算其累積調整因子
    # 這樣可以確保不同分割後的日期使用正確的調整因子
    adjusted_result: pd.Series = adjusted_price.copy()

    for date in adjusted_price.index:
        # 計算該日期的累積調整因子
        cumulative_ratio: float = 1.0
        for split_date, split_ratio in splits_normalized:
            # 如果該日期 >= 分割日期，則應用該分割的調整因子
            if date >= split_date:
                cumulative_ratio *= split_ratio

        # 應用累積調整因子
        if cumulative_ratio != 1.0:
            adjusted_result.loc[date] = adjusted_price.loc[date] * cumulative_ratio

    # 記錄分割調整信息
    for split_date, split_ratio in splits_normalized:
        # 計算受影響的日期範圍
        mask: pd.Series = adjusted_price.index >= split_date
        num_adjusted: int = mask.sum()

        if num_adjusted > 0:
            # 計算該分割的累積調整因子（用於日誌）
            cumulative_ratio_for_split: float = 1.0
            for sd, sr in splits_normalized:
                if sd <= split_date:
                    cumulative_ratio_for_split *= sr

            # 記錄分割日期前一天的價格（如果存在），用於驗證調整是否正確
            price_before_split: Optional[float] = None
            dates_before: pd.Index = adjusted_price.index[
                adjusted_price.index < split_date
            ]
            if len(dates_before) > 0:
                price_before_split = adjusted_result.loc[dates_before[-1]]

            # 記錄分割日期當天的調整後價格（如果存在）
            price_on_split_date_after: Optional[float] = None
            if split_date in adjusted_result.index:
                price_on_split_date_after = adjusted_result.loc[split_date]
            else:
                dates_on_or_after: pd.Index = adjusted_price.index[
                    adjusted_price.index >= split_date
                ]
                if len(dates_on_or_after) > 0:
                    price_on_split_date_after = adjusted_result.loc[
                        dates_on_or_after[0]
                    ]

            logger.info(
                f"股票分割調整: {stock_id} 在 {split_date} 進行 1:{int(split_ratio)} 分割，"
                f"調整了 {num_adjusted} 筆價格數據（累積調整因子: {cumulative_ratio_for_split:.2f}）"
            )

            # 驗證調整是否正確：分割當天的調整後價格應該接近分割前一天的價格
            if price_on_split_date_after is not None and price_before_split is not None:
                diff_pct: float = (
                    abs(price_on_split_date_after - price_before_split)
                    / price_before_split
                    * 100
                )
                if diff_pct > warning_pct:
                    logger.warning(
                        f"警告：分割當天調整後價格 ({price_on_split_date_after:.2f}) 與分割前一天價格 ({price_before_split:.2f}) 差異較大 ({diff_pct:.2f}%)，"
                        f"可能表示分割比例配置不正確或數據有問題"
                    )
        else:
            logger.warning(
                f"股票分割調整: {stock_id} 在 {split_date} 的分割事件沒有找到需要調整的價格數據。"
                f"可用日期範圍: {adjusted_price.index.min()} ~ {adjusted_price.index.max()}"
            )

    return adjusted_result
