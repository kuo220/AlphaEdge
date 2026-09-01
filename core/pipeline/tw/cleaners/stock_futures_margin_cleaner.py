import csv
import datetime
import re
from io import StringIO
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional

import pandas as pd
from loguru import logger

from core.config import FUTURES_MARGIN_DOWNLOADS_PATH
from core.pipeline.shared.base_cleaner import BaseDataCleaner
from core.pipeline.tw.cleaners.futures_margin_cleaner import EFFECTIVE_DATE_PATTERN
from core.utils import FileEncoding

"""
股票期貨保證金清洗

**這一份 CSV 有四個段落，每段的欄位語意與更新日期都不同**（2026-09-01 實查）：

| 段落 | 內容 | 欄位型態 | 該段的更新日期 |
|------|------|----------|----------------|
| 一(一) | 股票期貨（標的為**股票**） | **適用比例** ＋ 級距 | 2026/08/28 |
| 一(二) | 股票期貨（標的為**受益憑證／ETF**） | **每口固定金額** | 2026/08/12 |
| 二(一) | 股票選擇權（股票） | 比例，且是 `a%`／`b%` 雙欄 | 2026/08/14 |
| 二(二) | 股票選擇權（ETF） | `A值`／`B值` 固定金額，**一個商品佔兩列** | 2026/08/12 |

因此本 cleaner 的產出是**兩個 DataFrame**，不是一個：

- **比例**（一(一)）→ `stock_futures_margin_rate_history`
- **金額**（一(二)）→ `futures_margin_history`，與指數期貨同一張表

**分表的依據是「金額 vs 比例」，不是「指數 vs 股票」**——ETF 股期給的是每口固定
金額，語意與臺股期貨完全相同，硬要因為它是「股票類」而塞進比例表，只會讓比例欄
永遠是 NULL。

**選擇權兩段一律不收**：語意不是每口保證金（是風險保證金的參數），
且本專案目前沒有選擇權回測需求（見 `backlog/台期貨保證金ETL.md` 範圍界線）。

3. **級距欄可以是空的，而且那不是解析錯誤**——2026-09-01 實查 296 檔中有 15 檔
   （台玻、旺宏、南亞科、穩懋…）級距為空且比例更高（21.60%／22.95%／30.38%），
   那是**處置／注意股票的加成措施**。正常三個級距是 13.50%／16.20%／20.25%。
   空級距一律存成 NULL，**不可因此把該檔丟掉**。

其餘兩個實測撞到的坑：
1. **每段各有自己的「更新日期」**，不是全檔一個——用第一個找到的日期套用到全部
   會讓 ETF 股期的生效日錯 16 天。
2. **公司名稱含逗號**（`"...Co., Ltd."`），必須用 `csv` 模組解析，
   不可 `split(",")`（實測用 split 會把 `Ltd.` 讀成級距值）。
"""

# 段落標記；以「開頭是否為此字串」比對，避免全形空白等細節差異
FUTURES_SECTION_MARKER: str = "一、股票期貨契約保證金一覽表"
OPTIONS_SECTION_MARKER: str = "二、股票選擇權契約保證金一覽表"
STOCK_UNDERLYING_MARKER: str = "(一) 標的證券為股票"
ETF_UNDERLYING_MARKER: str = "(二) 標的證券為受益憑證"

# 一(一) 的表頭：比例型
RATE_HEADER: List[str] = [
    "序號",
    "股票期貨英文代碼",
    "股票期貨標的證券代號",
    "股票期貨中文簡稱",
    "股票期貨標的證券",
    "保證金所屬級距",
    "結算保證金適用比例",
    "維持保證金適用比例",
    "原始保證金適用比例",
]

# 一(二) 的表頭：金額型
AMOUNT_HEADER: List[str] = [
    "序號",
    "股票期貨英文代碼",
    "股票期貨標的證券代號",
    "股票期貨中文簡稱",
    "股票期貨標的證券",
    "結算保證金",
    "維持保證金",
    "原始保證金",
]


class MarginSection(NamedTuple):
    """一個段落的解析結果：生效日 ＋ 資料列"""

    effective_date: datetime.date
    rows: List[List[str]]


class StockFuturesMarginCleaner(BaseDataCleaner):
    """Stock Futures Margin Cleaner"""

    def __init__(self):
        super().__init__()

        # Downloads directory Path
        self.margin_dir: Path = FUTURES_MARGIN_DOWNLOADS_PATH

        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Cleaner"""

        # 主鍵為 (effective_date, product_id)
        self.rate_cleaned_cols: List[str] = [
            "effective_date",
            "product_id",
            "underlying_stock_id",
            "product_name",
            "保證金所屬級距",
            "結算保證金適用比例",
            "維持保證金適用比例",
            "原始保證金適用比例",
            "source",
        ]
        # 金額型與 `futures_margin_history` 的欄位一致，共用同一個 loader
        self.amount_cleaned_cols: List[str] = [
            "effective_date",
            "product",
            "product_name",
            "結算保證金",
            "維持保證金",
            "原始保證金",
            "source",
        ]

        self.margin_dir.mkdir(parents=True, exist_ok=True)

    def clean_stock_margin(
        self, text: str
    ) -> Optional[Dict[str, Optional[pd.DataFrame]]]:
        """
        - Description:
            清洗股票期貨保證金一覽表，回傳比例與金額兩個 DataFrame

            **選擇權段落一律不解析**，在切段時就被丟掉。
        - Parameters:
            - text: str
                crawler 取得的 CSV 原文（已 big5 解碼）
        - Return:
            - Optional[Dict[str, Optional[pd.DataFrame]]]
                `{"rate": ..., "amount": ...}`；整份無法解析時為 None。
                個別段落解析不出時該項為 None，另一項仍會回傳——兩段的
                更新日期不同、來源獨立，一段壞掉不該讓另一段也不入庫。
        """

        if not text or not text.strip():
            logger.warning("[Stock Futures Margin] CSV 為空")
            return None

        rows: List[List[str]] = [
            [cell.strip() for cell in row] for row in csv.reader(StringIO(text))
        ]

        futures_rows: List[List[str]] = self.take_futures_section(rows)
        if not futures_rows:
            logger.warning("[Stock Futures Margin] 找不到股票期貨段落，可能為站方改版")
            return None

        rate_section: Optional[MarginSection] = self.take_subsection(
            futures_rows, STOCK_UNDERLYING_MARKER, RATE_HEADER
        )
        amount_section: Optional[MarginSection] = self.take_subsection(
            futures_rows, ETF_UNDERLYING_MARKER, AMOUNT_HEADER
        )

        return {
            "rate": self.build_rate_df(rate_section),
            "amount": self.build_amount_df(amount_section),
        }

    @staticmethod
    def take_futures_section(rows: List[List[str]]) -> List[List[str]]:
        """
        取出「一、股票期貨」段落，丟掉「二、股票選擇權」之後的全部內容

        選擇權的代碼（`DFO`／`CAO`／`NYA`…）與股期高度相似，不先切掉的話
        很容易混進來——它們的保證金語意是風險保證金參數，不是每口保證金。
        """

        start: Optional[int] = None
        end: int = len(rows)

        for i, row in enumerate(rows):
            if not row or not row[0]:
                continue
            if row[0].startswith(FUTURES_SECTION_MARKER):
                start = i
            elif row[0].startswith(OPTIONS_SECTION_MARKER):
                end = i
                break

        return [] if start is None else rows[start:end]

    @staticmethod
    def take_subsection(
        rows: List[List[str]], marker: str, header: List[str]
    ) -> Optional[MarginSection]:
        """
        - Description:
            自段落內取出指定子節的生效日與資料列

            **生效日逐節各自解析**：四個子節的更新日期不同，用全檔第一個日期
            套用到全部會讓 ETF 股期的生效日錯 16 天（2026-09-01 實查）。
        - Parameters:
            - rows: List[List[str]]
                段落內的所有列
            - marker: str
                子節標題的起始字串
            - header: List[str]
                該子節的表頭；對不上代表站方改版
        - Return:
            - Optional[MarginSection]
                生效日與資料列；找不到子節或表頭不符時為 None
        """

        start: Optional[int] = None
        for i, row in enumerate(rows):
            if row and row[0].startswith(marker):
                start = i
                break
        if start is None:
            return None

        effective_date: Optional[datetime.date] = None
        header_index: Optional[int] = None

        for i in range(start + 1, len(rows)):
            row = rows[i]
            if not row or not any(row):
                continue
            # 下一個子節開始，代表本子節沒有表頭
            if row[0].startswith("(") and i != start:
                break
            if effective_date is None:
                found: Optional[re.Match] = re.search(EFFECTIVE_DATE_PATTERN, row[0])
                if found:
                    year, month, day = (int(g) for g in found.groups())
                    effective_date = datetime.date(year, month, day)
                    continue
            if row[: len(header)] == header:
                header_index = i
                break

        if effective_date is None or header_index is None:
            return None

        data_rows: List[List[str]] = []
        for row in rows[header_index + 1 :]:
            if not row or not any(row):
                continue
            # 遇到下一個子節標題就停
            if row[0].startswith("("):
                break
            if not row[0].isdigit():
                continue
            data_rows.append(row)

        return MarginSection(effective_date=effective_date, rows=data_rows)

    def build_rate_df(self, section: Optional[MarginSection]) -> Optional[pd.DataFrame]:
        """把一(一) 的比例列組成 DataFrame；比例一律轉成**小數**"""

        if section is None or not section.rows:
            logger.warning("[Stock Futures Margin] 比例段落解析不出資料")
            return None

        records: List[Dict[str, object]] = []
        for row in section.rows:
            if len(row) < len(RATE_HEADER):
                continue
            rates: Optional[List[float]] = self.parse_rates(row[6:9])
            if rates is None:
                continue
            records.append(
                {
                    "effective_date": section.effective_date,
                    "product_id": row[1],
                    "underlying_stock_id": row[2],
                    "product_name": row[3],
                    # 空級距存 None：處置股票沒有級距但仍有（更高的）比例，
                    # 見本檔說明第 3 點。**pandas 會把它正規化成 NaN**，
                    # 入庫時由 sqlite3 轉成真正的 NULL（已驗證）
                    "保證金所屬級距": row[5] or None,
                    "結算保證金適用比例": rates[0],
                    "維持保證金適用比例": rates[1],
                    "原始保證金適用比例": rates[2],
                    "source": "snapshot",
                }
            )

        if not records:
            return None

        df: pd.DataFrame = pd.DataFrame(records)[self.rate_cleaned_cols]
        self.save_csv(df, f"stock_futures_margin_rate_{section.effective_date:%Y%m%d}")
        return df

    def build_amount_df(
        self, section: Optional[MarginSection]
    ) -> Optional[pd.DataFrame]:
        """把一(二) 的金額列組成 DataFrame，欄位與 `futures_margin_history` 相同"""

        if section is None or not section.rows:
            logger.warning("[Stock Futures Margin] 金額段落解析不出資料")
            return None

        records: List[Dict[str, object]] = []
        for row in section.rows:
            if len(row) < len(AMOUNT_HEADER):
                continue
            amounts: Optional[List[int]] = self.parse_amounts(row[5:8])
            if amounts is None:
                continue
            records.append(
                {
                    "effective_date": section.effective_date,
                    "product": row[1],
                    "product_name": row[3],
                    "結算保證金": amounts[0],
                    "維持保證金": amounts[1],
                    "原始保證金": amounts[2],
                    "source": "snapshot",
                }
            )

        if not records:
            return None

        df: pd.DataFrame = pd.DataFrame(records)[self.amount_cleaned_cols]
        self.save_csv(df, f"etf_futures_margin_{section.effective_date:%Y%m%d}")
        return df

    @staticmethod
    def parse_rates(cells: List[str]) -> Optional[List[float]]:
        """
        `13.50%` → `0.1350`

        **存小數而非百分比數值**：下游直接乘不必再除以 100，
        而「忘記除 100」會讓保證金差 100 倍卻不會報錯。
        """

        rates: List[float] = []
        for cell in cells:
            value: str = cell.replace("%", "").replace(",", "").strip()
            try:
                rates.append(round(float(value) / 100, 6))
            except ValueError:
                return None
        return rates

    @staticmethod
    def parse_amounts(cells: List[str]) -> Optional[List[int]]:
        """三個金額欄轉整數；任一欄不是純數字就回傳 None"""

        amounts: List[int] = []
        for cell in cells:
            digits: str = cell.replace(",", "").strip()
            if not digits.isdigit():
                return None
            amounts.append(int(digits))
        return amounts

    def save_csv(self, df: pd.DataFrame, stem: str) -> None:
        """中繼檔落地，供人工核對"""

        df.to_csv(
            self.margin_dir / f"{stem}.csv",
            index=False,
            encoding=FileEncoding.UTF8_SIG.value,
        )
