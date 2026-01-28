"""
將 broker_trading 中的資料存入 data.db

使用方法（從專案根目錄執行）：
    python -m tasks.load_broker_trading_to_db

說明：
    此腳本會讀取 pipeline/downloads/finmind/broker_trading/ 目錄下的所有 CSV 檔案，
    並將資料存入 data.db 資料庫中的 taiwan_stock_trading_daily_report_secid_agg 資料表。

    檔案結構應為：
        broker_trading/
            {broker_id}/
                {stock_id}.csv

    此腳本會自動：
    - 檢查資料庫連線
    - 確保資料表存在
    - 過濾重複資料（根據 stock_id, date, securities_trader_id 複合主鍵）
    - 只插入新資料
"""

from loguru import logger

from trader.pipeline.loaders.finmind_loader import FinMindLoader


def main() -> None:
    """將 broker_trading 資料載入到 data.db"""
    logger.info("開始載入 broker_trading 資料到 data.db...")

    loader: FinMindLoader | None = None

    try:
        # 初始化 FinMindLoader
        loader = FinMindLoader()

        # 載入 broker_trading 資料（從 CSV 檔案）
        # 如果不傳入 df 參數，會自動從 pipeline/downloads/finmind/broker_trading/ 讀取
        loader.load_broker_trading_daily_report()

        logger.info("✅ broker_trading 資料載入完成")

    except Exception as e:
        logger.error(f"❌ 載入 broker_trading 資料時發生錯誤: {e}", exc_info=True)
        raise

    finally:
        # 確保資料庫連線關閉
        if loader is not None:
            loader.disconnect()


if __name__ == "__main__":
    main()
