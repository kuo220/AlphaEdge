import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

from loguru import logger

from core.pipeline.utils.exceptions import DataLoadError

"""Abstract base class for all data loaders that write processed data to a storage system"""


class BaseDataLoader(ABC):
    """Base Class of Data Loader"""

    def __init__(self):
        pass

    @abstractmethod
    def setup(self, *args, **kwargs) -> None:
        """Set Up the Config of Loader"""
        pass

    @abstractmethod
    def connect(self) -> None:
        """Connect to the Database"""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect the Database"""
        pass

    @abstractmethod
    def create_db(self, *args, **kwargs) -> None:
        """Create New Database"""
        pass

    @abstractmethod
    def create_missing_tables(self) -> None:
        """Ensure Database Tables Exist"""
        pass

    @abstractmethod
    def add_to_db(self, *args, **kwargs) -> None:
        """Add Data into Database"""
        pass

    @staticmethod
    def finish_load(
        source: str,
        succeeded: int,
        failed_files: List[str],
        remove_files: bool = False,
        downloads_path: Optional[Path] = None,
    ) -> None:
        """
        - Description:
            彙報單次入庫結果，並在有失敗時讓呼叫端無法忽略

            **逐檔 `except` 之後只記 warning、迴圈照跑、最後印成功，是本專案實際
            出過事的樣式**：2026-08-16 的 margin 回補有 2 個檔案入庫失敗，行程仍以
            結束碼 0 回報成功，缺的 1,553 列是事後逐日比對列數才發現的。

            「單檔失敗不中止整批」本身是對的——其餘檔案仍該入庫；錯的是**跑完之後
            不吭聲**。故此處在全部處理完才拋出，兩者兼顧。

            `remove_files` 的刪除動作也收在這裡：**有失敗時一律不刪來源**，
            否則會把還沒成功入庫的資料一起刪掉，連重試的機會都沒有。
        - Parameters:
            - source: str
                資料來源名稱，用於訊息辨識（例如 "margin"）
            - succeeded: int
                成功入庫的檔案數
            - failed_files: List[str]
                入庫失敗的檔案清單
            - remove_files: bool
                是否在成功後刪除來源檔案目錄
            - downloads_path: Optional[Path]
                來源檔案目錄；`remove_files` 為 True 時必填
        - Raise:
            - DataLoadError
                `failed_files` 非空時拋出
        """

        if failed_files:
            logger.error(
                f"[{source}] 入庫未完全成功：成功 {succeeded} 檔、失敗 "
                f"{len(failed_files)} 檔；失敗清單：{failed_files[:20]}"
                + ("…（僅列前 20 筆）" if len(failed_files) > 20 else "")
            )
            if remove_files:
                logger.error(f"[{source}] 因有失敗檔案，已略過刪除來源目錄")
            raise DataLoadError(source, failed_files, succeeded)

        if remove_files and downloads_path is not None:
            shutil.rmtree(downloads_path)

        logger.info(f"[{source}] 入庫完成：成功 {succeeded} 檔、失敗 0 檔")
