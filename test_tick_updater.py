"""
測試 StockTickUpdater 的 update 函數
只測試爬取和清洗，不存入資料庫
"""

import datetime
import sys
from pathlib import Path
from unittest.mock import MagicMock

from loguru import logger

# 在導入 StockTickUpdater 之前，先 mock dolphindb 模組（如果沒有安裝）
try:
    import dolphindb as ddb

    DOLPHINDB_AVAILABLE = True
except (ModuleNotFoundError, ImportError):
    # 創建一個 mock dolphindb 模組
    mock_ddb = MagicMock()
    mock_session = MagicMock()
    # Mock 所有可能被調用的方法
    mock_session.existsDatabase = MagicMock(return_value=False)
    mock_session.run = MagicMock()  # 用於執行 DolphinDB 腳本
    mock_session.close = MagicMock()  # 用於關閉連接
    mock_session.connect = MagicMock()  # 用於連接資料庫（不會真正連接）
    mock_ddb.session = MagicMock(return_value=mock_session)
    # 將 mock 模組注入到 sys.modules
    sys.modules["dolphindb"] = mock_ddb
    DOLPHINDB_AVAILABLE = False
    print("⚠️  dolphindb 模組未安裝，使用 mock 模組（測試模式）")

from trader.config import TICK_DOWNLOADS_PATH
from trader.pipeline.updaters.stock_tick_updater import StockTickUpdater


def test_update_without_db(start_date: datetime.date, end_date: datetime.date = None):
    """
    測試 StockTickUpdater 的 update 函數，但不存入資料庫

    Args:
        start_date: 開始日期，例如 datetime.date(2024, 1, 15)
        end_date: 結束日期，預設為今天，例如 datetime.date(2024, 1, 17)
    """
    if end_date is None:
        end_date = datetime.date.today()

    print(f"\n{'='*60}")
    print(f"測試 StockTickUpdater.update() - 不存入資料庫")
    print(f"{'='*60}")
    print(f"開始日期: {start_date}")
    print(f"結束日期: {end_date}")
    print(f"資料保存路徑: {TICK_DOWNLOADS_PATH}")

    # 初始化 updater
    print("\n初始化 StockTickUpdater...")
    updater = StockTickUpdater()

    # 將 loader.add_to_db 替換為空函數，避免存入資料庫
    def dummy_add_to_db(remove_file=False):
        """空的函數，不執行任何操作"""
        logger.info("⚠️  跳過資料庫寫入（測試模式）")
        return None

    # 替換 loader 的 add_to_db 方法
    original_add_to_db = updater.loader.add_to_db
    updater.loader.add_to_db = dummy_add_to_db

    print("✅ StockTickUpdater 初始化完成")
    print("✅ 已設定為測試模式（不會存入資料庫）")

    # 檢查資料夾中現有的 CSV 檔案數量
    existing_files = list(TICK_DOWNLOADS_PATH.glob("*.csv"))
    print(f"\n📁 開始測試前，資料夾中現有 CSV 檔案數量: {len(existing_files)}")

    try:
        # 執行 update（會爬取和清洗，但不會存入資料庫）
        print(f"\n開始執行 update()...")
        print(f"這會執行：")
        print(f"  1. 爬取資料 (crawler.crawl_stock_tick)")
        print(f"  2. 清洗資料 (cleaner.clean_stock_tick)")
        print(f"  3. 保存 CSV 檔案到 {TICK_DOWNLOADS_PATH}")
        print(f"  4. ⚠️  跳過存入資料庫 (loader.add_to_db)")

        updater.update(start_date=start_date, end_date=end_date)

        print(f"\n✅ update() 執行完成！")

        # 檢查資料夾中新增的 CSV 檔案
        new_files = list(TICK_DOWNLOADS_PATH.glob("*.csv"))
        print(f"\n📁 測試完成後，資料夾中 CSV 檔案數量: {len(new_files)}")
        print(f"📁 新增的 CSV 檔案數量: {len(new_files) - len(existing_files)}")

        if len(new_files) > len(existing_files):
            print(f"\n✅ 成功生成 CSV 檔案！")
            print(f"檔案列表（前 10 個）:")
            for i, csv_file in enumerate(new_files[:10], 1):
                file_size = csv_file.stat().st_size
                print(f"  {i}. {csv_file.name} ({file_size:,} bytes)")
            if len(new_files) > 10:
                print(f"  ... 還有 {len(new_files) - 10} 個檔案")
        else:
            print(f"⚠️  沒有新增 CSV 檔案（可能是日期範圍內沒有資料）")

        # 顯示資料保存位置
        print(f"\n{'='*60}")
        print(f"📁 資料保存位置: {TICK_DOWNLOADS_PATH}")
        print(f"   所有爬取並清洗後的 CSV 檔案都保存在此目錄")
        print(f"   檔案名稱格式: {{stock_id}}.csv (例如: 2330.csv)")
        print(f"{'='*60}")

    except Exception as e:
        print(f"\n❌ 執行 update() 時發生錯誤: {e}")
        import traceback

        traceback.print_exc()
    finally:
        # 恢復原始的 add_to_db 方法（雖然可能不會再用到）
        updater.loader.add_to_db = original_add_to_db


if __name__ == "__main__":
    # 設定 logger（可選，如果需要看到詳細日誌）
    logger.remove()  # 移除預設的 logger
    logger.add(
        lambda msg: print(msg, end=""),
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        level="INFO",
    )

    # ===== 測試範例 =====

    # 設定測試日期範圍
    # 請根據您的需求修改這些日期
    test_start_date = datetime.date(2024, 5, 11)  # 開始日期
    test_end_date = datetime.date(2024, 5, 15)  # 結束日期（可選，預設為今天）

    print("\n" + "=" * 60)
    print("測試 StockTickUpdater.update() - 不存入資料庫")
    print("=" * 60)
    print(f"\n⚠️  注意：此測試會爬取所有上市櫃股票的資料")
    print(f"   如果日期範圍很大，可能會花費較長時間")
    print(f"   建議先用小範圍的日期測試（例如 1-2 天）")
    print(f"\n測試參數：")
    print(f"  開始日期: {test_start_date}")
    print(f"  結束日期: {test_end_date}")

    # 執行測試
    test_update_without_db(start_date=test_start_date, end_date=test_end_date)

    print("\n" + "=" * 60)
    print("測試完成！")
    print("=" * 60)
