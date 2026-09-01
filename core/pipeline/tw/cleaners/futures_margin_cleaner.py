import csv
import datetime
import re
from io import StringIO
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from loguru import logger

from core.config import FUTURES_MARGIN_DOWNLOADS_PATH
from core.pipeline.shared.base_cleaner import BaseDataCleaner
from core.utils import FUTURES_MULTIPLIER, FileEncoding

"""
台期貨保證金清洗（指數類）

1. **生效日取自檔案第一行的「更新日期」，不是抓取日**
    那是這組保證金**開始適用**的日子。同一組保證金連抓 30 天只會產生 1 列
    （主鍵相同被 loader 的 `INSERT OR IGNORE` 擋掉），本表是**變動序列**
    不是每日快照——這正是它能回答「某日生效的保證金是多少」的原因。

2. **一律用 `csv` 模組解析，不可 `split(",")`**
    每列尾端有多餘的逗號，且股票類（S3）的公司名稱含 `"...Co., Ltd."`；
    用 split 會靜默錯位（實測把 `Ltd.` 讀成級距值）。

3. **契約乘數比例是免費的正確性檢查，但只在同一標的指數內成立**
    同一個標的指數的大小台，保證金與乘數等比例——2026-09-01 實測
    加權指數 TX(200) 701,000／MTX(50) 175,250／TMF(10) 35,050 皆為每點 3,505 元。
    **但跨指數不成立**：電子每點 244.50、金融每點 158.00，因為那是三個不同的指數。
    故檢查必須**分家族做**，拿 TX 去比 TE 會誤判成解析錯誤。

4. **只收得進 `FUTURES_MULTIPLIER` 的商品**
    一覽表含選擇權的風險保證金 A／B／C 值與尚未登錄乘數的商品；
    前者語意完全不同（不是每口金額），後者連 PnL 都算不出來。
    兩者一律不入庫，並在 log 列出被濾掉的名稱供人工複查。
"""

# 「更新日期:2026/08/12」——冒號可能是全形或半形
EFFECTIVE_DATE_PATTERN: str = r"更新日期[:：]\s*(\d{4})/(\d{1,2})/(\d{1,2})"

# 指數類一覽表的表頭欄位（第二行）
INDEX_MARGIN_HEADER: List[str] = [
    "商品別",
    "結算保證金",
    "維持保證金",
    "原始保證金",
]

# 中文商品名 → `FUTURES_MULTIPLIER` 的契約代碼。
#
# **來源沒有代碼欄，只有中文名**，故此表不可省。名稱以 TAIFEX 一覽表 2026-09-01
# 的實際用字為準（「小型臺指」沒有「期貨」二字，「微型臺指期貨」有），
# 對不上的一律跳過而不猜——猜錯會把某商品的保證金掛到另一個商品上。
PRODUCT_NAME_TO_CODE: Dict[str, str] = {
    "臺股期貨": "TX",
    "小型臺指": "MTX",
    "微型臺指期貨": "TMF",
    "電子期貨": "TE",
    "小型電子期貨": "ZEF",
    "金融期貨": "TF",
    "小型金融期貨": "ZFF",
}

# 契約代碼 → 標的指數家族。
#
# **只用於乘數比例檢查**（見本檔說明第 3 點）：同一家族的大小台保證金與乘數等比例，
# 跨家族則否。不屬於任何家族的商品會被跳過檢查而非判為錯誤。
PRODUCT_INDEX_FAMILY: Dict[str, str] = {
    "TX": "TAIEX",
    "MTX": "TAIEX",
    "TMF": "TAIEX",
    "TE": "ELECTRONIC",
    "ZEF": "ELECTRONIC",
    "TF": "FINANCE",
    "ZFF": "FINANCE",
}


class FuturesMarginCleaner(BaseDataCleaner):
    """Futures Margin Cleaner（指數類）"""

    # 乘數比例檢查的容許誤差；TAIFEX 的數值是整數且等比例，實務上誤差為 0
    MULTIPLIER_RATIO_TOLERANCE: float = 1e-6

    def __init__(self):
        super().__init__()

        # Downloads directory Path
        self.margin_dir: Path = FUTURES_MARGIN_DOWNLOADS_PATH

        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Cleaner"""

        # 主鍵為 (effective_date, product)：本表是變動序列，不是每日快照
        self.margin_cleaned_cols: List[str] = [
            "effective_date",
            "product",
            "product_name",
            "結算保證金",
            "維持保證金",
            "原始保證金",
            "source",
        ]

        self.margin_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def parse_effective_date(text: str) -> Optional[datetime.date]:
        """
        - Description:
            自 CSV 原文解析「更新日期」作為生效日

            **解析不到一律回傳 None 而不退回今天**：退回今天會產生一列
            日期錯誤但看起來正常的資料，那比整批不入庫難查得多。
        - Parameters:
            - text: str
                CSV 原文
        - Return:
            - Optional[datetime.date]
                生效日；解析不到時為 None
        """

        match: Optional[re.Match] = re.search(EFFECTIVE_DATE_PATTERN, text)
        if match is None:
            return None

        year, month, day = (int(g) for g in match.groups())
        try:
            return datetime.date(year, month, day)
        except ValueError:
            return None

    def clean_index_margin(self, text: str) -> Optional[pd.DataFrame]:
        """
        - Description:
            清洗股價指數類的保證金一覽表
        - Parameters:
            - text: str
                crawler 取得的 CSV 原文（已 big5 解碼）
        - Return:
            - Optional[pd.DataFrame]
                清洗後的 DataFrame；生效日解析失敗、表頭不符或無有效列時為 None
        """

        if not text or not text.strip():
            logger.warning("[Futures Margin] 指數類 CSV 為空")
            return None

        effective_date: Optional[datetime.date] = self.parse_effective_date(text)
        if effective_date is None:
            # 沒有生效日就沒有主鍵，整批放棄
            logger.warning("[Futures Margin] 指數類 CSV 找不到更新日期，中止")
            return None

        rows: List[List[str]] = [
            [cell.strip() for cell in row]
            for row in csv.reader(StringIO(text))
            if any(cell.strip() for cell in row)
        ]

        header_index: Optional[int] = self.find_header_index(rows)
        if header_index is None:
            logger.warning(
                f"[Futures Margin] 指數類 CSV 表頭不符（預期 {INDEX_MARGIN_HEADER}），"
                f"可能為站方改版，中止"
            )
            return None

        records: List[Dict[str, object]] = []
        skipped: List[str] = []

        for row in rows[header_index + 1 :]:
            if len(row) < len(INDEX_MARGIN_HEADER):
                continue

            product_name: str = row[0]
            product: Optional[str] = PRODUCT_NAME_TO_CODE.get(product_name)
            if product is None:
                # 選擇權的 A／B／C 值與未登錄乘數的商品，見本檔說明第 4 點
                skipped.append(product_name)
                continue

            amounts: Optional[List[int]] = self.parse_amounts(row[1:4])
            if amounts is None:
                skipped.append(product_name)
                continue

            records.append(
                {
                    "effective_date": effective_date,
                    "product": product,
                    "product_name": product_name,
                    "結算保證金": amounts[0],
                    "維持保證金": amounts[1],
                    "原始保證金": amounts[2],
                    "source": "snapshot",
                }
            )

        if not records:
            logger.warning("[Futures Margin] 指數類 CSV 無有效列")
            return None

        if skipped:
            logger.info(
                f"* 未收錄 {len(skipped)} 項（選擇權風險保證金或乘數未登錄）：{skipped}"
            )

        df: pd.DataFrame = pd.DataFrame(records)[self.margin_cleaned_cols]

        if not self.check_multiplier_ratio(df):
            logger.warning(
                "[Futures Margin] 保證金與契約乘數的比例關係不成立，"
                "可能是欄位錯位或站方改制，中止入庫"
            )
            return None

        csv_path: Path = self.margin_dir / f"futures_margin_{effective_date:%Y%m%d}.csv"
        df.to_csv(csv_path, index=False, encoding=FileEncoding.UTF8_SIG.value)

        return df

    @staticmethod
    def find_header_index(rows: List[List[str]]) -> Optional[int]:
        """找出表頭所在的列；找不到回傳 None（代表版面改制）"""

        for i, row in enumerate(rows):
            if row[: len(INDEX_MARGIN_HEADER)] == INDEX_MARGIN_HEADER:
                return i
        return None

    @staticmethod
    def parse_amounts(cells: List[str]) -> Optional[List[int]]:
        """
        把三個金額欄轉成整數；任一欄不是純數字就回傳 None

        來源的數字不帶千分位，但仍先移除逗號以防站方改格式。
        """

        amounts: List[int] = []
        for cell in cells:
            digits: str = cell.replace(",", "").strip()
            if not digits.isdigit():
                return None
            amounts.append(int(digits))
        return amounts

    def check_multiplier_ratio(self, df: pd.DataFrame) -> bool:
        """
        - Description:
            以契約乘數的比例關係驗證解析結果（**分標的指數家族**）

            同一個標的指數的大小台，保證金與乘數等比例，故
            `原始保證金 / 乘數`（每點保證金）在家族內應為同一個值。
            欄位錯位或抓錯欄時這個關係立刻破裂。

            **不可跨家族比對**：2026-09-01 實測加權每點 3,505、電子 244.50、
            金融 158.00，三者本來就不同——拿 TX 去比 TE 會誤判成解析錯誤。

            只有一個成員的家族沒有可比對的對象，直接視為通過。
        - Parameters:
            - df: pd.DataFrame
                清洗後的 DataFrame
        - Return:
            - bool
                比例關係是否成立
        """

        per_point_by_family: Dict[str, List[float]] = {}
        for _, row in df.iterrows():
            family: Optional[str] = PRODUCT_INDEX_FAMILY.get(row["product"])
            if family is None:
                continue
            per_point: float = row["原始保證金"] / FUTURES_MULTIPLIER[row["product"]]
            per_point_by_family.setdefault(family, []).append(per_point)

        for family, values in per_point_by_family.items():
            baseline: float = values[0]
            if any(
                abs(value - baseline) > self.MULTIPLIER_RATIO_TOLERANCE
                for value in values
            ):
                logger.warning(
                    f"[Futures Margin] {family} 家族的每點保證金不一致：{values}"
                )
                return False

        return True
