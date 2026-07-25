# Strategy 策略撰寫指南

**AlphaEdge** 的策略系統提供了一個完整的框架，讓開發者能夠輕鬆撰寫、測試和執行交易策略。本文件將詳細說明如何撰寫和使用策略。

## 目錄

- [Strategy 策略撰寫指南](#strategy-策略撰寫指南)
  - [目錄](#目錄)
  - [策略架構概述](#策略架構概述)
    - [目錄結構](#目錄結構)
  - [如何撰寫新策略](#如何撰寫新策略)
    - [步驟 1: 建立策略檔案](#步驟-1-建立策略檔案)
    - [步驟 2: 繼承 BaseStockStrategy](#步驟-2-繼承-basestockstrategy)
    - [步驟 3: 設定策略參數](#步驟-3-設定策略參數)
    - [步驟 4: 實作必須的方法](#步驟-4-實作必須的方法)
  - [必須實作的方法詳解](#必須實作的方法詳解)
    - [1. setup_account](#1-setup_account)
    - [2. setup_apis](#2-setup_apis)
    - [3. check_open_signal](#3-check_open_signal)
    - [4. check_close_signal](#4-check_close_signal)
    - [5. check_stop_loss_signal](#5-check_stop_loss_signal)
    - [6. calculate_position_size](#6-calculate_position_size)
  - [策略設定參數說明](#策略設定參數說明)
    - [策略基本資訊](#策略基本資訊)
    - [帳戶設定](#帳戶設定)
    - [回測設定](#回測設定)
    - [回測級別說明](#回測級別說明)
  - [資料 API 使用方式](#資料-api-使用方式)
    - [StockPriceAPI - 日線價格資料](#stockpriceapi---日線價格資料)
    - [StockTickAPI - 逐筆成交資料](#stocktickapi---逐筆成交資料)
    - [StockChipAPI - 籌碼資料](#stockchipapi---籌碼資料)
    - [MonthlyRevenueReportAPI - 月營收資料](#monthlyrevenuereportapi---月營收資料)
    - [FinancialStatementAPI - 財報資料](#financialstatementapi---財報資料)
  - [策略載入機制](#策略載入機制)
    - [自動載入規則](#自動載入規則)
    - [使用策略名稱](#使用策略名稱)
  - [使用策略進行回測](#使用策略進行回測)
    - [基本語法](#基本語法)
    - [參數說明](#參數說明)
    - [使用範例](#使用範例)
    - [回測結果](#回測結果)
  - [完整範例](#完整範例)
    - [快速開始範例](#快速開始範例)
  - [如何撰寫放空策略](#如何撰寫放空策略)
    - [放空策略的設定欄位](#放空策略的設定欄位)
    - [訊號方向對照](#訊號方向對照)
    - [放空策略範例](#放空策略範例)
    - [放空策略注意事項](#放空策略注意事項)

## 策略架構概述

AlphaEdge 的策略系統採用物件導向設計，所有策略都必須繼承 `BaseStockStrategy` 抽象類別。這個架構提供了：

- **統一的介面**: 所有策略都實作相同的方法，確保一致性
- **自動載入機制**: 策略會自動從 `core/strategies/stock/` 目錄載入
- **完整的資料存取**: 提供多種資料 API 供策略使用
- **靈活的回測設定**: 支援不同級別的回測（TICK、DAY、MIX）

### 目錄結構

```
core/strategies/
├── __init__.py              # 匯出 StrategyLoader
├── README.md                # 本文件
├── strategy_loader.py       # 策略自動載入器
└── stock/                   # 股票策略目錄
    ├── __init__.py
    ├── base.py              # BaseStockStrategy 基類
    ├── momentum_strategy_1.py # 動能策略 1（日線）
    ├── momentum_strategy_2.py # 動能策略 2（Tick）
    ├── momentum_strategy_3.py # 動能策略 3（均線動能）
    └── momentum_strategy_4.py # 動能策略 4（日線：T−1/T−2 收盤動能，開盤進出）
```

#### 動能策略 4（`MomentumStrategy4`）

- **篩選（T 日開盤前已知）**：T−1 收盤相對 T−2 收盤漲幅 ≥ 9%（可調 `MIN_PRICE_CHANGE_PCT_FOR_SIGNAL`）；成交量採 **T−1 全日量**（張）≥ 門檻（可調 `MIN_VOLUME_LOTS`）。
- **買進**：T 日以 **`open`** 作為 `StockOrder.price`。
- **賣出**：**開倉日的下一個交易日**（依 `StockPriceAPI` 有資料的交易日跳過休市，非僅日曆 +1 日）以 **`open`** 全數賣出。
- **回測**：須使用日線流程（`Scale.DAY`）；與框架一致，每日先執行平倉再開倉，故隔日開盤賣出會在出場日先平倉後再評估新進場。

```bash
python run.py --strategy MomentumStrategy4
```

## 如何撰寫新策略

### 步驟 1: 建立策略檔案

在 `core/strategies/stock/` 目錄下建立新的 Python 檔案，例如 `my_strategy.py`。

### 步驟 2: 繼承 BaseStockStrategy

```python
from core.strategies.stock import BaseStockStrategy
from core.models import StockAccount, StockOrder, StockQuote
from core.utils import Action, Scale, PositionType

class MyStrategy(BaseStockStrategy):
    """我的交易策略"""

    def __init__(self):
        super().__init__()
        # 策略設定...
```

### 步驟 3: 設定策略參數

在 `__init__` 方法中設定策略的基本參數：

```python
def __init__(self):
    super().__init__()

    # === 策略基本資訊 ===
    self.strategy_name: str = "MyStrategy"
    self.market: str = Market.STOCK
    self.position_type: str = PositionType.LONG
    self.enable_intraday: bool = True

    # === 帳戶設定 ===
    self.init_capital: float = 1000000.0  # 初始資金 100 萬
    self.max_holdings: Optional[int] = 10  # 最大持倉 10 檔

    # === 回測設定 ===
    self.is_backtest: bool = True
    self.scale: str = Scale.DAY  # 使用日線回測
    self.start_date: datetime.date = datetime.date(2020, 1, 1)
    self.end_date: datetime.date = datetime.date(2025, 5, 31)

    # 載入資料 API
    self.setup_apis()
```

### 步驟 4: 實作必須的方法

實作所有抽象方法，這些方法定義了策略的核心邏輯。詳細說明請參考下方「必須實作的方法詳解」章節。

## 必須實作的方法詳解

### 1. setup_account()

**用途**: 載入虛擬帳戶資訊，用於回測時管理資金和倉位。

**參數**:
- `account: StockAccount` - 虛擬帳戶物件

**實作範例**:

```python
def setup_account(self, account: StockAccount):
    """設置虛擬帳戶資訊"""
    self.account = account
```

**說明**:
- 這個方法會在回測開始時被自動呼叫
- 將 `account` 儲存到 `self.account` 以便後續使用
- 可以透過 `self.account` 存取帳戶餘額、持倉資訊等

### 2. setup_apis()

**用途**: 載入所需的資料 API，根據回測級別選擇性載入。

**實作範例**:

```python
def setup_apis(self):
    """設置資料 API"""

    # 基本資料 API（可選）
    self.chip = StockChipAPI()  # 籌碼資料
    self.mrr = MonthlyRevenueReportAPI()  # 月營收資料
    self.fs = FinancialStatementAPI()  # 財報資料

    # 根據回測級別載入對應的價格資料
    if self.scale in (Scale.TICK, Scale.MIX):
        self.tick = StockTickAPI()  # 逐筆資料

    if self.scale in (Scale.DAY, Scale.MIX):
        self.price = StockPriceAPI()  # 日線資料

    if self.scale == Scale.ALL:
        self.tick = StockTickAPI()
        self.price = StockPriceAPI()
```

**說明**:
- 根據 `self.scale` 決定要載入哪些 API
- `Scale.DAY`: 只需載入 `StockPriceAPI`
- `Scale.TICK`: 只需載入 `StockTickAPI`
- `Scale.MIX` 或 `Scale.ALL`: 需要載入兩者

### 3. check_open_signal()

**用途**: 開倉策略邏輯，判斷哪些股票應該開倉（買入）。

**參數**:
- `stock_quotes: List[StockQuote]` - 當前的股票報價列表

**回傳值**:
- `List[StockOrder]` - 開倉訂單列表

**實作範例**:

```python
def check_open_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
    """開倉策略（Long & Short）"""

    open_positions: List[StockQuote] = []

    # 檢查是否已達最大持倉數
    if self.max_holdings > 0 and self.account.get_position_count() >= self.max_holdings:
        return []

    # 取得前一個交易日的價格資料
    yesterday = MarketCalendar.get_last_trading_date(
        api=self.price, date=stock_quotes[0].date
    )
    yesterday_prices = self.price.get(yesterday)

    for stock_quote in stock_quotes:
        # 檢查是否已經持有該股票
        if self.account.check_has_position(stock_quote.stock_id):
            continue

        # 你的開倉條件判斷
        # 範例：當日漲幅 > 5% 且成交量 > 1000 張
        mask = yesterday_prices["stock_id"] == stock_quote.stock_id
        if yesterday_prices.loc[mask, "收盤價"].empty:
            continue

        yesterday_close = yesterday_prices.loc[mask, "收盤價"].iloc[0]
        if yesterday_close == 0:
            continue

        price_chg = (stock_quote.close / yesterday_close - 1) * 100

        if price_chg > 5 and stock_quote.volume > 1000:
            open_positions.append(stock_quote)

    # 計算部位大小並產生訂單
    return self.calculate_position_size(open_positions, Action.BUY)
```

**說明**:
- 此方法會在每個交易日被呼叫
- 需要根據策略邏輯篩選出符合條件的股票
- 最後呼叫 `calculate_position_size()` 來計算下單數量
- 回傳的訂單列表會被自動執行

### 4. check_close_signal()

**用途**: 平倉策略邏輯，判斷哪些持倉應該平倉（賣出）。

**參數**:
- `stock_quotes: List[StockQuote]` - 當前的股票報價列表

**回傳值**:
- `List[StockOrder]` - 平倉訂單列表

**實作範例**:

```python
def check_close_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
    """平倉策略（Long & Short）"""

    close_positions: List[StockQuote] = []

    for stock_quote in stock_quotes:
        # 檢查是否持有該股票
        if not self.account.check_has_position(stock_quote.stock_id):
            continue

        # 取得持倉資訊
        position = self.account.get_first_open_position(stock_quote.stock_id)
        if position is None:
            continue

        # 你的平倉條件判斷
        # 範例：持倉超過 5 天就平倉
        holding_days = (stock_quote.date - position.date).days
        if holding_days >= 5:
            close_positions.append(stock_quote)

        # 或根據獲利了結
        # profit_rate = (stock_quote.close / position.price - 1) * 100
        # if profit_rate > 10:  # 獲利超過 10% 就平倉
        #     close_positions.append(stock_quote)

    # 計算部位大小並產生訂單
    return self.calculate_position_size(close_positions, Action.SELL)
```

**說明**:
- 此方法會在每個交易日被呼叫，且會在 `check_open_signal()` 之前執行
- 需要檢查當前持倉並根據策略邏輯決定是否平倉
- 使用 `self.account.get_first_open_position()` 取得持倉資訊

### 5. check_stop_loss_signal()

**用途**: 停損策略邏輯，判斷哪些持倉應該觸發停損。

**參數**:
- `stock_quotes: List[StockQuote]` - 當前的股票報價列表

**回傳值**:
- `List[StockOrder]` - 停損訂單列表

**實作範例**:

```python
def check_stop_loss_signal(
    self, stock_quotes: List[StockQuote]
) -> List[StockOrder]:
    """停損策略"""

    stop_loss_orders: List[StockQuote] = []

    for stock_quote in stock_quotes:
        # 檢查是否持有該股票
        if not self.account.check_has_position(stock_quote.stock_id):
            continue

        # 取得持倉資訊
        position = self.account.get_first_open_position(stock_quote.stock_id)
        if position is None:
            continue

        # 計算虧損比例
        loss_rate = (stock_quote.close / position.price - 1) * 100

        # 停損條件：虧損超過 5%
        if loss_rate < -5:
            stop_loss_orders.append(stock_quote)
            logger.warning(
                f"股票 {stock_quote.stock_id} 觸發停損，"
                f"虧損 {round(loss_rate, 2)}%"
            )

    return self.calculate_position_size(stop_loss_orders, Action.SELL)
```

**說明**:
- 此方法會在每個交易日被呼叫
- 用於風險控制，當虧損達到設定閾值時自動平倉
- 如果不需要停損機制，可以回傳空列表

### 6. calculate_position_size()

**用途**: 計算下單股數，依據當前資金、價格、風控規則決定部位大小。

**參數**:
- `stock_quotes: List[StockQuote]` - 目標股票的報價資訊
- `action: Action` - 動作類型（`Action.BUY` 或 `Action.SELL`）

**回傳值**:
- `List[StockOrder]` - 訂單列表

**實作範例**:

```python
def calculate_position_size(
    self, stock_quotes: List[StockQuote], action: Action
) -> List[StockOrder]:
    """計算 Open or Close 的部位大小"""

    orders: List[StockOrder] = []

    if action == Action.BUY:
        # 計算可用的持倉檔數
        if self.max_holdings is not None:
            available_position_cnt = max(
                0, self.max_holdings - self.account.get_position_count()
            )
        else:
            available_position_cnt = len(stock_quotes)

        if available_position_cnt > 0:
            # 平均分配資金到每個部位
            per_position_size = self.account.balance / available_position_cnt

            for stock_quote in stock_quotes:
                if available_position_cnt == 0:
                    break

                # 計算可買張數：可用資金 / 每張價格
                # Units.LOT = 1000（1 張 = 1000 股）
                open_volume = int(
                    per_position_size / (stock_quote.close * Units.LOT)
                )

                # 至少買 1 張
                if open_volume >= 1:
                    orders.append(
                        StockOrder(
                            stock_id=stock_quote.stock_id,
                            date=stock_quote.date,
                            action=action,
                            position_type=PositionType.LONG,
                            price=stock_quote.cur_price,  # 使用當前價格
                            volume=open_volume,
                        )
                    )
                    available_position_cnt -= 1

    elif action == Action.SELL:
        # 平倉時使用持倉的全部股數
        for stock_quote in stock_quotes:
            position = self.account.get_first_open_position(stock_quote.stock_id)

            if position is None:
                continue

            orders.append(
                StockOrder(
                    stock_id=stock_quote.stock_id,
                    date=stock_quote.date,
                    action=action,
                    position_type=position.position_type,
                    price=stock_quote.cur_price,
                    volume=position.volume,  # 使用持倉的全部股數
                )
            )

    return orders
```

**說明**:
- **開倉時（Action.BUY）**:
  - 根據可用資金和最大持倉數計算每個部位的資金
  - 計算可買張數（1 張 = 1000 股）
  - 確保至少買 1 張才下單

- **平倉時（Action.SELL）**:
  - 使用持倉的全部股數進行平倉
  - 從 `position.volume` 取得持倉股數

## 策略設定參數說明

在 `__init__` 方法中可以設定的參數：

### 策略基本資訊

| 參數 | 類型 | 說明 | 預設值 |
|------|------|------|--------|
| `strategy_name` | `str` | 策略名稱，用於識別和報告 | `""` |
| `market` | `str` | 市場類型，目前僅支援 `Market.STOCK` | `Market.STOCK` |
| `position_type` | `str` | 部位方向，`PositionType.LONG`（做多）或 `PositionType.SHORT`（做空） | `PositionType.LONG` |
| `enable_intraday` | `bool` | 是否允許當沖交易 | `True` |

### 帳戶設定

| 參數 | 類型 | 說明 | 預設值 |
|------|------|------|--------|
| `init_capital` | `float` | 初始資金（元） | `0` |
| `max_holdings` | `Optional[int]` | 最大持倉檔數，`None` 表示無限制 | `0` |

### 回測設定

| 參數 | 類型 | 說明 | 預設值 |
|------|------|------|--------|
| `is_backtest` | `bool` | 是否為回測模式 | `True` |
| `scale` | `str` | 回測級別：`Scale.DAY`、`Scale.TICK`、`Scale.MIX`、`Scale.ALL` | `Scale.DAY` |
| `start_date` | `datetime.date` | 回測起始日期 | `None` |
| `end_date` | `datetime.date` | 回測結束日期 | `None` |

### 回測級別說明

- **`Scale.DAY`**: 日線回測，使用每日收盤價
- **`Scale.TICK`**: 逐筆回測，使用每筆成交資料
- **`Scale.MIX`**: 混合回測（目前尚未完全實作）
- **`Scale.ALL`**: 使用所有可用資料

## 資料 API 使用方式

策略中可以透過以下 API 取得各種資料。所有 API 都已經在 `setup_apis()` 中初始化，直接使用 `self.price`、`self.tick` 等即可。

### StockPriceAPI - 日線價格資料

**取得指定日期的所有股票價格**:

```python
# 取得 2024/1/1 的所有股票價格
prices = self.price.get(date=datetime.date(2024, 1, 1))
# 回傳 DataFrame，包含欄位：stock_id, 開盤價, 最高價, 最低價, 收盤價, 成交量等
```

**取得日期範圍的所有股票價格**:

```python
prices = self.price.get_range(
    start_date=datetime.date(2024, 1, 1),
    end_date=datetime.date(2024, 1, 31)
)
```

**取得指定個股的價格**:

```python
stock_prices = self.price.get_stock_price(
    stock_id="2330",
    start_date=datetime.date(2024, 1, 1),
    end_date=datetime.date(2024, 1, 31)
)
```

### StockTickAPI - 逐筆成交資料

**取得指定日期的逐筆資料**:

```python
# 取得 2024/1/1 的逐筆資料
ticks = self.tick.get(date=datetime.date(2024, 1, 1))
```

**取得指定個股的逐筆資料**:

```python
stock_ticks = self.tick.get_stock_tick(
    stock_id="2330",
    date=datetime.date(2024, 1, 1)
)
```

### StockChipAPI - 籌碼資料

**取得指定日期的籌碼資料**:

```python
# 取得 2024/1/1 的三大法人籌碼資料
chips = self.chip.get(date=datetime.date(2024, 1, 1))
# 回傳 DataFrame，包含欄位：stock_id, 外資買賣超, 投信買賣超, 自營商買賣超等
```

### MonthlyRevenueReportAPI - 月營收資料

**取得指定年月的月營收資料**:

```python
# 取得 2024 年 1 月的月營收資料
mrr = self.mrr.get(year=2024, month=1)
# 回傳 DataFrame，包含欄位：stock_id, 月營收, 月增率, 年增率等
```

### FinancialStatementAPI - 財報資料

**取得指定年季的財報資料**:

```python
# 取得 2024 年第 1 季的財報資料
fs = self.fs.get(year=2024, season=1)
# 回傳 DataFrame，包含各種財務指標
```

## 策略載入機制

AlphaEdge 使用 `StrategyLoader` 自動載入策略。系統會自動掃描 `core/strategies/stock/` 目錄下的所有 Python 檔案，找出繼承 `BaseStockStrategy` 的類別。

### 自動載入規則

1. **檔案位置**: 策略檔案必須放在 `core/strategies/stock/` 目錄下
2. **類別命名**: 策略類別名稱會作為策略識別名稱
3. **繼承要求**: 必須繼承 `BaseStockStrategy` 且不能是 `BaseStockStrategy` 本身

### 使用策略名稱

執行回測時，使用策略的**類別名稱**（Class Name）來指定策略：

```bash
# 如果策略類別名稱是 MomentumStrategy1，則使用 "MomentumStrategy1"
python run.py --strategy MomentumStrategy1
```

## 使用策略進行回測

### 基本語法

```bash
python run.py --strategy <StrategyName>
```

### 參數說明

- `--mode`: 執行模式，可選 `backtest` 或 `live`，預設為 `backtest`
- `--strategy`: 指定要使用的策略類別名稱（必填）

### 使用範例

```bash
# 執行回測模式，使用名為 "MomentumStrategy1" 的策略（動能 1 日線）
python run.py --strategy MomentumStrategy1

# 動能策略 4：T−1/T−2 收盤篩選、T 開盤買、次一交易日開盤賣
python run.py --strategy MomentumStrategy4

# 執行實盤模式（目前尚未實作）
python run.py --mode live --strategy MomentumStrategy1
```

### 回測結果

回測完成後，結果會儲存在 `core/backtest/results/<StrategyName>/` 目錄，包含：

1. **交易報告** (`trading_report.csv`) - 所有交易記錄和損益統計
2. **圖表分析**:
   - `balance_curve.png` - 資產曲線圖
   - `balance_and_benchmark_curve.png` - 資產與基準比較圖
   - `balance_mdd.png` - 最大回撤圖
   - `everyday_profit.png` - 每日損益圖
3. **日誌檔案** (`<StrategyName>.log`) - 回測過程的詳細日誌

## 完整範例

參考 `core/strategies/stock/momentum_strategy_1.py` 查看完整的策略實作範例。該範例展示了：

- 如何設定策略參數
- 如何實作開倉、平倉、停損邏輯
- 如何使用資料 API
- 如何計算部位大小

### 快速開始範例

以下是一個最簡單的策略範例：

```python
import datetime
from typing import List

from core.models import StockAccount, StockOrder, StockQuote
from core.strategies.stock import BaseStockStrategy
from core.utils import Action, Market, PositionType, Scale, Units

class SimpleStrategy(BaseStockStrategy):
    """簡單策略範例"""

    def __init__(self):
        super().__init__()
        self.strategy_name = "SimpleStrategy"
        self.init_capital = 1000000.0
        self.max_holdings = 5
        self.scale = Scale.DAY
        self.start_date = datetime.date(2020, 1, 1)
        self.end_date = datetime.date(2025, 5, 31)
        self.setup_apis()

    def setup_account(self, account: StockAccount):
        self.account = account

    def setup_apis(self):
        if self.scale in (Scale.DAY, Scale.MIX):
            self.price = StockPriceAPI()

    def check_open_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        # 簡單策略：隨機選擇前 3 檔股票
        open_positions = stock_quotes[:3]
        return self.calculate_position_size(open_positions, Action.BUY)

    def check_close_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        # 簡單策略：持倉超過 3 天就平倉
        close_positions = []
        for stock_quote in stock_quotes:
            if self.account.check_has_position(stock_quote.stock_id):
                position = self.account.get_first_open_position(stock_quote.stock_id)
                if position and (stock_quote.date - position.date).days >= 3:
                    close_positions.append(stock_quote)
        return self.calculate_position_size(close_positions, Action.SELL)

    def check_stop_loss_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        return []

    def calculate_position_size(
        self, stock_quotes: List[StockQuote], action: Action
    ) -> List[StockOrder]:
        orders = []
        if action == Action.BUY:
            available = max(0, self.max_holdings - self.account.get_position_count())
            if available > 0:
                per_position = self.account.balance / available
                for stock_quote in stock_quotes[:available]:
                    volume = int(per_position / (stock_quote.close * Units.LOT))
                    if volume >= 1:
                        orders.append(
                            StockOrder(
                                stock_id=stock_quote.stock_id,
                                date=stock_quote.date,
                                action=action,
                                position_type=PositionType.LONG,
                                price=stock_quote.cur_price,
                                volume=volume,
                            )
                        )
        elif action == Action.SELL:
            for stock_quote in stock_quotes:
                position = self.account.get_first_open_position(stock_quote.stock_id)
                if position:
                    orders.append(
                        StockOrder(
                            stock_id=stock_quote.stock_id,
                            date=stock_quote.date,
                            action=action,
                            position_type=position.position_type,
                            price=stock_quote.cur_price,
                            volume=position.volume,
                        )
                    )
        return orders
```

將此檔案儲存為 `core/strategies/stock/simple_strategy.py`，即可使用以下指令執行回測：

```bash
python run.py --strategy SimpleStrategy
```

---

**注意事項**:
- 策略檔案必須放在 `core/strategies/stock/` 目錄下
- 策略類別名稱會作為策略識別名稱
- 確保所有必須的方法都已實作
- 回測前請確認資料庫中有所需的資料（使用 `python -m tasks.update_db` 更新資料）


---

## 如何撰寫放空策略

回測框架支援放空（`PositionType.SHORT`），涵蓋**現股當沖沖賣**與**留倉（融券／借券）**兩種型態。
成本模型、保證金、借券費、維持率追繳與強制回補全部由引擎處理，策略只需要宣告方向並回傳正確的訂單。

完整規格見 [`backlog/放空回測框架建置.md`](../../backlog/放空回測框架建置.md)。

### 放空策略的設定欄位

在 `__init__` 中宣告（皆有預設值，只需設定用得到的）：

| 欄位 | 型別 | 預設 | 說明 |
| --- | --- | --- | --- |
| `position_type` | `PositionType` | `LONG` | 設為 `SHORT` 即為放空策略 |
| `enable_intraday` | `bool` | `True` | `True` 且方向為 SHORT 時，引擎自動採用**現股當沖沖賣**並切換為「先開後平」，使同日開平倉成立 |
| `short_method` | `ShortMethod` | `MARGIN` | 留倉放空的管道：`MARGIN`（融券）或 `SBL`（借券）；當沖時由引擎強制為 `DAY_TRADE` |
| `allowed_directions` | `Optional[Set[PositionType]]` | `None` | 訂單方向白名單，`None` 等同 `{position_type}`；要做多空並存的策略設為 `{LONG, SHORT}` |
| `max_holding_days` | `Optional[int]` | `None` | 留倉放空的保險絲，超過即強制回補（建議 20~30 天，用來近似停券強制回補） |
| `cost_config` | `Optional[CostConfig]` | `None` | 覆寫費率（手續費折扣、券費率等），`None` 使用市場常見預設值 |
| `short_constraint` | `Optional[ShortConstraint]` | `None` | 可成交限制：可當沖清單、券源檢核、停券日、單一標的曝險上限 |
| `day_trade_uncovered_policy` | `DayTradeUncoveredPolicy` | `FORCE_COVER_AT_CLOSE` | 當沖日終未回補的處理 |
| `margin_call_policy` | `MarginCallPolicy` | `FORCE_COVER` | 維持率跌破 130% 的處理 |
| `bar_execution_order` | `Optional[BarExecutionOrder]` | `None` | 單根 K 棒內的執行順序，`None` 由引擎依方向推導 |

### 訊號方向對照

放空是**先賣後買**，動作與做多完全相反：

| 方法 | 做多（LONG） | 放空（SHORT） |
| --- | --- | --- |
| `check_open_signal` | `Action.BUY` | **`Action.SELL`** |
| `check_close_signal` | `Action.SELL` | **`Action.BUY`**（回補） |
| `check_stop_loss_signal` | `Action.SELL`，**價格下跌**觸發 | **`Action.BUY`**，**價格上漲**觸發 |

> 訂單的 `position_type` 一律填 `PositionType.SHORT`。方向或動作填錯時，引擎會以 warning 剔除該筆訂單並計入拒單統計，不會靜默失敗。
>
> `short_method` 與 `is_day_trade` **不需要**自己填，引擎會依策略設定統一補值。

### 放空策略範例

```python
import datetime
from typing import List

from core.api.stock_price_api import StockPriceAPI
from core.models import StockAccount, StockOrder, StockQuote
from core.strategies.stock import BaseStockStrategy
from core.utils import Action, PositionType, Scale, ShortMethod


class SimpleShortStrategy(BaseStockStrategy):
    """
    簡易放空策略（日線、融券留倉）

    賣出（開倉）條件：
    - 當日漲幅 ≥ 9%（追高後的均值回歸）

    回補（平倉）條件：
    - 持有部位且報價日 ≥ 開倉日 + 1 日曆日

    停損條件：
    - 開倉後上漲超過 5%（放空是價格上漲才虧損）
    """

    MIN_PRICE_CHANGE_PCT: float = 9.0  # 開倉的最小漲幅（%）
    STOP_LOSS_PCT: float = 5.0  # 停損的上漲幅度（%）

    def __init__(self):
        super().__init__()

        self.strategy_name: str = "Simple-Short"
        self.init_capital: float = 1000000.0
        self.max_holdings: int = 5
        self.scale: Scale = Scale.DAY

        # 放空設定：融券留倉，最長持有 20 個曆日
        self.position_type: PositionType = PositionType.SHORT
        self.enable_intraday: bool = False
        self.short_method: ShortMethod = ShortMethod.MARGIN
        self.max_holding_days: int = 20

        self.start_date: datetime.date = datetime.date(2024, 1, 1)
        self.end_date: datetime.date = datetime.date(2024, 12, 31)

        self.setup_apis()

    def setup_account(self, account: StockAccount) -> None:
        """設置虛擬帳戶資訊"""

        self.account: StockAccount = account

    def setup_apis(self) -> None:
        """設置資料 API"""

        self.price: StockPriceAPI = StockPriceAPI()

    def check_open_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        """開倉（賣出）：漲幅達門檻即放空"""

        orders: List[StockOrder] = []
        for quote in stock_quotes:
            if self.account.check_has_position(quote.stock_id):
                continue

            if len(self.account.positions) >= self.max_holdings:
                break

            price_change_pct: float = (quote.close / quote.open - 1) * 100
            if price_change_pct < self.MIN_PRICE_CHANGE_PCT:
                continue

            orders.append(
                StockOrder(
                    stock_id=quote.stock_id,
                    date=quote.date,
                    action=Action.SELL,  # 放空開倉是賣出
                    position_type=PositionType.SHORT,
                    price=quote.close,
                    volume=1,
                )
            )
        return orders

    def check_close_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        """平倉（買進回補）：持有超過一個曆日即回補"""

        orders: List[StockOrder] = []
        for quote in stock_quotes:
            for position in self.account.get_positions(
                stock_id=quote.stock_id, position_type=PositionType.SHORT
            ):
                if (quote.date - position.date).days < 1:
                    continue

                orders.append(
                    StockOrder(
                        stock_id=quote.stock_id,
                        date=quote.date,
                        action=Action.BUY,  # 放空平倉是買進回補
                        position_type=PositionType.SHORT,
                        price=quote.close,
                        volume=position.volume,
                    )
                )
        return orders

    def check_stop_loss_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        """停損：放空是「價格上漲」才虧損，方向與做多相反"""

        orders: List[StockOrder] = []
        for quote in stock_quotes:
            for position in self.account.get_positions(
                stock_id=quote.stock_id, position_type=PositionType.SHORT
            ):
                loss_pct: float = (quote.close / position.price - 1) * 100
                if loss_pct < self.STOP_LOSS_PCT:
                    continue

                orders.append(
                    StockOrder(
                        stock_id=quote.stock_id,
                        date=quote.date,
                        action=Action.BUY,
                        position_type=PositionType.SHORT,
                        price=quote.close,
                        volume=position.volume,
                    )
                )
        return orders

    def calculate_position_size(
        self, stock_quotes: List[StockQuote], action: Action
    ) -> List[StockOrder]:
        """本範例固定 1 張，實務上應依保證金與曝險上限計算"""

        return []
```

### 放空策略注意事項

1. **資金佔用與做多不同**：放空的賣出價款會留作擔保品，不會進入可用餘額；帳戶當下只扣「保證金 + 開倉成本」，損益要等回補才結算。融券保證金成數為 90%，等於 1 張 100 元的股票會佔用 9 萬元。
2. **成本課在賣出端**：證交稅在放空**開倉**時就課（當沖 0.15%、留倉 0.3%），與做多相反；融券另有 0.08% 的融券手續費。
3. **當沖必須當日結清**：`enable_intraday=True` 時，日終仍未回補的部位會被引擎以收盤價強制回補並計數。若當日全日鎖漲停無法回補，會自動轉為融券留倉並記入 `limit_up_cover_failed`——這是放空最致命的尾部風險，**檢視回測結果時務必單獨看這個數字**。
4. **維持率會斷頭**：留倉放空在維持率跌破 130% 時會被強制回補，不是等你自己的停損訊號。停損條件應設得比斷頭門檻更早觸發。
5. **同一標的不可雙向持倉**：已有多單時開空單會被拒絕（反之亦然）。跨標的的多空並存則不受限制。
6. **成交價會被驗證**：訂單價格必須落在當日高低區間與漲跌停內，否則會被拒單。當沖策略請明確宣告成交價假設（建議開倉用 `open`、回補用 `close`），並確保 `check_open_signal` 只使用該時點之前可得的資訊。
7. **報表要看放空專屬欄位**：交易報表新增了 `Borrow Fee`、`Interest`、`Margin`、`Holding Days`、`ROI on Capital`，另有 `*_direction_summary.csv`（多空分開統計）與 `*_event_report.csv`（強制回補、斷頭、拒單次數）。
