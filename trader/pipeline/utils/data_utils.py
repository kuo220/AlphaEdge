import datetime
import json
import pandas as pd
from loguru import logger
from pathlib import Path
from typing import List, Optional, Any

from trader.pipeline.utils import FileEncoding


class DataUtils:
    """ Data Tools """

    @staticmethod
    def move_col(df: pd.DataFrame, col_name: str, ref_col_name: str) -> None:
        """ 移動 columns 位置：將 col_name 整個 column 移到 ref_col_name 後方 """

        col_data: pd.Series = df.pop(col_name)
        df.insert(df.columns.get_loc(ref_col_name) + 1, col_name, col_data)


    @staticmethod
    def remove_redundant_col(df: pd.DataFrame, col_name: str) -> pd.DataFrame:
        """ 刪除 DataFrame 中指定欄位後面的所有欄位 """

        if col_name in df.columns:
            last_col_loc: int = df.columns.get_loc(col_name)
            df = df.iloc[:, :last_col_loc + 1]
        return df


    @staticmethod
    def convert_col_to_numeric(df: pd.DataFrame, exclude_cols: List[str]) -> pd.DataFrame:
        """ 將 exclude_cols 以外的 columns 資料都轉為數字型態（int or float） """

        for col in df.columns:
            if col not in exclude_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        return df


    @staticmethod
    def pad2(n: int | str) -> str:
        """ 將數字補足為兩位數字字串 """
        return str(n).zfill(2)


    @staticmethod
    def fill_nan(df: pd.DataFrame, value: int=0) -> pd.DataFrame:
        """ 檢查 DataFrame 是否有 NaN 值，若有則將所有 NaN 值填補為指定值 """

        if df.isnull().values.any():
            df.fillna(value, inplace=True)
        return df


    @staticmethod
    def replace_column_name(
        col_name: str,
        keywords: List[str],
        replacement: str
    ) -> str:
        """
        - Description:
            將欄位名稱中出現的指定關鍵字（如「合計」、「總計」）替換為指定詞（如「總額」）
            e.g. 資產總計 -> 資產總額
        - Parameters:
            - col_name: str
                欄位名稱
            - keywords: List[str]
                欲替換的關鍵字列表，例如: 合計"、"總計"
            - replacement: str
                要統一替換成的文字，例如: 總額
        - Return: str
            - 處理後的欄位名稱
        """

        for keyword in keywords:
            if keyword in col_name:
                return col_name.replace(keyword, replacement)
        return col_name


    @staticmethod
    def remove_cols_by_keywords(
        df: pd.DataFrame,
        startswith: Optional[List[str]]=None,
        contains: Optional[List[str]]=None,
        case_insensitive: bool = True
    ) -> pd.DataFrame:
        """
        - Description:
            移除以指定字串開頭或包含指定字串的欄位名稱
        Parameters:
            - df: 原始 DataFrame
            - startswith: 欲刪除欄位的開頭關鍵字，例如 ["Unnamed"]
            - contains: 欲刪除欄位的包含關鍵字，例如 ["錯誤"]
            - case_insensitive: 是否忽略大小寫（預設 True）
        Returns:
            - 已刪除指定欄位的 DataFrame
        """

        # 確保 startswith / contains 一定是 list 型別，避免為 None 時無法迭代
        startswith: List[str] = startswith or []
        contains: List[str] = contains or []

        # 將欄位轉成 str 型別，並保留原始 index
        columns: pd.Index = df.columns.astype(str)

        # 初始化刪除遮罩（與欄位 index 對齊）
        columns_to_drop: pd.Series = pd.Series(False, index=columns)

        if case_insensitive:
            columns = columns.str.lower()
            startswith = [word.lower() for word in startswith]
            contains = [word.lower() for word in contains]

        for keyword in startswith:
            columns_to_drop |= columns.str.startswith(keyword)

        for keyword in contains:
            columns_to_drop |= columns.str.contains(keyword)

        return df.loc[:, ~columns_to_drop]


    @staticmethod
    def remove_items_by_keywords(
        items: List[str],
        startswith: Optional[List[str]] = None,
        contains: Optional[List[str]] = None,
        case_insensitive: bool = True
    ) -> List[str]:
        """
        - Description:
            移除符合指定關鍵字的欄位名稱（以開頭或包含），並回傳保留的欄位清單

        Parameters:
            - columns: 欲移除的欄位名稱清單
            - startswith: 欲排除的開頭字串，例如 ["Unnamed"]
            - contains: 欲排除的部分字串，例如 ["錯誤"]
            - case_insensitive: 是否忽略大小寫（預設 True）

        Returns:
            - 過濾後保留的欄位名稱 List[str]
        """

        startswith = startswith or []
        contains = contains or []

        def normalize(s: str) -> str:
            return s.lower() if case_insensitive else s

        norm_starts = [normalize(s) for s in startswith]
        norm_contains = [normalize(s) for s in contains]

        new_items: List[str] = []

        for item in items:
            norm_item = normalize(item)
            if any(norm_item.startswith(s) for s in norm_starts):
                continue
            if any(c in norm_item for c in norm_contains):
                continue
            new_items.append(norm_item)

        return new_items


    @staticmethod
    def save_json(
        data: Any,
        file_path: Path,
        encoding: str=FileEncoding.UTF8.value,
        ensure_ascii: bool=False,
        indent: int=2
    ) -> None:
        """
        - Description:
            將資料儲存成 JSON 檔案

        - Parameters:
            - data: Any
                要儲存的 Python 資料結構（如 dict 或 list）
            - file_path: Path
                儲存檔案的完整路徑
            - encoding: str
                檔案編碼（預設為 utf-8）
            - ensure_ascii: bool
                是否轉成 ASCII 編碼（預設 False，可保留中文）
            - indent: int
                JSON 排版的縮排層級（預設為 2）
        """

        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding=encoding) as f:
            json.dump(data, f, ensure_ascii=ensure_ascii, indent=indent)


    @staticmethod
    def load_json(
        file_path: Path,
        encoding: str=FileEncoding.UTF8.value
    ) -> Any:
        """
        - Description:
            從指定 JSON 檔案讀取資料。

        - Parameters:
            - file_path: Path
                JSON 檔案的完整路徑
            - encoding: str
                檔案編碼（預設為 utf-8）

        - Returns: Any
            從 JSON 載入的 Python 資料（通常為 dict 或 list）
        """

        try:
            with open(file_path, "r", encoding=encoding) as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"找不到檔案: {file_path}")
            return None
        except json.JSONDecodeError:
            logger.error(f"JSON 格式錯誤: {file_path}")
            return None