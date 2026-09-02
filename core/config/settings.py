import datetime
import os
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()

"""
爬取範圍、預設區間與外部服務設定

與 `paths`／`schema` 的差別：這裡的每一個值都是**可調的營運參數**
（要抓哪些商品、從哪一年開始、連哪一台 DolphinDB），
不是系統的結構。改這裡不會動到任何路徑或資料表定義。
"""


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
