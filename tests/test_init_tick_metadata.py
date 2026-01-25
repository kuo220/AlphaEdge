"""
測試初始化 tick_metadata.json
1. 使用 StockInfoCrawler.crawl_stock_list() 爬取所有上市櫃公司代號
2. 創建預設的 tick_metadata.json，每個公司的預設 "last_date" 都是 "2024-5-10"
3. 掃描 trader/pipeline/downloads/tick 資料夾底下的所有 CSV 檔案
4. 根據每個檔案的最後一筆資料的時間，更新到 tick_metadata.json
"""

import datetime
import json
from pathlib import Path
from typing import Dict, Any

import pandas as pd
from loguru import logger

from trader.config import TICK_DOWNLOADS_PATH, TICK_METADATA_PATH
from trader.pipeline.crawlers.stock_info_crawler import StockInfoCrawler
from trader.pipeline.utils.stock_tick_utils import StockTickUtils


def init_tick_metadata_with_default_date(default_date: str = "2024-5-10") -> None:
    """
    初始化 tick_metadata.json，使用預設日期

    Args:
        default_date: 預設日期字串，格式為 "YYYY-M-D" 或 "YYYY-MM-DD"
    """
    print(f"\n{'='*60}")
    print(f"初始化 tick_metadata.json")
    print(f"{'='*60}")

    # 確保 metadata 目錄存在
    TICK_METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)

    # 1. 爬取所有上市櫃公司代號
    print(f"\n步驟 1: 爬取所有上市櫃公司代號...")
    try:
        stock_list: list[str] = StockInfoCrawler.crawl_stock_list()
        print(f"✅ 成功爬取 {len(stock_list)} 檔股票")
    except Exception as e:
        logger.error(f"❌ 爬取股票列表失敗: {e}")
        raise

    # 2. 解析預設日期
    try:
        # 將 "2024-5-10" 轉換為標準格式 "2024-05-10"
        default_date_obj = datetime.datetime.strptime(default_date, "%Y-%m-%d").date()
        default_date_str = default_date_obj.isoformat()  # "YYYY-MM-DD"
        print(f"\n步驟 2: 設定預設日期為 {default_date_str}")
    except ValueError as e:
        logger.error(
            f"❌ 日期格式錯誤: {default_date}，請使用 YYYY-M-D 或 YYYY-MM-DD 格式"
        )
        raise

    # 3. 創建預設的 metadata 結構
    print(f"\n步驟 3: 創建預設的 metadata 結構...")
    metadata: Dict[str, Any] = {"stocks": {}}

    # 為每個股票設定預設日期
    for stock_id in stock_list:
        metadata["stocks"][stock_id] = {"last_date": default_date_str}

    print(f"✅ 已為 {len(stock_list)} 檔股票設定預設日期 {default_date_str}")

    # 4. 掃描 CSV 檔案並更新對應股票的 last_date
    print(f"\n步驟 4: 掃描 CSV 檔案並更新 last_date...")

    # 確保 tick 下載資料夾存在
    if not TICK_DOWNLOADS_PATH.exists():
        logger.warning(f"⚠️  Tick 下載資料夾不存在: {TICK_DOWNLOADS_PATH}")
        logger.info("將使用預設日期建立 metadata")
    else:
        # 掃描所有 CSV 檔案
        csv_files: list[Path] = list(TICK_DOWNLOADS_PATH.glob("*.csv"))
        print(f"找到 {len(csv_files)} 個 CSV 檔案")

        updated_count = 0
        for csv_file in csv_files:
            stock_id: str = csv_file.stem  # 取得檔名（不含副檔名）作為股票代號

            # 如果該股票不在 stock_list 中，跳過（可能是權證或其他）
            if stock_id not in metadata["stocks"]:
                logger.debug(f"跳過不在股票列表中的檔案: {csv_file.name}")
                continue

            try:
                # 讀取 CSV 檔案（只讀取 time 欄位以提升效能）
                df: pd.DataFrame = pd.read_csv(csv_file, usecols=["time"])

                if df.empty:
                    logger.warning(f"檔案 {csv_file.name} 為空，跳過")
                    continue

                # 取得最後一筆資料的時間
                last_time_str: str = df["time"].iloc[-1]

                # 解析時間字串（格式：YYYY-MM-DD HH:MM:SS.ffffff）
                try:
                    last_time: pd.Timestamp = pd.to_datetime(last_time_str)
                    last_date: datetime.date = last_time.date()
                    last_date_str: str = last_date.isoformat()

                    # 更新 metadata
                    metadata["stocks"][stock_id]["last_date"] = last_date_str
                    updated_count += 1

                    logger.debug(
                        f"股票 {stock_id}: 從 CSV 更新 last_date = {last_date_str}"
                    )
                except Exception as e:
                    logger.warning(
                        f"無法解析檔案 {csv_file.name} 的時間 '{last_time_str}': {e}"
                    )
                    continue

            except Exception as e:
                logger.error(f"讀取檔案 {csv_file.name} 時發生錯誤: {e}")
                continue

        print(f"✅ 成功更新 {updated_count} 檔股票的 last_date（從 CSV 檔案）")

    # 5. 寫入 metadata 檔案
    print(f"\n步驟 5: 寫入 tick_metadata.json...")
    try:
        with open(TICK_METADATA_PATH, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=4)
        print(f"✅ 成功寫入 {TICK_METADATA_PATH}")
    except Exception as e:
        logger.error(f"❌ 寫入檔案失敗: {e}")
        raise

    # 6. 統計資訊
    print(f"\n{'='*60}")
    print(f"初始化完成！")
    print(f"{'='*60}")
    print(f"總股票數: {len(metadata['stocks'])}")
    print(
        f"使用預設日期 ({default_date_str}) 的股票數: {len(metadata['stocks']) - updated_count}"
    )
    print(f"從 CSV 更新日期的股票數: {updated_count}")
    print(f"Metadata 檔案位置: {TICK_METADATA_PATH}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    # 設定 logger
    logger.remove()  # 移除預設的 logger
    logger.add(lambda msg: print(msg, end=""), format="{message}", level="INFO")

    # 執行初始化
    default_date = "2024-5-10"  # 預設日期
    init_tick_metadata_with_default_date(default_date=default_date)
