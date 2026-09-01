import datetime
import os
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

# 從 .env 載入環境變數
load_dotenv()


def get_static_resolved_path(base_dir: Path, dir_name: str) -> Path:
    """Resolve dir_name under base_dir to an absolute path"""
    return (base_dir / dir_name).resolve()


# -----------------------------------------------------------------------
# Root Directory (core/) Path
# -----------------------------------------------------------------------
#
BASE_DIR_PATH: Path = Path(__file__).resolve().parent


# -----------------------------------------------------------------------
# === General Directory Path ===
# -----------------------------------------------------------------------
#
DATABASE_DIR_PATH: Path = get_static_resolved_path(
    base_dir=BASE_DIR_PATH, dir_name="database"
)
# 目錄**不在此建立**：import 一個設定模組不應該有檔案系統副作用，
# 否則任何只是要讀常數的測試都會被動生出 core/logs/。
# 實際要寫檔時由 `LogManager.setup_logger()` 惰性建立（見 log_manager.py）
LOGS_DIR_PATH: Path = get_static_resolved_path(base_dir=BASE_DIR_PATH, dir_name="logs")
DATA_DIR_PATH: Path = get_static_resolved_path(base_dir=BASE_DIR_PATH, dir_name="data")


# -----------------------------------------------------------------------
# === Strategy Directory Path ===
# -----------------------------------------------------------------------
#
STOCK_STRATEGY_DIR_PATH: Path = get_static_resolved_path(
    base_dir=BASE_DIR_PATH, dir_name="strategies/stock"
)


# -----------------------------------------------------------------------
# === Backtest Result Directory Path ===
# -----------------------------------------------------------------------
#
BACKTEST_RESULT_DIR_PATH: Path = get_static_resolved_path(
    base_dir=BASE_DIR_PATH, dir_name="backtest/results"
)
BACKTEST_LOGS_DIR_PATH: Path = get_static_resolved_path(
    base_dir=BASE_DIR_PATH, dir_name="backtest/results/logs"
)

# -----------------------------------------------------------------------
# === Crawl Data Downloads Path ===
# -----------------------------------------------------------------------
#
PIPELINE_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=BASE_DIR_PATH, dir_name="pipeline/downloads"
)

# 中繼檔依「市場」分層，與 core/database/ 的 tw_stock.db／tw_futures.db 同一個維度。
# 程式碼（pipeline / api / adapters）維持命名平行不分目錄——兩者搬遷成本差一個量級，
# 決策理由見 docs/futures/tw-futures-platform.md §3.0
TW_STOCK_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=PIPELINE_DOWNLOADS_PATH, dir_name="tw_stock"
)
TW_FUTURES_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=PIPELINE_DOWNLOADS_PATH, dir_name="tw_futures"
)
FINANCIAL_STATEMENT_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=TW_STOCK_DOWNLOADS_PATH, dir_name="financial_statement"
)
MONTHLY_REVENUE_REPORT_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=TW_STOCK_DOWNLOADS_PATH, dir_name="monthly_revenue_report"
)
PRICE_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=TW_STOCK_DOWNLOADS_PATH, dir_name="price"
)
CHIP_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=TW_STOCK_DOWNLOADS_PATH, dir_name="chip"
)
MARGIN_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=TW_STOCK_DOWNLOADS_PATH, dir_name="margin"
)
DIVIDEND_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=TW_STOCK_DOWNLOADS_PATH, dir_name="dividend"
)
TICK_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=TW_STOCK_DOWNLOADS_PATH, dir_name="tick"
)
FINMIND_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=TW_STOCK_DOWNLOADS_PATH, dir_name="finmind"
)

# 台期貨中繼檔；目錄與 tw_stock 同構，只是資料類型不同
FUTURES_PRICE_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=TW_FUTURES_DOWNLOADS_PATH, dir_name="price"
)
FUTURES_CHIP_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=TW_FUTURES_DOWNLOADS_PATH, dir_name="chip"
)
FUTURES_CONTINUOUS_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=TW_FUTURES_DOWNLOADS_PATH, dir_name="continuous"
)
FUTURES_UNIVERSE_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=TW_FUTURES_DOWNLOADS_PATH, dir_name="universe"
)
FUTURES_TICK_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=TW_FUTURES_DOWNLOADS_PATH, dir_name="tick"
)
FUTURES_MARGIN_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=TW_FUTURES_DOWNLOADS_PATH, dir_name="margin"
)

# -----------------------------------------------------------------------
# === Crawler Downloads Metadata Directory Path ===
# -----------------------------------------------------------------------
#
DOWNLOADS_METADATA_DIR_PATH: Path = get_static_resolved_path(
    base_dir=TW_STOCK_DOWNLOADS_PATH, dir_name="meta"
)
FINANCIAL_STATEMENT_META_DIR_PATH: Path = get_static_resolved_path(
    base_dir=DOWNLOADS_METADATA_DIR_PATH, dir_name="financial_statement"
)
MONTHLY_REVENUE_REPORT_META_DIR_PATH: Path = get_static_resolved_path(
    base_dir=DOWNLOADS_METADATA_DIR_PATH, dir_name="monthly_revenue_report"
)
TICK_METADATA_DIR_PATH: Path = get_static_resolved_path(
    base_dir=DOWNLOADS_METADATA_DIR_PATH, dir_name="tick"
)
TICK_METADATA_PATH: Path = get_static_resolved_path(
    base_dir=TICK_METADATA_DIR_PATH, dir_name="tick_metadata.json"
)
BROKER_TRADING_METADATA_DIR_PATH: Path = get_static_resolved_path(
    base_dir=DOWNLOADS_METADATA_DIR_PATH, dir_name="broker_trading"
)
FUTURES_METADATA_DIR_PATH: Path = get_static_resolved_path(
    base_dir=TW_FUTURES_DOWNLOADS_PATH, dir_name="meta"
)
BROKER_TRADING_METADATA_PATH: Path = get_static_resolved_path(
    base_dir=BROKER_TRADING_METADATA_DIR_PATH, dir_name="broker_trading_metadata.json"
)

# -----------------------------------------------------------------------
# === Reference Data Directory Path ===
# -----------------------------------------------------------------------
# 股票相關參考資料表存放目錄
STOCK_INFO_DIR_PATH: Path = get_static_resolved_path(
    base_dir=DATA_DIR_PATH, dir_name="stock_info"
)

# 股票列表參考資料（上市、上櫃、興櫃的股票、權證名稱、代碼和產業類別）
STOCK_LIST_JSON_PATH: Path = get_static_resolved_path(
    base_dir=STOCK_INFO_DIR_PATH, dir_name="taiwan_stock_list.json"
)
STOCK_LIST_CSV_PATH: Path = get_static_resolved_path(
    base_dir=STOCK_INFO_DIR_PATH, dir_name="taiwan_stock_list.csv"
)

# 證券商資訊參考資料（用於台股分點資料表，使用券商代碼查詢特定券商所有股票進出）
BROKER_INFO_CSV_PATH: Path = get_static_resolved_path(
    base_dir=STOCK_INFO_DIR_PATH, dir_name="taiwan_securities_trader_info.csv"
)


# -----------------------------------------------------------------------
# === Database Files Full Paths ===
# -----------------------------------------------------------------------
# 常數名與檔名皆帶市場軸（TW_）：`core/database/` 是按市場分庫，
# 美股進來時會是 us_stock.db，泛用的檔名（stock.db）會失去指向
TW_STOCK_DB_NAME: str = "tw_stock.db"
TICK_DB_NAME: str = "tickDB"

TW_STOCK_DB_PATH: Path = get_static_resolved_path(
    base_dir=DATABASE_DIR_PATH, dir_name=TW_STOCK_DB_NAME
)
TICK_DB_PATH: str = f"{os.getenv('DDB_PATH')}{TICK_DB_NAME}"

# 期貨與股票分庫：合約碼（contract_id）與 stock_id 語意不同，混在同一個 DB
# 會讓「這張表的主鍵到底是什麼」失去單一答案
TW_FUTURES_DB_NAME: str = "tw_futures.db"

TW_FUTURES_DB_PATH: Path = get_static_resolved_path(
    base_dir=DATABASE_DIR_PATH, dir_name=TW_FUTURES_DB_NAME
)


# -----------------------------------------------------------------------
# === Database Table names ===
# -----------------------------------------------------------------------
#
PRICE_TABLE_NAME: str = "price"
CHIP_TABLE_NAME: str = "chip"
MARGIN_TABLE_NAME: str = "margin"
DIVIDEND_TABLE_NAME: str = "dividend"
TICK_TABLE_NAME: str = "tick"
# 期貨 tick **與股票分表**（Phase5-1）：主鍵不同（期貨要 product ＋ expiry ＋
# session 才能定位一筆成交，股票只要 stock_id），且期貨有夜盤。
# 兩者塞同一張表會讓分割鍵（partition key）失去意義，查詢一律掃全表
FUTURES_TICK_TABLE_NAME: str = "futures_tick"
MONTHLY_REVENUE_TABLE_NAME: str = "monthly_revenue"
BALANCE_SHEET_TABLE_NAME: str = "balance_sheet"
COMPREHENSIVE_INCOME_TABLE_NAME: str = "comprehensive_income"
CASH_FLOW_TABLE_NAME: str = "cash_flow"
EQUITY_CHANGE_TABLE_NAME: str = "equity_change"
STOCK_INFO_TABLE_NAME: str = "taiwan_stock_info"
STOCK_INFO_WITH_WARRANT_TABLE_NAME: str = "taiwan_stock_info_with_warrant"
SECURITIES_TRADER_INFO_TABLE_NAME: str = "taiwan_securities_trader_info"
# 台期貨（皆位於 tw_futures.db）
FUTURES_CONTRACT_TABLE_NAME: str = "futures_contract"  # 合約／商品規格
FUTURES_PRICE_DAILY_TABLE_NAME: str = "futures_price_daily"  # 各月份合約日 K
FUTURES_CONTINUOUS_TABLE_NAME: str = "futures_continuous"  # 連續合約（換月接續後）
FUTURES_INSTITUTIONAL_CHIP_TABLE_NAME: str = (
    "futures_institutional_chip"  # 三大法人（逐商品、逐身份別）
)
# 大額交易人與 PCR **各自成表**，不與三大法人共用：三者的主鍵不同
# （前者多了到期月份與交易人類別、PCR 一天只有一列），塞同一張表會讓多數欄位
# 永遠是 NULL，且下游得先判斷「這是哪一種籌碼」才知道該讀哪組欄位
FUTURES_LARGE_TRADER_TABLE_NAME: str = "futures_large_trader"  # 大額交易人
FUTURES_PUT_CALL_RATIO_TABLE_NAME: str = "futures_put_call_ratio"  # 選擇權 PCR
# 保證金**分兩張表**：指數類等商品給的是「每口固定金額」，股票期貨給的是
# 「適用比例 ＋ 級距」（每檔標的股價不同，固定金額沒有意義）。硬塞同一張表會讓
# 一半欄位永遠是 NULL，且下游得先判斷「這是哪一類」才知道讀哪一組欄位。
# 規劃見 `backlog/台期貨保證金ETL.md`
FUTURES_MARGIN_HISTORY_TABLE_NAME: str = (
    "futures_margin_history"  # 保證金歷史序列（每口金額）
)
STOCK_FUTURES_MARGIN_RATE_HISTORY_TABLE_NAME: str = (
    "stock_futures_margin_rate_history"  # 股票期貨保證金歷史序列（適用比例）
)
FUTURES_STOCK_UNIVERSE_TABLE_NAME: str = "futures_stock_universe"  # 股票期貨標的池

STOCK_TRADING_DAILY_REPORT_TABLE_NAME: str = (
    "taiwan_stock_trading_daily_report_secid_agg"
)


# -----------------------------------------------------------------------
# === 台期貨爬取範圍 ===
# -----------------------------------------------------------------------
#
# 「有哪些商品」定義在 `core/utils/constant.py` 的 `FuturesProduct`；
# 「這次要抓哪些」則是本清單——兩者刻意分開，否則想暫時只跑一檔就得改 Enum。
#
# **此處刻意寫字面值而不 import `FuturesProduct`**：`core.config` 是最底層模組，
# 而 `core.utils` 反過來相依它（`core/utils/account.py` → `core.config`），
# import 進來會造成循環。值本身是 TAIFEX 的外部代碼、不會改名，風險低；
# 拼錯的防呆由 `FuturesPriceCrawler.validate_product()` 在送出請求前比對
# `FuturesProduct` 擋下，並有 `test_configured_targets_are_all_valid` 釘住本清單。
#
# **每加一檔的成本是乘出來的**：這個來源一次只能查一個商品，且日盤與夜盤要分開查，
# 故請求數 = 商品數 × 2 × 交易日數（以 2013 年起算約 3,300 日 → 每檔約 6,600 次）。
# 目前 1 檔 ≈ 13,800 次請求（1998-07 起算約 6,900 個交易日）。
#
# **先跑通單檔再擴充**：TX 於 2026-08-29 驗證無誤，其餘六檔於 2026-09-02
# （Phase4-1）逐一實測可爬可清可入庫後加入，**crawler／updater 一行都沒改**
# ——商品代碼本來就是查詢參數，這正是當初分層的目的。
#
# ⚠️ **加入本清單不等於資料已回補**：`--target futures_price` 會逐一補齊，
# 六檔的歷史回補約需 40 小時（見 Phase4-1 完成紀錄）。要確認某商品補到哪一天，
# 查 `SELECT product, MIN(date), MAX(date), COUNT(*) FROM futures_price_daily GROUP BY product`。
#
# 收錄門檻：**契約乘數已查證**。乘數未登錄的商品即使爬回來也算不出 PnL，
# 會拖到回測階段才 KeyError，不如一開始就不收。
FUTURES_TARGET_PRODUCTS: List[str] = [
    "TX",  # 臺股期貨（大台）    乘數 200
    "MTX",  # 小型臺指           乘數 50
    "TMF",  # 微型臺指           乘數 10
    "TE",  # 電子期貨            乘數 4000
    "ZEF",  # 小型電子期貨       乘數 500
    "TF",  # 金融期貨            乘數 1000
    "ZFF",  # 小型金融期貨       乘數 250
]


# -----------------------------------------------------------------------
# === Default dates for update_db / pipeline（資料更新預設區間）===
# -----------------------------------------------------------------------
#
DEFAULT_CHIP_START_DATE: datetime.date = datetime.date(2013, 1, 1)
DEFAULT_MARGIN_START_DATE: datetime.date = datetime.date(2013, 1, 1)
DEFAULT_DIVIDEND_START_DATE: datetime.date = datetime.date(2013, 1, 1)
DEFAULT_PRICE_START_DATE: datetime.date = datetime.date(2013, 1, 1)

# 台期貨回補起點（2026-08-29 由使用者決定）。
#
# **來源能給的更早**：TX 臺股期貨可回溯到 1998-07-21（其上市日，逐日實測確認
# 07/20 無資料、07/21 起有），亦即 TAIFEX 提供完整歷史、沒有截斷。
# 此處取 2015-01-01 是**刻意收窄**，不是資料限制。
#
# 要改回更早的起點，改這一行即可——**已入庫的資料不受影響**（loader 走
# INSERT OR IGNORE），續跑會從表內該商品的最新日接續，
# 故往前擴張需要另行指定區間重跑，見 `FuturesPriceUpdater.update()`。
DEFAULT_FUTURES_START_DATE: datetime.date = datetime.date(2015, 1, 1)

# 股票期貨預設只爬**流動性前 N 檔**（Phase6-2）。
#
# **不要一次爬 320 檔**：那是每天 640 次請求（日夜盤各一），13 年的回補要好幾個月。
# 股期的流動性差距是數量級的——前段幾檔佔了絕大多數成交量，尾端有整批一天只成交
# 個位數口的商品，把它們納入回測只會製造「回測賺錢、實際掛不到單」的假訊號。
#
# 排序依據是**已入庫行情的平均日成交量**，故第一次跑（表內還沒有股期行情）會排不出
# 來而退回整份清單並提醒——那是雞生蛋，不是錯誤。
STOCK_FUTURES_TOP_N: int = 20
DEFAULT_START_YEAR: int = 2013
DEFAULT_END_MONTH: int = 12
TICK_UPDATE_START_DATE: datetime.date = datetime.date(2024, 5, 10)
FINMIND_BROKER_TRADING_START_DATE: datetime.date = datetime.date(2021, 6, 30)
# 結束日不設常數：與 chip／margin／dividend／price 一致，由呼叫端取 today()


# -----------------------------------------------------------------------
# === DolphinDB server setting ===
# -----------------------------------------------------------------------
#
def get_int_env(name: str, default: int = 0) -> int:
    """
    讀取整數型環境變數；無法轉型時退回預設值

    原本是 `int(os.getenv("DDB_PORT") or "0")`：環境變數被設成任何非數字字串
    （含誤植的空白或註解）都會在 **import 期**拋 ValueError，
    而這個模組被全專案 import，等於整個程式無法啟動且錯誤訊息與設定無關。
    """

    raw: Optional[str] = os.getenv(name)
    if not raw:
        return default

    try:
        return int(raw)
    except ValueError:
        return default


DDB_PATH: str | None = os.getenv("DDB_PATH")
DDB_HOST: str | None = os.getenv("DDB_HOST")
DDB_PORT: int = get_int_env("DDB_PORT")
DDB_USER: str | None = os.getenv("DDB_USER")
DDB_PASSWORD: str | None = os.getenv("DDB_PASSWORD")


# -----------------------------------------------------------------------
# === Shioaji API ===
# -----------------------------------------------------------------------
#
API_KEY: str | None = os.getenv("API_KEY")
API_SECRET_KEY: str | None = os.getenv("API_SECRET_KEY")

# -----------------------------------------------------------------------
# === API list for crawling tick data ===
# -----------------------------------------------------------------------
#
NUM_API: int = 4
API_KEYS: List[Optional[str]] = [os.getenv(f"API_KEY_{i + 1}") for i in range(NUM_API)]
API_SECRET_KEYS: List[Optional[str]] = [
    os.getenv(f"API_SECRET_KEY_{i + 1}") for i in range(NUM_API)
]
