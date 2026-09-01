from enum import Enum


class DataType(str, Enum):
    """資料類型"""

    PRICE = "Price"
    CHIP = "Chip"
    MARGIN = "Margin"  # 信用交易（融資融券餘額）
    DIVIDEND = "Dividend"  # 除權除息計算結果表
    TICK = "Tick"
    MRR = "MONTHLY_REVENUE_REPORT"
    FS = "FINANCIAL_STATEMENT"
    FINMIND = "FINMIND"
    FUTURES_PRICE = "FUTURES_PRICE"  # 台期貨每日行情（寫入 tw_futures.db）
    FUTURES_STOCK_UNIVERSE = "FUTURES_STOCK_UNIVERSE"  # 股票期貨標的池
    FUTURES_MARGIN = "FUTURES_MARGIN"  # 台期貨保證金（變動序列，寫入 tw_futures.db）
    # 連續合約：**衍生表**，來源是同一個 DB 的 futures_price_daily，不連網路
    FUTURES_CONTINUOUS = "FUTURES_CONTINUOUS"
    # 台期貨籌碼：三大法人 ＋ 大額交易人 ＋ 選擇權 PCR（皆為盤後公布）
    FUTURES_CHIP = "FUTURES_CHIP"


class ListingBoard(str, Enum):
    """
    掛牌板別（值即為公開資訊觀測站的 `TYPEK` 查詢參數）

    僅台股適用。與「發行人國別」是兩條獨立的軸，後者見 `IssuerOrigin`——
    兩者曾被合併在同一個 Enum 裡（`SII0`／`OTC0` 皆為 `"0"`），值相同會讓
    Python Enum 把後者摺成前者的 alias，是靜默的語意汙染。
    """

    SII = "sii"  # 上市（Securities Investment Information）
    OTC = "otc"  # 上櫃
    ROTC = "rotc"  # 興櫃
    PUB = "pub"  # 公開發行
    ALL = "all"  # 全部


class IssuerOrigin(str, Enum):
    """
    發行人國別（值即為月營收頁 URL 末碼）

    國外發行者即市場俗稱的 F 股／KY 股。本軸與 `ListingBoard` 正交：
    上市與上櫃各自都有國內、國外兩種發行人。
    """

    DOMESTIC = "0"  # 國內
    FOREIGN = "1"  # 國外


class FinancialStatementType(str, Enum):
    """財報類別"""

    BALANCE_SHEET = "BALANCE_SHEET"
    COMPREHENSIVE_INCOME = "COMPREHENSIVE_INCOME"
    CASH_FLOW = "CASH_FLOW"
    EQUITY_CHANGE = "EQUITY_CHANGE"


class FinMindDataType(str, Enum):
    """FinMind 資料子類型"""

    STOCK_INFO = "STOCK_INFO"
    STOCK_INFO_WITH_WARRANT = "STOCK_INFO_WITH_WARRANT"
    BROKER_INFO = "BROKER_INFO"
    BROKER_TRADING = "BROKER_TRADING"


# 定義 price 資料表欄位常量（schema 的宣告處為 stock_price_loader.py 的 CREATE TABLE）
PRICE_COL_OPEN: str = "開盤價"
PRICE_COL_HIGH: str = "最高價"
PRICE_COL_LOW: str = "最低價"
PRICE_COL_CLOSE: str = "收盤價"
PRICE_COL_SHARES: str = "成交股數"

# 定義 futures_price_daily 資料表欄位常量
# （schema 的宣告處為 futures_price_loader.py 的 CREATE TABLE）
FUTURES_PRICE_COL_OPEN: str = "開盤價"
FUTURES_PRICE_COL_HIGH: str = "最高價"
FUTURES_PRICE_COL_LOW: str = "最低價"
FUTURES_PRICE_COL_CLOSE: str = "收盤價"
FUTURES_PRICE_COL_VOLUME: str = "成交量"  # 單位：口（不是股）
FUTURES_PRICE_COL_SETTLEMENT: str = "結算價"
FUTURES_PRICE_COL_OPEN_INTEREST: str = "未沖銷契約量"

# 定義 chip 資料表欄位常量
CHIP_COL_FOREIGN_NET_SHARES: str = "外資買賣超股數"
CHIP_COL_TRUST_NET_SHARES: str = "投信買賣超股數"
CHIP_COL_DEALER_NET_SHARES: str = "自營商買賣超股數"


class PriceColumn(str, Enum):
    """
    price 資料表的中文欄位名

    **只有 `core/api/` 可以引用**：欄位名是資料庫 schema 的細節，策略層若直接
    取用中文字面值，換資料源時會靜默少開倉而非報錯。
    """

    OPEN = PRICE_COL_OPEN
    HIGH = PRICE_COL_HIGH
    LOW = PRICE_COL_LOW
    CLOSE = PRICE_COL_CLOSE
    SHARES = PRICE_COL_SHARES


class FuturesPriceColumn(str, Enum):
    """
    futures_price_daily 資料表的中文欄位名；引用規則同 `PriceColumn`

    **與 `PriceColumn` 不可互換**：期貨的量欄是 `成交量`（單位為口）而非
    `成交股數`，且 `結算價`／`未沖銷契約量` 在夜盤是 NULL（來源就沒有這兩項）。
    """

    OPEN = FUTURES_PRICE_COL_OPEN
    HIGH = FUTURES_PRICE_COL_HIGH
    LOW = FUTURES_PRICE_COL_LOW
    CLOSE = FUTURES_PRICE_COL_CLOSE
    VOLUME = FUTURES_PRICE_COL_VOLUME
    SETTLEMENT = FUTURES_PRICE_COL_SETTLEMENT
    OPEN_INTEREST = FUTURES_PRICE_COL_OPEN_INTEREST


class ChipColumn(str, Enum):
    """chip 資料表的中文欄位名；引用規則同 PriceColumn"""

    FOREIGN_NET_SHARES = CHIP_COL_FOREIGN_NET_SHARES
    TRUST_NET_SHARES = CHIP_COL_TRUST_NET_SHARES
    DEALER_NET_SHARES = CHIP_COL_DEALER_NET_SHARES


class UpdateStatus(str, Enum):
    """資料更新狀態"""

    SUCCESS = "success"  # 成功更新
    NO_DATA = "no_data"  # 沒有資料（API 返回空結果）
    ALREADY_UP_TO_DATE = "already_up_to_date"  # 資料庫已是最新
    ERROR = "error"  # 發生錯誤
