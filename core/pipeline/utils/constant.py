from enum import Enum


class InstrumentType(str, Enum):
    """金融商品類別"""

    STOCK = "Stock"
    FUTURE = "Future"
    OPTION = "Option"


class DataType(str, Enum):
    """資料類型"""

    PRICE = "Price"
    CHIP = "Chip"
    MARGIN = "Margin"  # 信用交易（融資融券餘額）
    TICK = "Tick"
    MRR = "MONTHLY_REVENUE_REPORT"
    FS = "FINANCIAL_STATEMENT"
    FINMIND = "FINMIND"


class MarketType(str, Enum):
    """公開資訊觀測站的 URL 類別"""

    SII = "sii"  # 上市（Securities Investment Information）
    OTC = "otc"  # 上櫃
    ROTC = "rotc"  # 興櫃
    PUB = "pub"  # 公開發行
    ALL = "all"  # 全部
    SII0 = "0"  # 國內上市（爬月營收會用到）
    SII1 = "1"  # 國外上市
    OTC0 = "0"  # 國內上櫃
    OTC1 = "1"  # 國外上櫃


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

# 定義 chip 資料表欄位常量
CHIP_COL_FOREIGN_NET_SHARES: str = "外資買賣超股數"
CHIP_COL_TRUST_NET_SHARES: str = "投信買賣超股數"
CHIP_COL_DEALER_NET_SHARES: str = "自營商買賣超股數"


class PriceColumn(str, Enum):
    """
    price 資料表的中文欄位名

    **只有 `core/api/` 可以引用**：欄位名是資料庫 schema 的細節，策略層若直接
    取用中文字面值，換資料源時會靜默少開倉而非報錯（見
    `backlog/策略層資料欄位抽象化.md`）。
    """

    OPEN = PRICE_COL_OPEN
    HIGH = PRICE_COL_HIGH
    LOW = PRICE_COL_LOW
    CLOSE = PRICE_COL_CLOSE
    SHARES = PRICE_COL_SHARES


class ChipColumn(str, Enum):
    """chip 資料表的中文欄位名；引用規則同 PriceColumn"""

    FOREIGN_NET_SHARES = CHIP_COL_FOREIGN_NET_SHARES
    TRUST_NET_SHARES = CHIP_COL_TRUST_NET_SHARES
    DEALER_NET_SHARES = CHIP_COL_DEALER_NET_SHARES


class FileEncoding(str, Enum):
    """檔案編碼類型"""

    UTF8 = "utf-8"
    UTF8_SIG = "utf-8-sig"  # UTF-8 with BOM，用於 Excel 等軟體正確識別中文
    BIG5 = "big5"


class UpdateStatus(str, Enum):
    """資料更新狀態"""

    SUCCESS = "success"  # 成功更新
    NO_DATA = "no_data"  # 沒有資料（API 返回空結果）
    ALREADY_UP_TO_DATE = "already_up_to_date"  # 資料庫已是最新
    ERROR = "error"  # 發生錯誤
