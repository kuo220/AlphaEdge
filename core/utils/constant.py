import datetime
from enum import Enum

# 定義動作類型常量
ACTION_BUY = "Buy"
ACTION_SELL = "Sell"
ACTION_OPEN = "Open"
ACTION_CLOSE = "Close"

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

# 定義放空管道常量
SHORT_METHOD_DAY_TRADE = "DAY_TRADE"  # 現股當沖沖賣（先賣後買，同日結清）
SHORT_METHOD_MARGIN = "MARGIN"  # 融券賣出（留倉）
SHORT_METHOD_SBL = "SBL"  # 借券賣出（留倉，議定費率）

# 定義單根 K 棒內的執行順序常量
BAR_EXECUTION_ORDER_CLOSE_THEN_OPEN = "CLOSE_THEN_OPEN"  # 先平倉再開倉（日頻再平衡）
BAR_EXECUTION_ORDER_OPEN_THEN_CLOSE = "OPEN_THEN_CLOSE"  # 先開倉再平倉（當沖）

# 定義當沖日終未回補的處理政策常量
DAY_TRADE_UNCOVERED_FORCE_COVER_AT_CLOSE = "FORCE_COVER_AT_CLOSE"  # 以收盤價強制回補
DAY_TRADE_UNCOVERED_CONVERT_TO_MARGIN = "CONVERT_TO_MARGIN"  # 轉為融券留倉
DAY_TRADE_UNCOVERED_RAISE = "RAISE"  # 直接拋出錯誤

# 定義融券維持率追繳的處理政策常量
MARGIN_CALL_FORCE_COVER = "FORCE_COVER"  # 強制回補（斷頭）
MARGIN_CALL_WARN_ONLY = "WARN_ONLY"  # 僅記錄不強制回補

# 現股當沖證交稅減半的落日日期（放 module-level：float Enum 無法承載 date）
DAY_TRADE_TAX_EXPIRY: datetime.date = datetime.date(2027, 12, 31)

# 計息基準日數（放 module-level：float Enum 內混入整數語意會失真）
DAYS_PER_YEAR: int = 365

# 台股漲跌幅限制（單日 ±10%）
PRICE_LIMIT_RATIO: float = 0.1

# 台股價格檔位：(價格上限, 檔位)，價格小於上限時適用該檔位
PRICE_TICK_TABLE: list = [
    (10.0, 0.01),
    (50.0, 0.05),
    (100.0, 0.1),
    (500.0, 0.5),
    (1000.0, 1.0),
    (float("inf"), 5.0),
]


class Action(str, Enum):
    BUY = ACTION_BUY
    SELL = ACTION_SELL
    OPEN = ACTION_OPEN
    CLOSE = ACTION_CLOSE


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
    """券商手續費相關常數"""

    CommRate = 0.001425  # 券商手續費率（commission rate）
    Discount = 0.3  # 券商手續費折扣（commission discount）
    MinFee = 20.0  # 券商最低手續費限制（minimum fee）
    TaxRate = 0.003  # 證券交易稅（Securities Transaction Tax Rate）
    DayTradeTaxRate = 0.0015  # 現股當沖證交稅（減半，適用至 DAY_TRADE_TAX_EXPIRY）


class ShortCost(float, Enum):
    """放空（融券／借券）相關成本常數"""

    MarginRate = 0.9  # 融券保證金成數（賣出價金的 90%）
    MarginBorrowFeeRate = 0.0008  # 融券手續費率（借券費，賣出時一次性收取）
    MarginInterestRate = 0.002  # 融券保證金利息年利率（券商付給客戶，為收入）
    MaintenanceRatio = 1.3  # 融券維持率門檻（低於則追繳／斷頭）
    SBLFeeRate = 0.03  # 借券（SBL）年化費率（議定區間 0.01%~16%，取市場常見值）


class MarginCost(float, Enum):
    """融資（做多槓桿）相關成本常數，本階段僅定義不啟用"""

    FinancingRate = 0.0635  # 融資年利率（券商常見 6.15%~6.5%）
    ListedFinancingRatio = 0.6  # 上市股票融資成數
    OTCFinancingRatio = 0.5  # 上櫃股票融資成數


class Market(str, Enum):
    """市場類別"""

    STOCK = "Stock"
    FUTURE = "Future"
    OPTION = "Option"


class Scale(str, Enum):
    """Kbar 級別"""

    TICK = "TICK"
    DAY = "DAY"
    MIX = "MIX"


class PositionType(str, Enum):
    """部位方向"""

    LONG = "LONG"
    SHORT = "SHORT"


class ShortMethod(str, Enum):
    """放空管道：三者的成本結構完全不同"""

    DAY_TRADE = SHORT_METHOD_DAY_TRADE
    MARGIN = SHORT_METHOD_MARGIN
    SBL = SHORT_METHOD_SBL


class BarExecutionOrder(str, Enum):
    """單根 K 棒內開平倉的執行順序"""

    CLOSE_THEN_OPEN = BAR_EXECUTION_ORDER_CLOSE_THEN_OPEN
    OPEN_THEN_CLOSE = BAR_EXECUTION_ORDER_OPEN_THEN_CLOSE


class DayTradeUncoveredPolicy(str, Enum):
    """當沖放空於日終仍未回補時的處理政策"""

    FORCE_COVER_AT_CLOSE = DAY_TRADE_UNCOVERED_FORCE_COVER_AT_CLOSE
    CONVERT_TO_MARGIN = DAY_TRADE_UNCOVERED_CONVERT_TO_MARGIN
    RAISE = DAY_TRADE_UNCOVERED_RAISE


class MarginCallPolicy(str, Enum):
    """融券維持率低於門檻時的處理政策"""

    FORCE_COVER = MARGIN_CALL_FORCE_COVER
    WARN_ONLY = MARGIN_CALL_WARN_ONLY


class Units(int, Enum):
    """股票張數單位"""

    SHARE = 1  # 1 Share = 1 Share
    LOT = 1000  # 1 Lot = 1000 Shares
