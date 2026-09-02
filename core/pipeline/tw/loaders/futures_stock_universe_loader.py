import sqlite3
from pathlib import Path
from typing import List, Optional, Set

import pandas as pd
from loguru import logger

from core.config import (
    FUTURES_STOCK_UNIVERSE_TABLE_NAME,
    FUTURES_UNIVERSE_DOWNLOADS_PATH,
    TW_FUTURES_DB_PATH,
)
from core.pipeline.shared.base_loader import BaseDataLoader
from core.pipeline.utils.sqlite_utils import SQLiteUtils

"""
Futures Stock Universe Loader

**這張表是「快照序列」，不是「現況表」**——每次執行都新增一整份當日快照，
不覆蓋也不刪除舊的。理由是來源（TAIFEX 標的一覽表）只給當下有哪些商品，
沒有掛牌日與下市日；唯一能得到這兩個日期的方式就是留下每次看到的樣子再差分：

- 掛牌日 ≈ `MIN(snapshot_date)`（該商品第一次出現的快照日）
- 下市   ≈ 該商品的 `MAX(snapshot_date)` 早於全表最新快照日
- 契約單位異動 ≈ 同一 `product_id` 的 `contract_size` 在快照之間改變

⚠️ **這三者都是「觀測值」而非官方日期**：本表建立之前就已掛牌的商品，
其 `MIN(snapshot_date)` 只會是本表的第一天，不是真正的掛牌日。要精確的掛牌／
下市日必須另抓 TAIFEX 契約調整與商品異動公告（Phase6-2）。

每份快照約 320 列，即使每日執行，一年也只有約 8 萬列，不需要為了省空間改成
覆蓋式現況表——那會讓上面三個問題全部無解。
"""


class FuturesStockUniverseLoader(BaseDataLoader):
    """Futures Stock Universe Loader"""

    def __init__(self):
        super().__init__()

        # SQLite Connection（指向 tw_futures.db）
        self.conn: Optional[sqlite3.Connection] = None

        # Downloads directory Path
        self.universe_dir: Path = FUTURES_UNIVERSE_DOWNLOADS_PATH

        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Loader"""

        self.connect()

        # Ensure Database Table Exists
        self.create_missing_tables()

        self.universe_dir.mkdir(parents=True, exist_ok=True)

    def connect(self) -> None:
        """Connect to the Database"""

        if self.conn is None:
            # 期貨與股票分庫，故不是 TW_STOCK_DB_PATH
            TW_FUTURES_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            self.conn: sqlite3.Connection = sqlite3.connect(TW_FUTURES_DB_PATH)

    def disconnect(self) -> None:
        """Disconnect the Database"""

        if self.conn:
            self.conn.close()
            self.conn: Optional[sqlite3.Connection] = None

    def create_db(self) -> None:
        """創建股票期貨標的池 db"""

        cursor: sqlite3.Cursor = self.conn.cursor()

        # 主鍵為 (snapshot_date, product_id)：本表是快照序列，見本檔開頭說明。
        #
        # `underlying_stock_id` 為 TEXT 且不可改成整數：ETF 標的有 `0050`
        # （前導 0）與 `00679B`（含英文字母），轉成數字就對不回 tw_stock.db。
        #
        # `contract_size` 是**掛牌時的標準契約單位，不是契約乘數**。標的除權息後
        # TAIFEX 會調整乘數或另掛新契約（代碼帶數字尾碼，如 `EE1`），實際乘數會
        # 偏離本欄。算 PnL 前必須先接上 Phase6-2 的乘數歷史，不可直接拿本欄當乘數。
        #
        # 兩個交易時段欄位允許 NULL：`-` 代表沒有該時段，2026-08-29 實查僅 6 檔
        # 有盤後交易時段。填空字串會讓「沒有夜盤」與「未知」混為一談。
        create_table_query: str = f"""
        CREATE TABLE IF NOT EXISTS {FUTURES_STOCK_UNIVERSE_TABLE_NAME}(
            "snapshot_date" TEXT NOT NULL,
            "product_id" TEXT NOT NULL,
            "base_code" TEXT NOT NULL,
            "product_type" TEXT NOT NULL,
            "underlying_stock_id" TEXT NOT NULL,
            "underlying_name" TEXT NOT NULL,
            "underlying_listing_board" TEXT,
            "contract_size" INT NOT NULL,
            "day_session_time" TEXT,
            "night_session_time" TEXT,
            PRIMARY KEY ("snapshot_date", "product_id")
        );
        """
        cursor.execute(create_table_query)

        # 下游最常見的查詢是「某商品的快照歷史」（差分出掛牌／下市與乘數異動），
        # 主鍵的前綴是 snapshot_date，幫不上這種查詢，故另建索引
        cursor.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_futures_stock_universe_product
            ON {FUTURES_STOCK_UNIVERSE_TABLE_NAME} ("product_id", "snapshot_date");
            """
        )

        cursor.execute(f"PRAGMA table_info('{FUTURES_STOCK_UNIVERSE_TABLE_NAME}')")
        if cursor.fetchall():
            logger.info(
                f"Table {FUTURES_STOCK_UNIVERSE_TABLE_NAME} create successfully!"
            )
        else:
            logger.warning(
                f"Table {FUTURES_STOCK_UNIVERSE_TABLE_NAME} create unsuccessfully!"
            )

        self.conn.commit()

    def create_missing_tables(self) -> None:
        """確保股票期貨標的池資料表存在"""

        if not SQLiteUtils.check_table_exist(
            conn=self.conn, table_name=FUTURES_STOCK_UNIVERSE_TABLE_NAME
        ):
            self.create_db()

    def add_to_db(
        self,
        remove_files: bool = False,
        only_dates: Optional[Set[str]] = None,
    ) -> None:
        """將資料夾中的所有 CSV 檔存入 tw_futures.db 的股票期貨標的池表"""

        if self.conn is None:
            self.connect()

        self.create_missing_tables()

        file_cnt: int = 0
        failed_files: List[str] = []
        partial_files: List[str] = []
        skipped_cnt: int = 0

        for file_path in self.select_csv_files(self.universe_dir, only_dates):
            try:
                # 商品代碼與證券代號一律當字串：`0050` 的前導 0 會被吃掉，
                # 而 `00679B` 根本不是數字。
                #
                # **`keep_default_na=False` 不可省，且 `dtype=str` 擋不住它**：
                # 穩懋的商品代碼就是 `NA`，落在 pandas 預設的 NA 字面值裡，回讀時
                # 會變成 NaN 而觸發 base_code 的 NOT NULL，再被 `INSERT OR IGNORE`
                # 靜靜吞掉——2026-08-29 實測就是這樣少了 1 檔（319/320），
                # 只有 `finish_load` 的「部分列寫入」警告會提到。
                # 同一個坑在 crawler 解析 HTML 時已經踩過一次，CSV 回讀是第二次。
                #
                # `na_values=[""]` 則是為了保住真正的空值：關掉預設 NA 之後，
                # 沒有夜盤的空欄位會變成空字串而不是 NULL。
                df: pd.DataFrame = pd.read_csv(
                    file_path,
                    dtype={
                        "product_id": str,
                        "base_code": str,
                        "underlying_stock_id": str,
                    },
                    keep_default_na=False,
                    na_values=[""],
                )
                inserted, skipped = self.insert_dataframe(
                    self.conn, FUTURES_STOCK_UNIVERSE_TABLE_NAME, df
                )
                if inserted == 0 and skipped > 0:
                    # 整檔已在資料庫中：同一天重跑必然走到這裡
                    skipped_cnt += 1
                    continue
                if skipped > 0:
                    partial_files.append(str(file_path))
                logger.info(f"Save {file_path} into database")
                file_cnt += 1
            except Exception as e:
                logger.warning(f"Error saving {file_path}: {e}")
                failed_files.append(str(file_path))

        self.conn.commit()
        self.disconnect()

        self.finish_load(
            source="futures_stock_universe",
            succeeded=file_cnt,
            failed_files=failed_files,
            remove_files=remove_files,
            downloads_path=FUTURES_UNIVERSE_DOWNLOADS_PATH,
            skipped_files=skipped_cnt,
            partial_files=partial_files,
        )
