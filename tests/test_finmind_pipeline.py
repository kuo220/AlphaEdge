import datetime
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any, List, Optional, Tuple
from unittest.mock import patch

# 添加專案根目錄到 Python 路徑
project_root: Path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
from loguru import logger

"""測試 FinMind 完整流程（crawler -> cleaner -> loader），使用臨時資料庫"""


def test_finmind_pipeline():
    """測試 FinMind 完整流程，使用臨時資料庫"""
    # 直接使用字符串常數，避免導入 config 時的循環導入問題
    # 這些常數值與 core.config 中定義的一致
    STOCK_INFO_WITH_WARRANT_TABLE_NAME = "taiwan_stock_info_with_warrant"
    SECURITIES_TRADER_INFO_TABLE_NAME = "taiwan_securities_trader_info"
    STOCK_TRADING_DAILY_REPORT_TABLE_NAME = (
        "taiwan_stock_trading_daily_report_secid_agg"
    )

    # 解決循環導入：使用 mock 在導入前先設置 config 模組
    # 這樣當其他模組導入 config 時，會使用我們預先設置的版本
    import importlib
    from unittest.mock import MagicMock

    # 創建一個臨時的 config mock，包含所有需要的屬性
    temp_config = MagicMock()
    # 設置 log_manager 需要的路徑
    temp_config.BACKTEST_LOGS_DIR_PATH = (
        project_root / "trader" / "backtest" / "results" / "logs"
    )
    temp_config.LOGS_DIR_PATH = project_root / "trader" / "logs"
    # 設置其他可能需要的屬性（使用合理的預設值）
    temp_config.DB_PATH = project_root / "trader" / "database" / "data.db"
    temp_config.FINMIND_DOWNLOADS_PATH = (
        project_root / "trader" / "pipeline" / "downloads" / "finmind"
    )
    temp_config.STOCK_INFO_WITH_WARRANT_TABLE_NAME = STOCK_INFO_WITH_WARRANT_TABLE_NAME
    temp_config.SECURITIES_TRADER_INFO_TABLE_NAME = SECURITIES_TRADER_INFO_TABLE_NAME
    temp_config.STOCK_TRADING_DAILY_REPORT_TABLE_NAME = (
        STOCK_TRADING_DAILY_REPORT_TABLE_NAME
    )

    # 將臨時 config 放入 sys.modules
    sys.modules["core.config"] = temp_config

    # 現在導入其他模組（它們會使用臨時的 config）
    from core.pipeline.cleaners.finmind_cleaner import FinMindCleaner
    from core.pipeline.crawlers.finmind_crawler import FinMindCrawler

    # 現在嘗試導入真正的 config（此時所有依賴的模組都已經初始化）
    # 如果成功，替換臨時的 config
    try:
        # 先移除臨時的 config
        if "core.config" in sys.modules:
            del sys.modules["core.config"]
        # 現在導入真正的 config
        import core.config as real_config

        # 更新臨時 config 的屬性為真實值
        temp_config.DB_PATH = real_config.DB_PATH
        temp_config.FINMIND_DOWNLOADS_PATH = real_config.FINMIND_DOWNLOADS_PATH
        # 將真實的 config 放回 sys.modules
        sys.modules["core.config"] = real_config
    except Exception as e:
        # 如果導入真正的 config 失敗，繼續使用臨時的 config
        print(f"⚠️  無法導入真正的 config，使用臨時配置: {e}")
        sys.modules["core.config"] = temp_config

    # 現在導入 loader（使用真正的或臨時的 config）
    from core.pipeline.loaders.finmind_loader import FinMindLoader

    print(f"\n{'='*60}")
    print(f"測試 FinMind 完整流程（使用臨時資料庫）")
    print(f"{'='*60}")

    # 檢查環境變數
    if not os.getenv("FINMIND_API_TOKEN"):
        print("\n⚠️  警告: 未設置 FINMIND_API_TOKEN 環境變數")
        print("   請在 .env 檔案中設置 FINMIND_API_TOKEN，或使用以下命令：")
        print("   export FINMIND_API_TOKEN=your_token_here")
        print("\n   測試將無法繼續執行")
        return False

    # 創建臨時資料庫檔案
    # 在專案目錄下的 tests/temp 資料夾中創建，方便查找和管理
    temp_dir: Path = project_root / "tests" / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    # 使用時間戳記創建唯一的檔案名
    timestamp: str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_db_path: str = str(temp_dir / f"test_finmind_{timestamp}.db")

    print(f"📁 臨時資料庫路徑: {temp_db_path}")

    try:
        # 使用 mock 替換 DB_PATH，讓 loader 使用臨時資料庫
        # 需要同時 patch 多個地方，因為 DB_PATH 可能在不同模組中被導入
        with patch("core.config.DB_PATH", temp_db_path), patch(
            "core.pipeline.loaders.finmind_loader.DB_PATH", temp_db_path
        ):
            # 初始化各個組件
            print("\n1️⃣ 初始化組件...")
            crawler: FinMindCrawler = FinMindCrawler()
            cleaner: FinMindCleaner = FinMindCleaner()
            loader: FinMindLoader = FinMindLoader()  # 會使用臨時資料庫

            print("✅ 組件初始化完成")

            # ===== 測試 1: 台股總覽(含權證) =====
            print(f"\n{'='*60}")
            print("測試 1: 台股總覽(含權證) - TaiwanStockInfoWithWarrant")
            print(f"{'='*60}")

            # Crawler: 爬取資料
            print("\n📥 步驟 1: 爬取資料...")
            stock_info_df: Optional[pd.DataFrame] = (
                crawler.crawl_stock_info_with_warrant()
            )

            if stock_info_df is None or stock_info_df.empty:
                print("❌ 爬取失敗：沒有取得資料")
                return False

            print(f"✅ 爬取成功！取得 {len(stock_info_df)} 筆資料")
            print(f"   資料欄位: {list(stock_info_df.columns)}")
            print(f"   前 3 筆資料:")
            print(stock_info_df.head(3).to_string())

            # Cleaner: 清洗資料
            print("\n🧹 步驟 2: 清洗資料...")
            cleaned_stock_info_df: Optional[pd.DataFrame] = (
                cleaner.clean_stock_info_with_warrant(stock_info_df)
            )

            if cleaned_stock_info_df is None or cleaned_stock_info_df.empty:
                print("❌ 清洗失敗：清洗後的資料為空")
                return False

            print(f"✅ 清洗成功！清洗後 {len(cleaned_stock_info_df)} 筆資料")

            # Loader: 載入資料到資料庫
            print("\n💾 步驟 3: 載入資料到資料庫...")
            loader.add_to_db(remove_files=False)

            # 驗證資料是否寫入資料庫
            conn: sqlite3.Connection = sqlite3.connect(temp_db_path)
            cursor: sqlite3.Cursor = conn.cursor()

            cursor.execute(f"SELECT COUNT(*) FROM {STOCK_INFO_WITH_WARRANT_TABLE_NAME}")
            count: int = cursor.fetchone()[0]

            if count > 0:
                print(f"✅ 資料載入成功！資料庫中有 {count} 筆資料")
                cursor.execute(
                    f"SELECT * FROM {STOCK_INFO_WITH_WARRANT_TABLE_NAME} LIMIT 3"
                )
                rows: List[Tuple[Any, ...]] = cursor.fetchall()
                print(f"   前 3 筆資料:")
                for row in rows:
                    print(f"   {row}")
            else:
                print("❌ 資料載入失敗：資料庫中沒有資料")
                conn.close()
                return False

            conn.close()

            # ===== 測試 2: 證券商資訊 =====
            print(f"\n{'='*60}")
            print("測試 2: 證券商資訊 - TaiwanSecuritiesTraderInfo")
            print(f"{'='*60}")

            # Crawler: 爬取資料
            print("\n📥 步驟 1: 爬取資料...")
            broker_info_df: Optional[pd.DataFrame] = crawler.crawl_broker_info()

            if broker_info_df is None or broker_info_df.empty:
                print("❌ 爬取失敗：沒有取得資料")
                return False

            print(f"✅ 爬取成功！取得 {len(broker_info_df)} 筆資料")
            print(f"   資料欄位: {list(broker_info_df.columns)}")
            print(f"   前 3 筆資料:")
            print(broker_info_df.head(3).to_string())

            # Cleaner: 清洗資料
            print("\n🧹 步驟 2: 清洗資料...")
            cleaned_broker_info_df: Optional[pd.DataFrame] = cleaner.clean_broker_info(
                broker_info_df
            )

            if cleaned_broker_info_df is None or cleaned_broker_info_df.empty:
                print("❌ 清洗失敗：清洗後的資料為空")
                return False

            print(f"✅ 清洗成功！清洗後 {len(cleaned_broker_info_df)} 筆資料")

            # Loader: 載入資料到資料庫
            print("\n💾 步驟 3: 載入資料到資料庫...")
            loader.add_to_db(remove_files=False)

            # 驗證資料是否寫入資料庫
            conn: sqlite3.Connection = sqlite3.connect(temp_db_path)
            cursor: sqlite3.Cursor = conn.cursor()

            cursor.execute(f"SELECT COUNT(*) FROM {SECURITIES_TRADER_INFO_TABLE_NAME}")
            count: int = cursor.fetchone()[0]

            if count > 0:
                print(f"✅ 資料載入成功！資料庫中有 {count} 筆資料")
                cursor.execute(
                    f"SELECT * FROM {SECURITIES_TRADER_INFO_TABLE_NAME} LIMIT 3"
                )
                rows: List[Tuple[Any, ...]] = cursor.fetchall()
                print(f"   前 3 筆資料:")
                for row in rows:
                    print(f"   {row}")
            else:
                print("❌ 資料載入失敗：資料庫中沒有資料")
                conn.close()
                return False

            conn.close()

            # ===== 測試 3: 當日券商分點統計表 =====
            print(f"\n{'='*60}")
            print("測試 3: 當日券商分點統計表 - TaiwanStockTradingDailyReportSecIdAgg")
            print(f"{'='*60}")

            # 設定測試參數（使用 finmind.ipynb 中的參數）
            test_stock_id: str = "2330"
            test_broker_id: str = "1020"
            start_date: str = "2024-07-01"
            end_date: str = "2024-07-15"

            print(f"   測試參數:")
            print(f"   - 股票代碼: {test_stock_id}")
            print(f"   - 券商代碼: {test_broker_id}")
            print(f"   - 日期範圍: {start_date} 到 {end_date}")

            # Crawler: 爬取資料
            print("\n📥 步驟 1: 爬取資料...")

            trading_report_df: Optional[pd.DataFrame] = (
                crawler.crawl_broker_trading_daily_report(
                    stock_id=test_stock_id,
                    securities_trader_id=test_broker_id,
                    start_date=start_date,
                    end_date=end_date,
                )
            )

            if trading_report_df is None or trading_report_df.empty:
                print("⚠️  爬取失敗：沒有取得資料（可能是該日期範圍內沒有交易資料）")
                print("   這是正常的，因為不是所有股票和券商在每個日期都有交易")
                print("   繼續測試其他功能...")
            else:
                print(f"✅ 爬取成功！取得 {len(trading_report_df)} 筆資料")
                print(f"   資料欄位: {list(trading_report_df.columns)}")
                print(f"   前 3 筆資料:")
                print(trading_report_df.head(3).to_string())

                # Cleaner: 清洗資料
                print("\n🧹 步驟 2: 清洗資料...")
                cleaned_trading_report_df: Optional[pd.DataFrame] = (
                    cleaner.clean_broker_trading_daily_report(trading_report_df)
                )

                if cleaned_trading_report_df is None or cleaned_trading_report_df.empty:
                    print("❌ 清洗失敗：清洗後的資料為空")
                    return False

                print(f"✅ 清洗成功！清洗後 {len(cleaned_trading_report_df)} 筆資料")

                # Loader: 載入資料到資料庫
                print("\n💾 步驟 3: 載入資料到資料庫...")
                loader.add_to_db(remove_files=False)

                # 驗證資料是否寫入資料庫
                conn: sqlite3.Connection = sqlite3.connect(temp_db_path)
                cursor: sqlite3.Cursor = conn.cursor()

                cursor.execute(
                    f"SELECT COUNT(*) FROM {STOCK_TRADING_DAILY_REPORT_TABLE_NAME}"
                )
                count: int = cursor.fetchone()[0]

                if count > 0:
                    print(f"✅ 資料載入成功！資料庫中有 {count} 筆資料")
                    cursor.execute(
                        f"SELECT * FROM {STOCK_TRADING_DAILY_REPORT_TABLE_NAME} LIMIT 3"
                    )
                    rows: List[Tuple[Any, ...]] = cursor.fetchall()
                    print(f"   前 3 筆資料:")
                    for row in rows:
                        print(f"   {row}")
                else:
                    print("⚠️  資料庫中沒有資料（可能是因為資料已存在或沒有新資料）")

                conn.close()

            # ===== 最終驗證 =====
            print(f"\n{'='*60}")
            print("最終驗證：檢查所有資料表")
            print(f"{'='*60}")

            conn: sqlite3.Connection = sqlite3.connect(temp_db_path)
            cursor: sqlite3.Cursor = conn.cursor()

            # 檢查所有資料表
            tables: List[str] = [
                STOCK_INFO_WITH_WARRANT_TABLE_NAME,
                SECURITIES_TRADER_INFO_TABLE_NAME,
                STOCK_TRADING_DAILY_REPORT_TABLE_NAME,
            ]

            all_success: bool = True
            for table_name in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count: int = cursor.fetchone()[0]
                status: str = "✅" if count > 0 else "⚠️"
                print(f"{status} {table_name}: {count} 筆資料")
                if count == 0 and table_name != STOCK_TRADING_DAILY_REPORT_TABLE_NAME:
                    # 交易報表可能為空是正常的
                    all_success = False

            conn.close()

            # 清理 loader 連接
            loader.disconnect()

            if all_success:
                print(f"\n{'='*60}")
                print("✅ 所有測試通過！")
                print(f"{'='*60}")
                print(f"📁 臨時資料庫位置: {temp_db_path}")
                print("   測試完成後可以手動刪除此檔案")
                return True
            else:
                print(f"\n{'='*60}")
                print("⚠️  部分測試未完全通過，請檢查上述結果")
                print(f"{'='*60}")
                return False

    except Exception as e:
        print(f"\n❌ 測試過程中發生錯誤: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        # 清理臨時資料庫（可選，保留以便檢查）
        # 如果需要保留資料庫檔案進行檢查，可以註解掉下面這行
        # Path(temp_db_path).unlink(missing_ok=True)
        # print(f"\n🗑️  已清理臨時資料庫: {temp_db_path}")
        pass


if __name__ == "__main__":
    # 設定 logger
    logger.remove()  # 移除預設的 logger
    logger.add(lambda msg: print(msg, end=""), format="{message}")

    # 執行測試
    success: bool = test_finmind_pipeline()

    if success:
        print("\n🎉 測試完成！")
    else:
        print("\n⚠️  測試未完全成功，請檢查上述輸出")
