import datetime
import sys
from pathlib import Path
from typing import List, Optional
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

from core.config import TICK_DOWNLOADS_PATH, TICK_METADATA_DIR_PATH
from core.pipeline.updaters.stock_tick_updater import StockTickUpdater
from core.pipeline.utils.stock_tick_utils import StockTickUtils

"""測試 StockTickUpdater.update：僅爬取與清洗，不寫入資料庫"""


def test_update_without_db(start_date: datetime.date, end_date: datetime.date = None):
    """測試 StockTickUpdater.update，不存入資料庫"""
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
    updater: StockTickUpdater = StockTickUpdater()

    # 將 loader.add_to_db 替換為空函數，避免存入資料庫
    def dummy_add_to_db(remove_file=False):
        """空函數，不執行任何操作"""
        logger.info("⚠️  跳過資料庫寫入（測試模式）")
        return None

    # 替換 loader 的 add_to_db 方法
    original_add_to_db = updater.loader.add_to_db
    updater.loader.add_to_db = dummy_add_to_db  # type: ignore

    print("✅ StockTickUpdater 初始化完成")
    print("✅ 已設定為測試模式（不會存入資料庫）")

    # 檢查資料夾中現有的 CSV 檔案數量
    existing_files: List[Path] = list(TICK_DOWNLOADS_PATH.glob("*.csv"))
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
        new_files: List[Path] = list(TICK_DOWNLOADS_PATH.glob("*.csv"))
        print(f"\n📁 測試完成後，資料夾中 CSV 檔案數量: {len(new_files)}")
        print(f"📁 新增的 CSV 檔案數量: {len(new_files) - len(existing_files)}")

        if len(new_files) > len(existing_files):
            print(f"\n✅ 成功生成 CSV 檔案！")
            print(f"檔案列表（前 10 個）:")
            for i, csv_file in enumerate(new_files[:10], 1):
                file_size: int = csv_file.stat().st_size
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


def test_scan_tick_downloads_folder():
    """
    測試 StockTickUtils.scan_tick_downloads_folder() 函數
    掃描 tick 下載資料夾並返回每個股票的最後一筆資料日期
    """
    print(f"\n{'='*60}")
    print(f"測試 scan_tick_downloads_folder()")
    print(f"{'='*60}")
    print(f"資料夾路徑: {TICK_DOWNLOADS_PATH}")

    try:
        # 執行掃描
        print("\n開始掃描 tick 下載資料夾...")
        stock_last_dates = StockTickUtils.scan_tick_downloads_folder()

        print(f"\n✅ 掃描完成！")
        print(f"📊 掃描結果統計：")
        print(f"   找到 {len(stock_last_dates)} 個股票的資料檔案")

        if stock_last_dates:
            print(f"\n📋 前 10 個股票的資訊：")
            for i, (stock_id, last_date) in enumerate(
                list(stock_last_dates.items())[:10], 1
            ):
                print(f"   {i}. {stock_id}: 最後一筆資料日期 = {last_date}")
            if len(stock_last_dates) > 10:
                print(f"   ... 還有 {len(stock_last_dates) - 10} 個股票")

            # 顯示日期範圍統計
            dates = list(stock_last_dates.values())
            unique_dates = sorted(set(dates))
            print(f"\n📅 日期範圍統計：")
            print(f"   最早日期: {min(unique_dates)}")
            print(f"   最晚日期: {max(unique_dates)}")
            print(f"   共有 {len(unique_dates)} 個不同的日期")
        else:
            print(f"\n⚠️  沒有找到任何 CSV 檔案")
            print(f"   請確認資料夾路徑是否正確：{TICK_DOWNLOADS_PATH}")
            print(f"   或者先執行 test_update_without_db() 來下載一些資料")

        return stock_last_dates

    except Exception as e:
        print(f"\n❌ 執行 scan_tick_downloads_folder() 時發生錯誤: {e}")
        import traceback

        traceback.print_exc()
        return {}


def test_update_tick_downloads_metadata():
    """
    測試 StockTickUtils.update_tick_downloads_metadata() 函數
    更新 tick_downloads_metadata.json 檔案
    """
    print(f"\n{'='*60}")
    print(f"測試 update_tick_downloads_metadata()")
    print(f"{'='*60}")

    # 定義 metadata 檔案路徑
    downloads_metadata_path = TICK_METADATA_DIR_PATH / "tick_downloads_metadata.json"
    print(f"Metadata 檔案路徑: {downloads_metadata_path}")

    try:
        # 檢查更新前的 metadata（如果存在）
        metadata_before = None
        if downloads_metadata_path.exists():
            with open(downloads_metadata_path, "r", encoding="utf-8") as f:
                import json

                metadata_before = json.load(f)
                stocks_count_before = len(metadata_before.get("stocks", {}))
                print(f"\n📄 更新前的 metadata：")
                print(f"   已有 {stocks_count_before} 個股票的記錄")
        else:
            print(f"\n📄 metadata 檔案不存在，將創建新檔案")

        # 執行更新
        print("\n開始更新 tick_downloads_metadata...")
        StockTickUtils.update_tick_downloads_metadata()

        print(f"\n✅ 更新完成！")

        # 讀取更新後的 metadata
        if downloads_metadata_path.exists():
            with open(downloads_metadata_path, "r", encoding="utf-8") as f:
                import json

                metadata_after = json.load(f)
                stocks_count_after = len(metadata_after.get("stocks", {}))

                print(f"\n📊 更新後的 metadata：")
                print(f"   共有 {stocks_count_after} 個股票的記錄")

                if metadata_before:
                    new_stocks = stocks_count_after - stocks_count_before
                    if new_stocks > 0:
                        print(f"   新增了 {new_stocks} 個股票的記錄")
                    elif new_stocks < 0:
                        print(f"   減少了 {abs(new_stocks)} 個股票的記錄")
                    else:
                        print(f"   股票數量沒有變化（可能已更新日期）")

                # 顯示前 5 個股票的資訊
                stocks = metadata_after.get("stocks", {})
                if stocks:
                    print(f"\n📋 前 5 個股票的資訊：")
                    for i, (stock_id, stock_info) in enumerate(
                        list(stocks.items())[:5], 1
                    ):
                        last_date = stock_info.get("last_date", "N/A")
                        print(f"   {i}. {stock_id}: last_date = {last_date}")

                print(f"\n📁 Metadata 檔案已保存至: {downloads_metadata_path}")
        else:
            print(f"\n⚠️  metadata 檔案未生成（可能沒有找到任何 CSV 檔案）")

    except Exception as e:
        print(f"\n❌ 執行 update_tick_downloads_metadata() 時發生錯誤: {e}")
        import traceback

        traceback.print_exc()


def test_both_functions():
    """
    測試兩個函數的組合使用
    """
    print(f"\n{'='*60}")
    print(f"測試 scan_tick_downloads_folder() 和 update_tick_downloads_metadata()")
    print(f"{'='*60}")

    # 先測試掃描功能
    print("\n【步驟 1】測試 scan_tick_downloads_folder()")
    stock_last_dates = test_scan_tick_downloads_folder()

    # 再測試更新 metadata
    print("\n【步驟 2】測試 update_tick_downloads_metadata()")
    test_update_tick_downloads_metadata()

    # 驗證一致性
    print(f"\n【步驟 3】驗證一致性")
    downloads_metadata_path = TICK_METADATA_DIR_PATH / "tick_downloads_metadata.json"
    if downloads_metadata_path.exists():
        with open(downloads_metadata_path, "r", encoding="utf-8") as f:
            import json

            metadata = json.load(f)
            metadata_stocks = set(metadata.get("stocks", {}).keys())
            scan_stocks = set(stock_last_dates.keys())

            if metadata_stocks == scan_stocks:
                print(f"✅ 驗證通過：metadata 中的股票與掃描結果一致")
                print(f"   兩者都包含 {len(metadata_stocks)} 個股票")
            else:
                print(f"⚠️  驗證發現差異：")
                only_in_metadata = metadata_stocks - scan_stocks
                only_in_scan = scan_stocks - metadata_stocks
                if only_in_metadata:
                    print(f"   只在 metadata 中: {only_in_metadata}")
                if only_in_scan:
                    print(f"   只在掃描結果中: {only_in_scan}")

    print(f"\n{'='*60}")
    print(f"✅ 所有測試完成！")
    print(f"{'='*60}")


if __name__ == "__main__":
    # 設定 logger（可選，如果需要看到詳細日誌）
    logger.remove()  # 移除預設的 logger
    logger.add(
        lambda msg: print(msg, end=""),
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        level="INFO",
    )

    # ===== 選擇要執行的測試 =====
    import sys

    # 如果沒有提供參數，顯示選單
    if len(sys.argv) == 1:
        print("\n" + "=" * 60)
        print("請選擇要執行的測試：")
        print("=" * 60)
        print("1. 測試 StockTickUpdater.update() - 不存入資料庫")
        print("2. 測試 scan_tick_downloads_folder() - 掃描下載資料夾")
        print("3. 測試 update_tick_downloads_metadata() - 更新 metadata")
        print("4. 測試兩個函數的組合使用")
        print("5. 執行所有測試")
        print("=" * 60)
        choice = input("\n請輸入選項 (1-5): ").strip()
    else:
        choice = sys.argv[1]

    if choice == "1":
        # ===== 測試 StockTickUpdater.update() =====
        # 設定測試日期範圍
        # 請根據您的需求修改這些日期
        test_start_date = datetime.date(2024, 5, 14)  # 開始日期
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

    elif choice == "2":
        # ===== 測試 scan_tick_downloads_folder() =====
        test_scan_tick_downloads_folder()
        print("\n" + "=" * 60)
        print("測試完成！")
        print("=" * 60)

    elif choice == "3":
        # ===== 測試 update_tick_downloads_metadata() =====
        test_update_tick_downloads_metadata()
        print("\n" + "=" * 60)
        print("測試完成！")
        print("=" * 60)

    elif choice == "4":
        # ===== 測試兩個函數的組合使用 =====
        test_both_functions()

    elif choice == "5":
        # ===== 執行所有測試 =====
        print("\n" + "=" * 60)
        print("執行所有測試")
        print("=" * 60)

        # 1. 測試 scan_tick_downloads_folder()
        print("\n【測試 1/3】scan_tick_downloads_folder()")
        test_scan_tick_downloads_folder()

        # 2. 測試 update_tick_downloads_metadata()
        print("\n【測試 2/3】update_tick_downloads_metadata()")
        test_update_tick_downloads_metadata()

        # 3. 測試組合使用
        print("\n【測試 3/3】組合測試")
        test_both_functions()

        print("\n" + "=" * 60)
        print("✅ 所有測試完成！")
        print("=" * 60)

    else:
        print(f"\n❌ 無效的選項: {choice}")
        print("請執行: python test_tick_updater.py [1-5]")
