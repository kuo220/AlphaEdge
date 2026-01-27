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
    BROKER_INFO = "BROKER_INFO"
    BROKER_TRADING = "BROKER_TRADING"


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
