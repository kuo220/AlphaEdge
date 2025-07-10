from enum import Enum


class InstrumentType(str, Enum):
    STOCK = "Stock"
    FUTURE = "Future"
    OPTION = "Option"


class DataType(str, Enum):
    PRICE = "Price"
    CHIP = "Chip"
    TICK = "Tick"


class MarketType(str, Enum):
    SII = "sii"                 # 上市（Securities Investment Information）
    OTC = "otc"                 # 上櫃
    ROTC = "rotc"               # 興櫃
    PUB = "pub"                 # 公開發行
    ALL = "all"                 # 全部
    SII0 = "sii0"               # 國內上市（爬月營收會用到）
    SII1 = "sii1"               # 國外上市
    OTC0 = "otc0"               # 國內上櫃
    OTC1 = "otc1"               # 國外上櫃