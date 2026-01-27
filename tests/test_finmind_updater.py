"""
測試 FinMindUpdater 的更新功能
使用臨時資料庫進行測試，不會影響 data.db
"""

import datetime
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, List, Optional, Tuple
from unittest.mock import patch

# 添加專案根目錄到 Python 路徑
project_root: Path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# 載入 .env 檔案（在檢查環境變數之前）
from dotenv import load_dotenv

# 載入專案根目錄的 .env 檔案
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    # 如果根目錄沒有 .env，嘗試載入預設位置
    load_dotenv()

from loguru import logger

# 直接使用字符串常數，避免導入 config 時的循環導入問題
STOCK_INFO_WITH_WARRANT_TABLE_NAME = "taiwan_stock_info_with_warrant"
SECURITIES_TRADER_INFO_TABLE_NAME = "taiwan_securities_trader_info"
STOCK_TRADING_DAILY_REPORT_TABLE_NAME = (
    "taiwan_stock_trading_daily_report_secid_agg"
)


def test_finmind_updater():
    """
    測試 FinMindUpdater 的各種更新方法
    使用臨時資料庫進行測試
    """
    print(f"\n{'='*60}")
    print(f"測試 FinMindUpdater（使用臨時資料庫）")
    print(f"{'='*60}")

    # 檢查環境變數是否已載入
    api_token = os.getenv("FINMIND_API_TOKEN")
    if api_token:
        # 只顯示 token 的前後部分，保護隱私
        token_preview = (
            f"{api_token[:20]}...{api_token[-10:]}" if len(api_token) > 30 else "***"
        )
        print(f"\n✅ 已載入 FINMIND_API_TOKEN: {token_preview}")
    else:
        print("\n" + "=" * 60)
        print("⚠️  警告: 未設置 FINMIND_API_TOKEN 環境變數")
        print("=" * 60)
        print("\n此測試需要 FinMind API Token 才能執行。")
        print("\n設置方式：")
        print("1. 在專案根目錄的 .env 檔案中添加：")
        print("   FINMIND_API_TOKEN=your_token_here")
        print("\n2. 或在終端機中執行：")
        print("   export FINMIND_API_TOKEN=your_token_here")
        print("\n3. 取得 Token 的方式：")
        print("   - 前往 https://finmindtrade.com/")
        print("   - 註冊帳號並取得 API Token")
        print("\n" + "=" * 60)
        print("測試將無法繼續執行")
        print("=" * 60)
        return False

    # 先導入不依賴 config 的模組
    from trader.pipeline.utils import FinMindDataType

    # 解決循環導入：使用 mock 在導入前先設置 config 模組
    from unittest.mock import MagicMock

    # 創建一個臨時的 config mock，包含所有需要的屬性
    temp_config = MagicMock()
    temp_config.BACKTEST_LOGS_DIR_PATH = (
        project_root / "trader" / "backtest" / "results" / "logs"
    )
    temp_config.LOGS_DIR_PATH = project_root / "trader" / "logs"
    temp_config.DB_PATH = project_root / "trader" / "database" / "data.db"
    temp_config.FINMIND_DOWNLOADS_PATH = (
        project_root / "trader" / "pipeline" / "downloads" / "finmind"
    )
    temp_config.STOCK_INFO_WITH_WARRANT_TABLE_NAME = (
        STOCK_INFO_WITH_WARRANT_TABLE_NAME
    )
    temp_config.SECURITIES_TRADER_INFO_TABLE_NAME = (
        SECURITIES_TRADER_INFO_TABLE_NAME
    )
    temp_config.STOCK_TRADING_DAILY_REPORT_TABLE_NAME = (
        STOCK_TRADING_DAILY_REPORT_TABLE_NAME
    )

    # 將臨時 config 放入 sys.modules（如果還沒有）
    if "trader.config" not in sys.modules:
        sys.modules["trader.config"] = temp_config

    # 現在嘗試導入真正的 config
    try:
        # 先移除臨時的 config
        if "trader.config" in sys.modules:
            del sys.modules["trader.config"]
        # 現在導入真正的 config
        import trader.config as real_config

        # 更新臨時 config 的屬性為真實值
        temp_config.DB_PATH = real_config.DB_PATH
        temp_config.FINMIND_DOWNLOADS_PATH = real_config.FINMIND_DOWNLOADS_PATH
        # 將真實的 config 放回 sys.modules
        sys.modules["trader.config"] = real_config
    except Exception as e:
        # 如果導入真正的 config 失敗，繼續使用臨時的 config
        print(f"⚠️  無法導入真正的 config，使用臨時配置: {e}")
        sys.modules["trader.config"] = temp_config

    # 現在導入 updater（使用真正的或臨時的 config）
    from trader.pipeline.updaters.finmind_updater import FinMindUpdater

    # 創建臨時資料庫檔案
    temp_dir: Path = project_root / "tests" / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    timestamp: str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_db_path: str = str(temp_dir / f"test_finmind_updater_{timestamp}.db")

    print(f"📁 臨時資料庫路徑: {temp_db_path}")

    try:
        # 使用 mock 替換 DB_PATH
        with patch("trader.config.DB_PATH", temp_db_path), patch(
            "trader.pipeline.updaters.finmind_updater.DB_PATH", temp_db_path
        ), patch(
            "trader.pipeline.loaders.finmind_loader.DB_PATH", temp_db_path
        ):
            # ===== 測試 1: update_stock_info_with_warrant =====
            print(f"\n{'='*60}")
            print("測試 1: update_stock_info_with_warrant()")
            print(f"{'='*60}")

            updater: FinMindUpdater = FinMindUpdater()
            print("✅ FinMindUpdater 初始化完成")

            # 執行更新
            print("\n🔄 執行更新...")
            updater.update_stock_info_with_warrant()

            # 驗證資料是否寫入資料庫
            conn: sqlite3.Connection = sqlite3.connect(temp_db_path)
            cursor: sqlite3.Cursor = conn.cursor()

            cursor.execute(
                f"SELECT COUNT(*) FROM {STOCK_INFO_WITH_WARRANT_TABLE_NAME}"
            )
            count: int = cursor.fetchone()[0]

            if count > 0:
                print(f"✅ 更新成功！資料庫中有 {count} 筆資料")
                cursor.execute(
                    f"SELECT * FROM {STOCK_INFO_WITH_WARRANT_TABLE_NAME} LIMIT 3"
                )
                rows: List[Tuple[Any, ...]] = cursor.fetchall()
                print(f"   前 3 筆資料:")
                for row in rows:
                    print(f"   {row}")
            else:
                print("⚠️  資料庫中沒有資料（可能是資料已存在）")

            conn.close()

            # ===== 測試 2: update_broker_info =====
            print(f"\n{'='*60}")
            print("測試 2: update_broker_info()")
            print(f"{'='*60}")

            print("\n🔄 執行更新...")
            updater.update_broker_info()

            # 驗證資料是否寫入資料庫
            conn = sqlite3.connect(temp_db_path)
            cursor = conn.cursor()

            cursor.execute(
                f"SELECT COUNT(*) FROM {SECURITIES_TRADER_INFO_TABLE_NAME}"
            )
            count = cursor.fetchone()[0]

            if count > 0:
                print(f"✅ 更新成功！資料庫中有 {count} 筆資料")
                cursor.execute(
                    f"SELECT * FROM {SECURITIES_TRADER_INFO_TABLE_NAME} LIMIT 3"
                )
                rows = cursor.fetchall()
                print(f"   前 3 筆資料:")
                for row in rows:
                    print(f"   {row}")
            else:
                print("⚠️  資料庫中沒有資料（可能是資料已存在）")

            conn.close()

            # ===== 測試 3: update_broker_trading_daily_report =====
            print(f"\n{'='*60}")
            print("測試 3: update_broker_trading_daily_report()")
            print(f"{'='*60}")

            # 設定測試參數
            start_date = datetime.date(2024, 7, 1)
            end_date = datetime.date(2024, 7, 15)
            test_stock_id = "2330"
            test_broker_id = "1020"

            print(f"   測試參數:")
            print(f"   - 起始日期: {start_date}")
            print(f"   - 結束日期: {end_date}")
            print(f"   - 股票代碼: {test_stock_id}")
            print(f"   - 券商代碼: {test_broker_id}")

            print("\n🔄 執行更新...")
            updater.update_broker_trading_daily_report(
                start_date=start_date,
                end_date=end_date,
                stock_id=test_stock_id,
                securities_trader_id=test_broker_id,
            )

            # 驗證資料是否寫入資料庫
            conn = sqlite3.connect(temp_db_path)
            cursor = conn.cursor()

            cursor.execute(
                f"SELECT COUNT(*) FROM {STOCK_TRADING_DAILY_REPORT_TABLE_NAME}"
            )
            count = cursor.fetchone()[0]

            if count > 0:
                print(f"✅ 更新成功！資料庫中有 {count} 筆資料")
                cursor.execute(
                    f"SELECT * FROM {STOCK_TRADING_DAILY_REPORT_TABLE_NAME} LIMIT 3"
                )
                rows = cursor.fetchall()
                print(f"   前 3 筆資料:")
                for row in rows:
                    print(f"   {row}")
            else:
                print(
                    "⚠️  資料庫中沒有資料（可能是該日期範圍內沒有交易資料或資料已存在）"
                )

            conn.close()

            # ===== 測試 4: update() 方法 - 使用 Enum =====
            print(f"\n{'='*60}")
            print("測試 4: update() 方法 - 使用 FinMindDataType Enum")
            print(f"{'='*60}")

            print("\n🔄 測試 update(data_type=FinMindDataType.STOCK_INFO)...")
            updater.update(data_type=FinMindDataType.STOCK_INFO)

            conn = sqlite3.connect(temp_db_path)
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT COUNT(*) FROM {STOCK_INFO_WITH_WARRANT_TABLE_NAME}"
            )
            count = cursor.fetchone()[0]
            print(f"✅ STOCK_INFO 更新完成，資料庫中有 {count} 筆資料")
            conn.close()

            print("\n🔄 測試 update(data_type=FinMindDataType.BROKER_INFO)...")
            updater.update(data_type=FinMindDataType.BROKER_INFO)

            conn = sqlite3.connect(temp_db_path)
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT COUNT(*) FROM {SECURITIES_TRADER_INFO_TABLE_NAME}"
            )
            count = cursor.fetchone()[0]
            print(f"✅ BROKER_INFO 更新完成，資料庫中有 {count} 筆資料")
            conn.close()

            print(
                "\n🔄 測試 update(data_type=FinMindDataType.BROKER_TRADING)..."
            )
            updater.update(
                data_type=FinMindDataType.BROKER_TRADING,
                start_date=start_date,
                end_date=end_date,
            )

            conn = sqlite3.connect(temp_db_path)
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT COUNT(*) FROM {STOCK_TRADING_DAILY_REPORT_TABLE_NAME}"
            )
            count = cursor.fetchone()[0]
            print(
                f"✅ BROKER_TRADING 更新完成，資料庫中有 {count} 筆資料"
            )
            conn.close()

            # ===== 測試 5: update() 方法 - 使用字串 =====
            print(f"\n{'='*60}")
            print("測試 5: update() 方法 - 使用字串參數")
            print(f"{'='*60}")

            print("\n🔄 測試 update(data_type='stock_info')...")
            updater.update(data_type="stock_info")

            conn = sqlite3.connect(temp_db_path)
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT COUNT(*) FROM {STOCK_INFO_WITH_WARRANT_TABLE_NAME}"
            )
            count = cursor.fetchone()[0]
            print(f"✅ 'stock_info' 更新完成，資料庫中有 {count} 筆資料")
            conn.close()

            print("\n🔄 測試 update(data_type='BROKER_INFO')...")
            updater.update(data_type="BROKER_INFO")

            conn = sqlite3.connect(temp_db_path)
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT COUNT(*) FROM {SECURITIES_TRADER_INFO_TABLE_NAME}"
            )
            count = cursor.fetchone()[0]
            print(f"✅ 'BROKER_INFO' 更新完成，資料庫中有 {count} 筆資料")
            conn.close()

            # ===== 測試 6: update_all() =====
            print(f"\n{'='*60}")
            print("測試 6: update_all()")
            print(f"{'='*60}")

            print("\n🔄 執行 update_all()...")
            updater.update_all(
                start_date=start_date,
                end_date=end_date,
            )

            # 驗證所有資料表
            conn = sqlite3.connect(temp_db_path)
            cursor = conn.cursor()

            tables: List[str] = [
                STOCK_INFO_WITH_WARRANT_TABLE_NAME,
                SECURITIES_TRADER_INFO_TABLE_NAME,
                STOCK_TRADING_DAILY_REPORT_TABLE_NAME,
            ]

            print("\n📊 最終資料統計:")
            all_success: bool = True
            for table_name in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                status: str = "✅" if count > 0 else "⚠️"
                print(f"{status} {table_name}: {count} 筆資料")
                if count == 0 and table_name != STOCK_TRADING_DAILY_REPORT_TABLE_NAME:
                    # 交易報表可能為空是正常的
                    all_success = False

            conn.close()

            # ===== 測試 7: get_actual_update_start_date =====
            print(f"\n{'='*60}")
            print("測試 7: get_actual_update_start_date()")
            print(f"{'='*60}")

            # 測試從資料庫取得最新日期
            default_date = datetime.date(2021, 6, 30)
            actual_start_date = updater.get_actual_update_start_date(
                default_date=default_date
            )

            print(f"預設日期: {default_date}")
            print(f"實際起始日期: {actual_start_date}")
            print(f"類型: {type(actual_start_date)}")

            # 測試字串格式
            default_date_str = "2021-06-30"
            actual_start_date_str = updater.get_actual_update_start_date(
                default_date=default_date_str
            )

            print(f"\n預設日期（字串）: {default_date_str}")
            print(f"實際起始日期（字串）: {actual_start_date_str}")
            print(f"類型: {type(actual_start_date_str)}")

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
        # Path(temp_db_path).unlink(missing_ok=True)
        pass


if __name__ == "__main__":
    # 設定 logger
    logger.remove()  # 移除預設的 logger
    logger.add(lambda msg: print(msg, end=""), format="{message}")

    # 執行測試
    success: bool = test_finmind_updater()

    if success:
        print("\n🎉 測試完成！")
    else:
        print("\n⚠️  測試未完全成功，請檢查上述輸出")
