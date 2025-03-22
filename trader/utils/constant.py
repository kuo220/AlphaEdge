from enum import Enum

# 定義動作類型常量
ACTION_BUY = "Buy"
ACTION_SELL = "Sell"

# 定義價格類型常量
STOCK_PRICE_TYPE_LIMITPRICE = "LMT"
STOCK_PRICE_TYPE_MKT = "MKT"
STOCK_PRICE_TYPE_CLOSE = "Close"

# 定義下單類型常量
ORDER_TYPE_ROD = "ROD"
ORDER_TYPE_IOC = "IOC"
ORDER_TYPE_FOK = "FOK"

# 定義報價模式常量
QUOTE_TYPE_TICK = "tick"
QUOTE_TYPE_BIDASK = "bidask"
QUOTE_TYPE_QUOTE = "quote"

# 定義股票下單單位常量
STOCK_ORDER_LOT_COMMON = "Common"  # 整股
STOCK_ORDER_LOT_BLOCKTRADE = "BlockTrade"  # 鉅額
STOCK_ORDER_LOT_FIXING = "Fixing"  # 定盤
STOCK_ORDER_LOT_ODD = "Odd"  # 零股
STOCK_ORDER_LOT_INTRADAY_ODD = "IntradayOdd"  # 零股


class Action(str, Enum):
    Buy = ACTION_BUY
    Sell = ACTION_SELL
    
class StockPriceType(str, Enum):
    LMT = STOCK_PRICE_TYPE_LIMITPRICE
    MKT = STOCK_PRICE_TYPE_MKT


class OrderType(str, Enum):
    ROD = ORDER_TYPE_ROD
    IOC = ORDER_TYPE_IOC
    FOK = ORDER_TYPE_FOK
    
    
class QuoteType(str, Enum):
    Tick = QUOTE_TYPE_TICK
    BidAsk = QUOTE_TYPE_BIDASK
    Quote = QUOTE_TYPE_QUOTE
    
    
class StockOrderLot(str, Enum):
    Common = STOCK_ORDER_LOT_COMMON  # 整股
    BlockTrade = STOCK_ORDER_LOT_BLOCKTRADE  # 鉅額
    Fixing = STOCK_ORDER_LOT_FIXING  # 定盤
    Odd = STOCK_ORDER_LOT_ODD  # 零股
    IntradayOdd = STOCK_ORDER_LOT_INTRADAY_ODD  # 盤中零股
    

class OrderState(str, Enum):
    StockDeal = "SDEAL"
    StockOrder = "SORDER"
    FuturesOrder = "FORDER"
    FuturesDeal = "FDEAL"
    

class Status(str, Enum):
    Cancelled = "Cancelled"
    Filled = "Filled"
    PartFilled = "PartFilled"
    Inactive = "Inactive"
    Failed = "Failed"
    PendingSubmit = "PendingSubmit"
    PreSubmitted = "PreSubmitted"
    Submitted = "Submitted"
    

class Commission(float, Enum):
    """ 券商手續費相關常數 """
    CommRate = 0.001425  # 券商手續費率（commission rate）
    Discount = 0.3  # 券商手續費折扣（commission discount）
    MinFee = 20.0  # 券商最低手續費限制（minimum fee）
    TaxRate = 0.003 # 證券交易稅（Securities Transaction Tax Rate）


class Market(str, Enum):
    """ 市場類別 """
    Stock = "Stock"
    Future = "Future"
    

class Scale(str, Enum):
    """ Kbar 級別 """
    TICK = "TICK"
    DAY = "DAY"
    ALL = "ALL"
    

class PositionType(str, Enum):
    """ 部位方向 """
    LONG = "LONG"
    SHORT = "SHORT"
    
    