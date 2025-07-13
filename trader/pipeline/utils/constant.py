from enum import Enum


class InstrumentType(str, Enum):
    """ 金融商品類別 """

    STOCK = "Stock"
    FUTURE = "Future"
    OPTION = "Option"


class DataType(str, Enum):
    """ 資料類型 """

    PRICE = "Price"
    CHIP = "Chip"
    TICK = "Tick"


class MarketType(str, Enum):
    """ 公開資訊觀測站的 URL 類別 """

    SII = "sii"                 # 上市（Securities Investment Information）
    OTC = "otc"                 # 上櫃
    ROTC = "rotc"               # 興櫃
    PUB = "pub"                 # 公開發行
    ALL = "all"                 # 全部
    SII0 = "0"                  # 國內上市（爬月營收會用到）
    SII1 = "1"                  # 國外上市
    OTC0 = "0"                  # 國內上櫃
    OTC1 = "1"                  # 國外上櫃


class FinancialStatementType(str, Enum):
    """ 財報類別 """

    BALANCE_SHEET = "BALANCE_SHEET"
    COMPREHENSIVE_INCOME = "COMPREHENSIVE_INCOME"
    CASH_FLOW = "CASH_FLOW"
    EQUITY_CHANGE = "EQUITY_CHANGE"


class FileEncoding(str, Enum):
    """ 檔案編碼類型 """

    UTF8 = "utf-8"
    BIG5 = "big5"