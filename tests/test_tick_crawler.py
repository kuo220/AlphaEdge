"""
測試 StockTickCrawler 的爬取功能
只測試爬取和清洗，不存入資料庫
"""

import datetime
from pathlib import Path
from typing import List, Optional

import pandas as pd
import shioaji as sj
from loguru import logger

from trader.config import TICK_DOWNLOADS_PATH
from trader.pipeline.cleaners.stock_tick_cleaner import StockTickCleaner
from trader.pipeline.crawlers.stock_tick_crawler import StockTickCrawler
from trader.utils import ShioajiAccount, ShioajiAPI, TimeUtils
from trader.config import API_KEY, API_SECRET_KEY


def test_crawler_only(stock_id: str, date: datetime.date):
    """
    只測試爬取功能，不保存檔案

    Args:
        stock_id: 股票代號，例如 "2330"
        date: 日期，例如 datetime.date(2024, 1, 15)
    """
    print(f"\n{'='*60}")
    print(f"測試爬取功能（不保存檔案）")
    print(f"{'='*60}")
    print(f"股票代號: {stock_id}")
    print(f"日期: {date}")

    # 初始化 crawler
    crawler: StockTickCrawler = StockTickCrawler()

    # 登入 Shioaji API
    api: sj.Shioaji = sj.Shioaji()
    api_instance: Optional[sj.Shioaji] = ShioajiAccount.API_login(
        api, API_KEY, API_SECRET_KEY
    )

    if api_instance is None:
        print("❌ API 登入失敗")
        return None

    print("✅ API 登入成功")

    # 爬取資料
    print(f"\n開始爬取 {stock_id} 在 {date} 的 tick 資料...")
    df: Optional[pd.DataFrame] = crawler.crawl_stock_tick(api_instance, date, stock_id)

    if df is None or df.empty:
        print(f"❌ 沒有爬取到資料")
        ShioajiAccount.API_logout(api_instance)
        return None

    print(f"✅ 爬取成功！")
    print(f"資料筆數: {len(df)}")
    print(f"資料欄位: {list(df.columns)}")
    print(f"\n前 5 筆資料:")
    print(df.head())

    # 登出 API
    ShioajiAccount.API_logout(api_instance)

    return df


def test_crawler_and_cleaner(stock_id: str, date: datetime.date):
    """
    測試爬取和清洗功能，會保存 CSV 檔案到 TICK_DOWNLOADS_PATH

    Args:
        stock_id: 股票代號，例如 "2330"
        date: 日期，例如 datetime.date(2024, 1, 15)
    """
    print(f"\n{'='*60}")
    print(f"測試爬取和清洗功能（會保存 CSV 檔案）")
    print(f"{'='*60}")
    print(f"股票代號: {stock_id}")
    print(f"日期: {date}")
    print(f"資料保存路徑: {TICK_DOWNLOADS_PATH}")

    # 初始化 crawler 和 cleaner
    crawler: StockTickCrawler = StockTickCrawler()
    cleaner: StockTickCleaner = StockTickCleaner()

    # 登入 Shioaji API
    api: sj.Shioaji = sj.Shioaji()
    api_instance: Optional[sj.Shioaji] = ShioajiAccount.API_login(
        api, API_KEY, API_SECRET_KEY
    )

    if api_instance is None:
        print("❌ API 登入失敗")
        return None

    print("✅ API 登入成功")

    # 爬取資料
    print(f"\n開始爬取 {stock_id} 在 {date} 的 tick 資料...")
    df: Optional[pd.DataFrame] = crawler.crawl_stock_tick(api_instance, date, stock_id)

    if df is None or df.empty:
        print(f"❌ 沒有爬取到資料")
        ShioajiAccount.API_logout(api_instance)
        return None

    print(f"✅ 爬取成功！資料筆數: {len(df)}")

    # 清洗資料（會自動保存 CSV）
    print(f"\n開始清洗資料...")
    cleaned_df: Optional[pd.DataFrame] = cleaner.clean_stock_tick(df, stock_id)

    if cleaned_df is None or cleaned_df.empty:
        print(f"❌ 清洗後的資料為空")
        ShioajiAccount.API_logout(api_instance)
        return None

    print(f"✅ 清洗成功！")
    print(f"清洗後資料筆數: {len(cleaned_df)}")
    print(f"清洗後資料欄位: {list(cleaned_df.columns)}")
    print(f"\n前 5 筆清洗後的資料:")
    print(cleaned_df.head())

    # 檢查檔案是否已保存
    csv_file = TICK_DOWNLOADS_PATH / f"{stock_id}.csv"
    if csv_file.exists():
        file_size = csv_file.stat().st_size
        print(f"\n✅ CSV 檔案已保存: {csv_file}")
        print(f"檔案大小: {file_size:,} bytes ({file_size/1024:.2f} KB)")
    else:
        print(f"\n⚠️  警告: CSV 檔案未找到於 {csv_file}")

    # 登出 API
    ShioajiAccount.API_logout(api_instance)

    return cleaned_df


def test_multiple_dates(stock_id: str, dates: list[datetime.date]):
    """
    測試爬取多個日期的資料並合併

    Args:
        stock_id: 股票代號，例如 "2330"
        dates: 日期列表，例如 [datetime.date(2024, 1, 15), datetime.date(2024, 1, 16)]
    """
    print(f"\n{'='*60}")
    print(f"測試爬取多個日期的資料")
    print(f"{'='*60}")
    print(f"股票代號: {stock_id}")
    print(f"日期範圍: {dates[0]} ~ {dates[-1]} (共 {len(dates)} 天)")
    print(f"資料保存路徑: {TICK_DOWNLOADS_PATH}")

    # 初始化 crawler 和 cleaner
    crawler: StockTickCrawler = StockTickCrawler()
    cleaner: StockTickCleaner = StockTickCleaner()

    # 登入 Shioaji API
    api: sj.Shioaji = sj.Shioaji()
    api_instance: Optional[sj.Shioaji] = ShioajiAccount.API_login(
        api, API_KEY, API_SECRET_KEY
    )

    if api_instance is None:
        print("❌ API 登入失敗")
        return None

    print("✅ API 登入成功")

    # 爬取多個日期的資料
    df_list: List[pd.DataFrame] = []
    for date in dates:
        print(f"\n爬取 {date} 的資料...")
        df: Optional[pd.DataFrame] = crawler.crawl_stock_tick(
            api_instance, date, stock_id
        )

        if df is not None and not df.empty:
            df_list.append(df)
            print(f"  ✅ 成功，取得 {len(df)} 筆資料")
        else:
            print(f"  ⚠️  沒有資料")

    if not df_list:
        print(f"\n❌ 所有日期都沒有爬取到資料")
        ShioajiAccount.API_logout(api_instance)
        return None

    # 合併所有日期的資料
    merged_df: pd.DataFrame = pd.concat(df_list, ignore_index=True)
    print(f"\n✅ 合併完成！總共 {len(merged_df)} 筆資料")

    # 清洗資料（會自動保存 CSV）
    print(f"\n開始清洗資料...")
    cleaned_df: Optional[pd.DataFrame] = cleaner.clean_stock_tick(merged_df, stock_id)

    if cleaned_df is None or cleaned_df.empty:
        print(f"❌ 清洗後的資料為空")
        ShioajiAccount.API_logout(api_instance)
        return None

    print(f"✅ 清洗成功！")
    print(f"清洗後資料筆數: {len(cleaned_df)}")

    # 檢查檔案是否已保存
    csv_file = TICK_DOWNLOADS_PATH / f"{stock_id}.csv"
    if csv_file.exists():
        file_size = csv_file.stat().st_size
        print(f"\n✅ CSV 檔案已保存: {csv_file}")
        print(f"檔案大小: {file_size:,} bytes ({file_size/1024:.2f} KB)")
    else:
        print(f"\n⚠️  警告: CSV 檔案未找到於 {csv_file}")

    # 登出 API
    ShioajiAccount.API_logout(api_instance)

    return cleaned_df


if __name__ == "__main__":
    # 設定 logger
    logger.remove()  # 移除預設的 logger
    logger.add(lambda msg: print(msg, end=""), format="{message}")

    # ===== 測試範例 =====

    # 範例 1: 只測試爬取功能（不保存檔案）
    print("\n" + "=" * 60)
    print("範例 1: 只測試爬取功能")
    print("=" * 60)
    test_date = datetime.date(2024, 1, 15)  # 請修改為您想測試的日期
    test_stock = "2330"  # 台積電，請修改為您想測試的股票代號
    df1 = test_crawler_only(test_stock, test_date)

    # 範例 2: 測試爬取和清洗功能（會保存 CSV）
    print("\n" + "=" * 60)
    print("範例 2: 測試爬取和清洗功能（會保存 CSV）")
    print("=" * 60)
    df2 = test_crawler_and_cleaner(test_stock, test_date)

    # 範例 3: 測試多個日期
    print("\n" + "=" * 60)
    print("範例 3: 測試多個日期")
    print("=" * 60)
    dates = TimeUtils.generate_date_range(
        datetime.date(2024, 1, 15), datetime.date(2024, 1, 17)
    )
    df3 = test_multiple_dates(test_stock, dates)

    print("\n" + "=" * 60)
    print("測試完成！")
    print("=" * 60)
    print(f"\n📁 資料保存位置: {TICK_DOWNLOADS_PATH}")
    print(f"   如果執行了範例 2 或 3，CSV 檔案會保存在此目錄下")
    print(f"   檔案名稱格式: {{stock_id}}.csv (例如: 2330.csv)")
