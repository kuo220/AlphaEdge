# 快速開始

本指南將幫助您快速開始使用 AlphaEdge API。

## 安裝

### 環境要求

- Python 3.8+
- SQLite（用於一般資料）
- DolphinDB（用於時序 tick 資料，可選）

### 安裝步驟

1. 克隆專案：
```bash
git clone https://github.com/your-username/AlphaEdge.git
cd AlphaEdge
```

2. 安裝依賴：
```bash
# 使用 conda 環境（推薦）
conda env create -f dev/env/quant_mac.yml  # macOS
# 或
conda env create -f dev/env/quant_win.yml   # Windows

conda activate quant
```

3. 配置環境變數：
```bash
cp .env.example .env
# 編輯 .env 文件，填入必要的配置
```

## 基本使用

### 1. 初始化 API

```python
from trader.api.stock_price_api import StockPriceAPI
import datetime

# 建立 API 實例
price_api = StockPriceAPI()

# 查詢資料
date = datetime.date(2024, 1, 1)
prices = price_api.get(date)
print(prices.head())
```

### 2. 查詢價格資料

```python
from trader.api.stock_price_api import StockPriceAPI
import datetime

price_api = StockPriceAPI()

# 查詢單日所有股票價格
prices = price_api.get(datetime.date(2024, 1, 1))

# 查詢日期範圍的價格
prices_range = price_api.get_range(
    start_date=datetime.date(2024, 1, 1),
    end_date=datetime.date(2024, 1, 31)
)

# 查詢特定個股價格
stock_prices = price_api.get_stock_price(
    stock_id="2330",
    start_date=datetime.date(2024, 1, 1),
    end_date=datetime.date(2024, 1, 31)
)
```

### 3. 查詢 Tick 資料

```python
from trader.api.stock_tick_api import StockTickAPI
import datetime

tick_api = StockTickAPI()

# 查詢日期範圍的 tick 資料
ticks = tick_api.get(
    start_date=datetime.date(2024, 1, 1),
    end_date=datetime.date(2024, 1, 1)
)

# 查詢特定個股的 tick 資料
stock_ticks = tick_api.get_stock_ticks(
    stock_id="2330",
    start_date=datetime.date(2024, 1, 1),
    end_date=datetime.date(2024, 1, 1)
)
```

## 下一步

- 查看 [API 參考](api/overview.md) 了解所有可用的 API
- 閱讀 [使用範例](examples/basic.md) 了解更多使用方式
- 學習如何 [開發策略](examples/strategy.md)
