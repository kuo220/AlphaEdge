"""
測試 MonthlyRevenueReportLoader 的 merge 邏輯
使用臨時資料庫和臨時目錄，不會影響實際的 .db 檔案
"""

import sqlite3
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from loguru import logger

from trader.pipeline.loaders.monthly_revenue_report_loader import MonthlyRevenueReportLoader
from trader.config import MONTHLY_REVENUE_TABLE_NAME


def create_test_csv(file_path: Path, data: list) -> None:
    """創建測試用的 CSV 檔案"""
    df = pd.DataFrame(data)
    # 確保 stock_id 是字串型別，避免 merge 時的型別不一致問題
    if 'stock_id' in df.columns:
        df['stock_id'] = df['stock_id'].astype(str)
    df.to_csv(file_path, index=False, encoding='utf-8-sig')


def test_merge_logic():
    """測試 merge 邏輯是否正確"""
    
    # 創建臨時目錄
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # 創建臨時資料庫
        test_db_path = temp_path / "test_data.db"
        test_downloads_dir = temp_path / "test_downloads"
        test_meta_dir = temp_path / "test_meta"
        test_downloads_dir.mkdir(parents=True, exist_ok=True)
        test_meta_dir.mkdir(parents=True, exist_ok=True)
        
        # 創建 cleaned_columns.json
        # 注意：檔案名稱應該是 monthly_revenue_report_cleaned_columns.json
        # 因為 DataType.MRR.lower() 會變成 "monthly_revenue_report"
        cleaned_cols = [
            "year", "month", "stock_id", "公司名稱",
            "當月營收", "上月營收", "去年當月營收",
            "上月比較增減(%)", "去年同月增減(%)",
            "當月累計營收", "去年累計營收", "前期比較增減(%)"
        ]
        import json
        cleaned_cols_file = test_meta_dir / "monthly_revenue_report_cleaned_columns.json"
        with open(cleaned_cols_file, "w", encoding="utf-8") as f:
            json.dump(cleaned_cols, f, ensure_ascii=False, indent=2)
        
        # 準備測試資料
        # 第一筆 CSV：包含 3 筆記錄
        # 注意：確保 stock_id 是字串型別，避免 merge 時的型別不一致問題
        test_data_1 = [
            {
                "year": 2025,
                "month": 7,
                "stock_id": "1101",  # 確保是字串
                "公司名稱": "台泥",
                "當月營收": 13535929,
                "上月營收": 10107877,
                "去年當月營收": 14429687,
                "上月比較增減(%)": 33.91,
                "去年同月增減(%)": -6.19,
                "當月累計營收": 83916845,
                "去年累計營收": 79261662,
                "前期比較增減(%)": 5.87
            },
            {
                "year": 2025,
                "month": 7,
                "stock_id": "1102",  # 確保是字串
                "公司名稱": "亞泥",
                "當月營收": 5836590,
                "上月營收": 6019299,
                "去年當月營收": 6722518,
                "上月比較增減(%)": -3.03,
                "去年同月增減(%)": -13.17,
                "當月累計營收": 41097034,
                "去年累計營收": 42207123,
                "前期比較增減(%)": -2.63
            },
            {
                "year": 2025,
                "month": 7,
                "stock_id": "1103",  # 確保是字串
                "公司名稱": "嘉泥",
                "當月營收": 251867,
                "上月營收": 247791,
                "去年當月營收": 258383,
                "上月比較增減(%)": 1.64,
                "去年同月增減(%)": -2.52,
                "當月累計營收": 1772889,
                "去年累計營收": 1695827,
                "前期比較增減(%)": 4.54
            }
        ]
        
        # 第二筆 CSV：包含 1 筆重複記錄 + 1 筆新記錄
        test_data_2 = [
            {
                "year": 2025,
                "month": 7,
                "stock_id": "1101",  # 重複記錄（確保是字串）
                "公司名稱": "台泥",
                "當月營收": 13535929,
                "上月營收": 10107877,
                "去年當月營收": 14429687,
                "上月比較增減(%)": 33.91,
                "去年同月增減(%)": -6.19,
                "當月累計營收": 83916845,
                "去年累計營收": 79261662,
                "前期比較增減(%)": 5.87
            },
            {
                "year": 2025,
                "month": 7,
                "stock_id": "1104",  # 新記錄（確保是字串）
                "公司名稱": "環泥",
                "當月營收": 575078,
                "上月營收": 627049,
                "去年當月營收": 621001,
                "上月比較增減(%)": -8.28,
                "去年同月增減(%)": -7.39,
                "當月累計營收": 4472556,
                "去年累計營收": 4621653,
                "前期比較增減(%)": -3.22
            }
        ]
        
        # 創建測試 CSV 檔案
        csv_file_1 = test_downloads_dir / "monthly_revenue_report_2025_7_batch1.csv"
        csv_file_2 = test_downloads_dir / "monthly_revenue_report_2025_7_batch2.csv"
        create_test_csv(csv_file_1, test_data_1)
        create_test_csv(csv_file_2, test_data_2)
        
        logger.info("=" * 60)
        logger.info("開始測試 MonthlyRevenueReportLoader 的 merge 邏輯")
        logger.info("=" * 60)
        
        # 使用 patch 來替換配置路徑（需要在 loader 初始化前 patch）
        import trader.config as config_module
        original_db_path = config_module.DB_PATH
        original_downloads_path = config_module.MONTHLY_REVENUE_REPORT_DOWNLOADS_PATH
        original_meta_path = config_module.MONTHLY_REVENUE_REPORT_META_DIR_PATH
        
        try:
            # 替換配置
            config_module.DB_PATH = test_db_path
            config_module.MONTHLY_REVENUE_REPORT_DOWNLOADS_PATH = test_downloads_dir
            config_module.MONTHLY_REVENUE_REPORT_META_DIR_PATH = test_meta_dir
            
            # 重新導入 loader 模組以使用新的配置
            import importlib
            import trader.pipeline.loaders.monthly_revenue_report_loader as loader_module
            importlib.reload(loader_module)
            
            # 創建 Loader 實例
            loader = loader_module.MonthlyRevenueReportLoader()
            
            # 確保 loader 使用臨時目錄
            loader.mrr_dir = test_downloads_dir
            loader.monthly_revenue_report_cleaned_cols_path = test_meta_dir / "monthly_revenue_report_cleaned_columns.json"
            
            # 第一次執行：只處理第一個 CSV 檔案（3 筆記錄）
            logger.info("\n[測試 1] 插入第一批資料（3 筆記錄）")
            # 暫時移除第二個 CSV 檔案
            csv_file_2_temp = test_downloads_dir / "monthly_revenue_report_2025_7_batch2.csv.tmp"
            if csv_file_2.exists():
                csv_file_2.rename(csv_file_2_temp)
            
            loader.add_to_db(remove_files=False)
            
            # 檢查資料庫中的記錄數
            conn = sqlite3.connect(test_db_path)
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {MONTHLY_REVENUE_TABLE_NAME}")
            count_after_first = cursor.fetchone()[0]
            logger.info(f"資料庫中的記錄數：{count_after_first}")
            assert count_after_first == 3, f"預期 3 筆記錄，實際 {count_after_first} 筆"
            
            # 檢查具體記錄
            cursor.execute(f"SELECT year, month, stock_id, 公司名稱 FROM {MONTHLY_REVENUE_TABLE_NAME}")
            records = cursor.fetchall()
            logger.info(f"資料庫中的記錄：{records}")
            expected_records = [(2025, 7, '1101', '台泥'), (2025, 7, '1102', '亞泥'), (2025, 7, '1103', '嘉泥')]
            assert set(records) == set(expected_records), f"記錄不匹配"
            
            conn.close()
            logger.info("✓ 第一批資料插入成功")
            
            # 恢復第二個 CSV 檔案
            if csv_file_2_temp.exists():
                csv_file_2_temp.rename(csv_file_2)
            
            # 第二次執行：插入第二批資料（1 筆重複 + 1 筆新記錄）
            logger.info("\n[測試 2] 插入第二批資料（1 筆重複 + 1 筆新記錄）")
            loader.add_to_db(remove_files=False)
            
            # 檢查資料庫中的記錄數
            conn = sqlite3.connect(test_db_path)
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {MONTHLY_REVENUE_TABLE_NAME}")
            count_after_second = cursor.fetchone()[0]
            logger.info(f"資料庫中的記錄數：{count_after_second}")
            assert count_after_second == 4, f"預期 4 筆記錄（3 + 1 新記錄），實際 {count_after_second} 筆"
            
            # 檢查具體記錄
            cursor.execute(f"SELECT year, month, stock_id, 公司名稱 FROM {MONTHLY_REVENUE_TABLE_NAME} ORDER BY stock_id")
            records = cursor.fetchall()
            logger.info(f"資料庫中的記錄：{records}")
            expected_records = [
                (2025, 7, '1101', '台泥'),
                (2025, 7, '1102', '亞泥'),
                (2025, 7, '1103', '嘉泥'),
                (2025, 7, '1104', '環泥')
            ]
            assert set(records) == set(expected_records), f"記錄不匹配"
            
            # 檢查是否有重複的 1101
            cursor.execute(f"SELECT COUNT(*) FROM {MONTHLY_REVENUE_TABLE_NAME} WHERE stock_id = '1101'")
            count_1101 = cursor.fetchone()[0]
            assert count_1101 == 1, f"預期只有 1 筆 1101 記錄，實際 {count_1101} 筆"
            
            conn.close()
            logger.info("✓ 第二批資料插入成功，重複記錄已正確過濾")
            
            # 第三次執行：再次插入相同的資料（應該全部被過濾）
            logger.info("\n[測試 3] 再次插入相同的資料（應該全部被過濾）")
            loader.add_to_db(remove_files=False)
            
            # 檢查資料庫中的記錄數
            conn = sqlite3.connect(test_db_path)
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {MONTHLY_REVENUE_TABLE_NAME}")
            count_after_third = cursor.fetchone()[0]
            logger.info(f"資料庫中的記錄數：{count_after_third}")
            assert count_after_third == 4, f"預期仍為 4 筆記錄，實際 {count_after_third} 筆"
            
            conn.close()
            logger.info("✓ 重複資料已正確過濾，沒有新增記錄")
            
        finally:
            # 還原原始配置
            config_module.DB_PATH = original_db_path
            config_module.MONTHLY_REVENUE_REPORT_DOWNLOADS_PATH = original_downloads_path
            config_module.MONTHLY_REVENUE_REPORT_META_DIR_PATH = original_meta_path
        
        logger.info("\n" + "=" * 60)
        logger.info("✓ 所有測試通過！merge 邏輯運作正常")
        logger.info("=" * 60)


if __name__ == "__main__":
    try:
        test_merge_logic()
    except Exception as e:
        logger.error(f"測試失敗：{e}")
        import traceback
        traceback.print_exc()
        raise

