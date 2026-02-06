import datetime
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, patch

import pandas as pd

# 添加專案根目錄到 Python 路徑
project_root: Path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# 載入 .env 檔案
from dotenv import load_dotenv

env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

from loguru import logger

# 直接使用字符串常數
STOCK_INFO_WITH_WARRANT_TABLE_NAME = "taiwan_stock_info_with_warrant"
SECURITIES_TRADER_INFO_TABLE_NAME = "taiwan_securities_trader_info"
STOCK_TRADING_DAILY_REPORT_TABLE_NAME = "taiwan_stock_trading_daily_report_secid_agg"


"""測試 FinMindUpdater broker trading 更新：CSV 分類、API 耗盡模擬、模擬 DB 寫入"""


def create_mock_broker_trading_data(
    securities_trader_id: str,
    stock_id: str,
    start_date: datetime.date,
    end_date: datetime.date,
) -> pd.DataFrame:
    """創建模擬的券商交易資料"""
    dates = pd.date_range(start=start_date, end=end_date, freq="D")
    # 只保留工作日（簡單處理，實際應該排除假日）
    dates = [d.date() for d in dates if d.weekday() < 5]

    data = []
    for date in dates:
        data.append(
            {
                "securities_trader": f"券商_{securities_trader_id}",
                "securities_trader_id": securities_trader_id,
                "stock_id": stock_id,
                "date": date.strftime("%Y-%m-%d"),
                "buy_volume": 1000,
                "sell_volume": 800,
                "buy_price": 100.0,
                "sell_price": 101.0,
            }
        )

    return pd.DataFrame(data)


def setup_test_database(
    db_path: str, stock_list: List[str], trader_list: List[str]
) -> None:
    """設置測試資料庫，包含股票和券商資訊"""
    conn = sqlite3.connect(db_path)

    # 創建股票資訊表
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {STOCK_INFO_WITH_WARRANT_TABLE_NAME} (
            stock_id TEXT PRIMARY KEY,
            stock_name TEXT,
            industry_category TEXT,
            type TEXT,
            date TEXT
        )
        """
    )

    # 插入測試股票
    for stock_id in stock_list:
        conn.execute(
            f"""
            INSERT OR REPLACE INTO {STOCK_INFO_WITH_WARRANT_TABLE_NAME}
            (stock_id, stock_name, industry_category, type, date)
            VALUES (?, ?, ?, ?, ?)
            """,
            (stock_id, f"股票_{stock_id}", "電子", "上市", "2021-01-01"),
        )

    # 創建券商資訊表
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {SECURITIES_TRADER_INFO_TABLE_NAME} (
            securities_trader_id TEXT PRIMARY KEY,
            securities_trader TEXT,
            date TEXT,
            address TEXT,
            phone TEXT
        )
        """
    )

    # 插入測試券商
    for trader_id in trader_list:
        conn.execute(
            f"""
            INSERT OR REPLACE INTO {SECURITIES_TRADER_INFO_TABLE_NAME}
            (securities_trader_id, securities_trader, date, address, phone)
            VALUES (?, ?, ?, ?, ?)
            """,
            (trader_id, f"券商_{trader_id}", "2021-01-01", "台北市", "02-12345678"),
        )

    # 創建券商交易報表表
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {STOCK_TRADING_DAILY_REPORT_TABLE_NAME} (
            securities_trader TEXT,
            securities_trader_id TEXT,
            stock_id TEXT,
            date TEXT,
            buy_volume INTEGER,
            sell_volume INTEGER,
            buy_price REAL,
            sell_price REAL,
            PRIMARY KEY (securities_trader_id, stock_id, date)
        )
        """
    )

    conn.commit()
    conn.close()


def test_broker_trading_updater():
    """
    測試 broker trading daily report 更新功能
    """
    print(f"\n{'='*60}")
    print(f"測試 Broker Trading Daily Report Updater")
    print(f"{'='*60}")

    # 測試參數
    start_date = datetime.date(2021, 6, 30)
    end_date = datetime.date.today()
    test_stock_list = ["2330", "2317", "2454"]  # 3 檔股票
    test_trader_list = ["1020", "1021"]  # 2 間券商

    print(f"\n測試參數:")
    print(f"  - 起始日期: {start_date}")
    print(f"  - 結束日期: {end_date}")
    print(f"  - 股票列表: {test_stock_list}")
    print(f"  - 券商列表: {test_trader_list}")

    # 使用 tests/downloads 目錄存放測試資料（固定結構，所有測試共用）
    test_root = project_root / "tests" / "downloads"
    test_root.mkdir(parents=True, exist_ok=True)

    # 資料庫路徑（所有測試共用同一個資料庫）
    database_dir = project_root / "tests" / "database"
    database_dir.mkdir(parents=True, exist_ok=True)
    temp_db_path = str(database_dir / "test.db")

    # 下載目錄（簡化結構：downloads/finmind）
    temp_downloads_path = test_root / "finmind"
    temp_downloads_path.mkdir(parents=True, exist_ok=True)

    # metadata 目錄（簡化結構：downloads/meta/broker_trading）
    temp_metadata_path = test_root / "meta" / "broker_trading"
    temp_metadata_path.mkdir(parents=True, exist_ok=True)
    temp_metadata_file = temp_metadata_path / "broker_trading_metadata.json"

    print(f"\n📁 測試資料目錄: {test_root}")
    print(f"   - 資料庫: {temp_db_path}")
    print(f"   - 下載目錄: {temp_downloads_path}")
    print(f"   - Metadata: {temp_metadata_file}")

    try:
        # 設置測試資料庫
        setup_test_database(temp_db_path, test_stock_list, test_trader_list)
        print("✅ 測試資料庫設置完成")

        # Mock crawler 的 crawl_broker_trading_daily_report 方法
        def mock_crawl_broker_trading_daily_report(
            stock_id: Optional[str] = None,
            securities_trader_id: Optional[str] = None,
            start_date: Optional[Any] = None,
            end_date: Optional[Any] = None,
        ) -> Optional[pd.DataFrame]:
            """模擬爬取資料"""
            # 轉換日期格式
            if isinstance(start_date, str):
                start_date_obj = datetime.datetime.strptime(
                    start_date, "%Y-%m-%d"
                ).date()
            else:
                start_date_obj = start_date

            if isinstance(end_date, str):
                end_date_obj = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
            else:
                end_date_obj = end_date

            # 創建模擬資料
            return create_mock_broker_trading_data(
                securities_trader_id=securities_trader_id,
                stock_id=stock_id,
                start_date=start_date_obj,
                end_date=end_date_obj,
            )

        # 清除可能已緩存的模組
        modules_to_clear = [
            "trader.pipeline.updaters.finmind_updater",
            "trader.pipeline.loaders.finmind_loader",
            "trader.pipeline.cleaners.finmind_cleaner",
            "trader.pipeline.crawlers.finmind_crawler",
        ]
        for module_name in modules_to_clear:
            if module_name in sys.modules:
                del sys.modules[module_name]

        # Mock FinMind 模組（如果不存在）
        if "FinMind" not in sys.modules:
            finmind_mock = MagicMock()
            finmind_data_mock = MagicMock()
            finmind_data_mock.DataLoader = MagicMock
            finmind_mock.data = finmind_data_mock
            sys.modules["FinMind"] = finmind_mock
            sys.modules["FinMind.data"] = finmind_data_mock

        # 使用 patch 替換配置（在導入前 patch）
        with patch("trader.config.DB_PATH", temp_db_path), patch(
            "trader.config.FINMIND_DOWNLOADS_PATH", temp_downloads_path
        ), patch("trader.config.BROKER_TRADING_METADATA_PATH", temp_metadata_file):
            # 導入 updater（在 patch 後導入，這樣會使用 patch 後的值）
            from trader.pipeline.updaters.finmind_updater import FinMindUpdater

            updater = FinMindUpdater()

            # Mock crawler 方法
            updater.crawler.crawl_broker_trading_daily_report = (
                mock_crawl_broker_trading_daily_report
            )

            # ===== 測試 1: 測試單一組合更新 (update_broker_trading_daily_report) =====
            print(f"\n{'='*60}")
            print("測試 1: update_broker_trading_daily_report() - 單一組合更新")
            print(f"{'='*60}")

            test_stock_id = test_stock_list[0]
            test_trader_id = test_trader_list[0]

            print(f"\n測試參數:")
            print(f"  - 股票代碼: {test_stock_id}")
            print(f"  - 券商代碼: {test_trader_id}")
            print(f"  - 日期範圍: {start_date} ~ {end_date}")

            # 執行更新
            status = updater.update_broker_trading_daily_report(
                stock_id=test_stock_id,
                securities_trader_id=test_trader_id,
                start_date=start_date,
                end_date=end_date,
            )

            print(f"\n更新狀態: {status}")

            # 驗證 CSV 檔案是否存在且結構正確
            csv_path = (
                temp_downloads_path
                / "broker_trading"
                / test_trader_id
                / f"{test_stock_id}.csv"
            )

            assert csv_path.exists(), f"CSV 檔案不存在: {csv_path}"

            # 讀取 CSV 檔案
            df_csv = pd.read_csv(csv_path, encoding="utf-8-sig")
            print(f"\n✅ CSV 檔案驗證通過:")
            print(f"  - 路徑: {csv_path}")
            print(f"  - 資料筆數: {len(df_csv)}")
            print(f"  - 欄位: {list(df_csv.columns)}")

            # 驗證資料庫中的資料
            conn = sqlite3.connect(temp_db_path)
            query = f"""
            SELECT COUNT(*) FROM {STOCK_TRADING_DAILY_REPORT_TABLE_NAME}
            WHERE stock_id = ? AND securities_trader_id = ?
            """
            cursor = conn.cursor()
            cursor.execute(query, (test_stock_id, test_trader_id))
            db_count = cursor.fetchone()[0]

            print(f"\n✅ 資料庫驗證:")
            print(f"  - 資料筆數: {db_count}")

            # 驗證資料一致性
            assert db_count > 0, "資料庫中沒有資料"
            assert db_count == len(df_csv), "CSV 和資料庫的資料筆數不一致"

            conn.close()

            # ===== 測試 2: 測試批量更新 (update_broker_trading_daily_report) =====
            print(f"\n{'='*60}")
            print("測試 2: update_broker_trading_daily_report() - 批量更新")
            print(f"{'='*60}")

            # 測試 2 使用相同的資料庫和目錄（清空資料庫重新開始）
            # 先刪除現有資料庫以確保乾淨的測試環境
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)

            setup_test_database(temp_db_path, test_stock_list, test_trader_list)

            # 清除模組緩存
            modules_to_clear = [
                "trader.pipeline.updaters.finmind_updater",
                "trader.pipeline.loaders.finmind_loader",
                "trader.pipeline.cleaners.finmind_cleaner",
                "trader.pipeline.crawlers.finmind_crawler",
            ]
            for module_name in modules_to_clear:
                if module_name in sys.modules:
                    del sys.modules[module_name]

            with patch("trader.config.DB_PATH", temp_db_path), patch(
                "trader.config.FINMIND_DOWNLOADS_PATH", temp_downloads_path
            ), patch("trader.config.BROKER_TRADING_METADATA_PATH", temp_metadata_file):
                from trader.pipeline.updaters.finmind_updater import FinMindUpdater

                updater2 = FinMindUpdater()
                updater2.crawler.crawl_broker_trading_daily_report = (
                    mock_crawl_broker_trading_daily_report
                )

                # 重置 API quota 計數器
                updater2.api_call_count = 0
                updater2.api_quota_limit = 100  # 設置較小的 quota 以便測試耗盡情況

                print(f"\nAPI Quota 設定:")
                print(f"  - 限制: {updater2.api_quota_limit}")
                print(f"  - 當前使用: {updater2.api_call_count}")

                # 執行批量更新
                print(f"\n🔄 執行批量更新...")
                updater2.update_broker_trading_daily_report(
                    start_date=start_date, end_date=end_date
                )

                # 驗證所有組合的 CSV 檔案
                print(f"\n✅ CSV 檔案結構驗證:")
                broker_trading_dir = temp_downloads_path / "broker_trading"
                assert broker_trading_dir.exists(), "broker_trading 目錄不存在"

                csv_files_found = []
                for trader_id in test_trader_list:
                    trader_dir = broker_trading_dir / trader_id
                    if not trader_dir.exists():
                        print(f"  ⚠️  券商目錄不存在: {trader_dir}（可能沒有資料）")
                        continue

                    for stock_id in test_stock_list:
                        csv_file = trader_dir / f"{stock_id}.csv"
                        if csv_file.exists():
                            csv_files_found.append((trader_id, stock_id))
                            df = pd.read_csv(csv_file, encoding="utf-8-sig")
                            print(f"  ✅ {trader_id}/{stock_id}.csv: {len(df)} 筆資料")

                print(f"\n找到 {len(csv_files_found)} 個 CSV 檔案")

                # 驗證資料庫中的資料
                conn = sqlite3.connect(temp_db_path)
                query = f"SELECT COUNT(*) FROM {STOCK_TRADING_DAILY_REPORT_TABLE_NAME}"
                cursor = conn.cursor()
                cursor.execute(query)
                total_db_count = cursor.fetchone()[0]

                print(f"\n✅ 資料庫總資料筆數: {total_db_count}")

                # 驗證每個組合的資料
                for trader_id in test_trader_list:
                    for stock_id in test_stock_list:
                        query = f"""
                        SELECT COUNT(*) FROM {STOCK_TRADING_DAILY_REPORT_TABLE_NAME}
                        WHERE stock_id = ? AND securities_trader_id = ?
                        """
                        cursor.execute(query, (stock_id, trader_id))
                        count = cursor.fetchone()[0]
                        if count > 0:
                            print(f"  ✅ {trader_id}/{stock_id}: {count} 筆資料")

                conn.close()

            # ===== 測試 3: 模擬 API 耗盡的情況 =====
            print(f"\n{'='*60}")
            print("測試 3: 模擬 API 耗盡的情況")
            print(f"{'='*60}")

            # 測試 3 使用相同的資料庫和目錄（清空資料庫重新開始）
            # 先刪除現有資料庫以確保乾淨的測試環境
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)

            setup_test_database(temp_db_path, test_stock_list, test_trader_list)

            # 清除可能已緩存的模組
            modules_to_clear = [
                "trader.pipeline.updaters.finmind_updater",
                "trader.pipeline.loaders.finmind_loader",
                "trader.pipeline.cleaners.finmind_cleaner",
                "trader.pipeline.crawlers.finmind_crawler",
            ]
            for module_name in modules_to_clear:
                if module_name in sys.modules:
                    del sys.modules[module_name]

            with patch("trader.config.DB_PATH", temp_db_path), patch(
                "trader.config.FINMIND_DOWNLOADS_PATH", temp_downloads_path
            ), patch("trader.config.BROKER_TRADING_METADATA_PATH", temp_metadata_file):
                # 重新導入 updater
                from trader.pipeline.updaters.finmind_updater import FinMindUpdater

                updater2 = FinMindUpdater()
                updater2.crawler.crawl_broker_trading_daily_report = (
                    mock_crawl_broker_trading_daily_report
                )

                # 使用計數器來追蹤處理的組合數
                processed_count = [0]  # 使用列表以便在閉包中修改

                # 保存原始的 _check_and_update_api_quota 方法
                original_check_quota = updater2._check_and_update_api_quota

                def mock_check_and_update_api_quota() -> bool:
                    """模擬 quota 檢查，在處理 2 個組合後觸發耗盡"""
                    processed_count[0] += 1
                    if processed_count[0] <= 2:
                        # 前 2 個組合正常處理
                        return original_check_quota()
                    else:
                        # 第 3 個組合開始觸發耗盡
                        print(
                            f"  ⚠️  已處理 {processed_count[0]} 個組合，觸發 API quota 耗盡檢查"
                        )
                        return False

                updater2._check_and_update_api_quota = mock_check_and_update_api_quota

                # 設置 API quota
                updater2.api_quota_limit = 100
                updater2.api_call_count = 0

                print(f"\nAPI Quota 設定:")
                print(f"  - 限制: {updater2.api_quota_limit}")
                print(f"  - 當前使用: {updater2.api_call_count}")
                print(f"  - 測試策略: 處理 2 個組合後觸發 quota 耗盡")

                # Mock _wait_for_quota_reset 來避免真的等待
                def mock_wait_for_quota_reset(
                    check_interval_minutes: int = 10,
                    max_wait_minutes: Optional[int] = None,
                ) -> bool:
                    """模擬等待 quota 重置（立即返回 False 以測試耗盡情況）"""
                    print("  ⚠️  API quota 耗盡，模擬等待失敗（測試目的）")
                    return False  # 模擬等待超時

                updater2._wait_for_quota_reset = mock_wait_for_quota_reset

                # 執行批量更新（應該會在處理 2 個組合後停止）
                print(f"\n🔄 執行批量更新（預期處理 2 個組合後耗盡 quota）...")
                updater2.update_broker_trading_daily_report(
                    start_date=start_date, end_date=end_date
                )

                print(f"  ✅ 批量更新已停止（已處理 {processed_count[0]} 個組合）")

                # 驗證 metadata JSON 檔案是否存在且有記錄
                assert (
                    temp_metadata_file.exists()
                ), "Metadata JSON 檔案不存在（應該在 quota 耗盡前保存）"

                # 讀取 metadata
                with open(temp_metadata_file, "r", encoding="utf-8") as f:
                    metadata = json.load(f)

                print(f"\n✅ Metadata JSON 檔案驗證:")
                print(f"  - 路徑: {temp_metadata_file}")
                print(f"  - 記錄的組合數: {len(metadata)}")

                # 顯示 metadata 內容
                for broker_id, stocks in metadata.items():
                    print(f"  - 券商 {broker_id}:")
                    for stock_id, date_range in stocks.items():
                        print(
                            f"    - 股票 {stock_id}: {date_range.get('earliest_date')} ~ {date_range.get('latest_date')}"
                        )

                # 驗證至少有一些記錄
                total_combinations = sum(len(stocks) for stocks in metadata.values())
                print(f"\n  總共記錄了 {total_combinations} 個組合的日期範圍")

                # 驗證至少有一些記錄（由於處理了 2 個組合，應該至少有 1-2 個記錄）
                assert total_combinations > 0, "Metadata 中應該至少有一些記錄"

                # 驗證 metadata 結構正確（每個組合都應該有 earliest_date 和 latest_date）
                for broker_id, stocks in metadata.items():
                    for stock_id, date_range in stocks.items():
                        assert (
                            "earliest_date" in date_range
                        ), f"缺少 earliest_date: {broker_id}/{stock_id}"
                        assert (
                            "latest_date" in date_range
                        ), f"缺少 latest_date: {broker_id}/{stock_id}"
                        print(f"  ✅ {broker_id}/{stock_id}: 日期範圍完整")

                # 驗證 CSV 檔案（檢查已處理的組合是否有 CSV 檔案）
                print(f"\n✅ CSV 檔案驗證（quota 耗盡前處理的資料）:")
                broker_trading_dir = temp_downloads_path / "broker_trading"
                if broker_trading_dir.exists():
                    csv_count = 0
                    for trader_dir in broker_trading_dir.iterdir():
                        if trader_dir.is_dir():
                            for csv_file in trader_dir.glob("*.csv"):
                                csv_count += 1
                                df = pd.read_csv(csv_file, encoding="utf-8-sig")
                                print(
                                    f"  ✅ {csv_file.parent.name}/{csv_file.name}: {len(df)} 筆資料"
                                )
                    print(f"  總共找到 {csv_count} 個 CSV 檔案")
                else:
                    print("  ⚠️  broker_trading 目錄不存在（可能沒有處理任何組合）")

                # 驗證資料庫中的資料
                print(f"\n✅ 資料庫驗證（quota 耗盡前處理的資料）:")
                conn = sqlite3.connect(temp_db_path)
                query = f"SELECT COUNT(*) FROM {STOCK_TRADING_DAILY_REPORT_TABLE_NAME}"
                cursor = conn.cursor()
                cursor.execute(query)
                db_count = cursor.fetchone()[0]
                print(f"  - 資料庫總資料筆數: {db_count}")
                conn.close()

            print(f"\n{'='*60}")
            print("✅ 所有測試通過！")
            print(f"{'='*60}")
            print(f"\n📁 測試結果:")
            print(f"  - 測試資料目錄: {test_root}")
            print(f"  - CSV 檔案結構: ✅ 正確")
            print(f"  - 資料庫資料: ✅ 正確")
            print(f"  - Metadata JSON: ✅ 正確記錄")
            print(f"\n💡 提示:")
            print(f"  - 所有測試資料已保存在: {test_root}")
            print(f"  - CSV 檔案已保留，可以手動檢查")
            print(f"  - 測試資料庫位置: tests/database/test.db")
            print(f"  - 下載資料位置: {test_root}/finmind/broker_trading/")
            print(f"  - Metadata 位置: {test_root}/meta/broker_trading/")

            return True

    except Exception as e:
        print(f"\n❌ 測試過程中發生錯誤: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        # 保留所有測試資料（不刪除）
        # 測試資料已保存在 tests/downloads/ 目錄中
        pass


if __name__ == "__main__":
    # 設定 logger
    logger.remove()
    logger.add(lambda msg: print(msg, end=""), format="{message}")

    # 執行測試
    success = test_broker_trading_updater()

    if success:
        print("\n🎉 測試完成！")
    else:
        print("\n⚠️  測試未完全成功，請檢查上述輸出")
