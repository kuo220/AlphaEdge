# 常見問題

## 一般問題

### Q: 如何安裝 AlphaEdge？

A: 請參考 [快速開始指南](getting-started.md) 的安裝步驟。

### Q: 需要哪些依賴？

A: 主要依賴包括：
- Python 3.8+
- pandas
- SQLite（用於一般資料）
- DolphinDB（用於 tick 資料，可選）
- loguru（用於日誌）

詳細的依賴列表請參考 `dev/env/quant_mac.yml` 或 `dev/env/quant_win.yml`。

### Q: 如何更新資料庫？

A: 使用 `tasks/update_db.py` 腳本：

```bash
python -m tasks.update_db --target price chip mrr fs
```

詳細說明請參考 [README](../README.md#資料庫更新)。

## API 使用問題

### Q: API 返回空 DataFrame 怎麼辦？

A: 這可能是因為：
1. 查詢的日期沒有資料
2. 資料庫尚未更新
3. 查詢參數錯誤（例如日期範圍錯誤）

建議：
- 檢查資料庫中是否有該日期的資料
- 確認日期格式正確（使用 `datetime.date`）
- 檢查日誌檔案了解詳細錯誤資訊

### Q: 如何查詢特定股票的所有歷史資料？

A: 使用 `get_stock_price` 方法：

```python
from trader.api.stock_price_api import StockPriceAPI
import datetime

api = StockPriceAPI()
prices = api.get_stock_price(
    stock_id="2330",
    start_date=datetime.date(2013, 1, 1),  # 從最早開始
    end_date=datetime.date.today()
)
```

### Q: Tick 資料查詢很慢怎麼辦？

A: 建議：
1. 縮小查詢的日期範圍
2. 使用 `get_stock_ticks` 查詢特定股票，而不是 `get` 查詢所有股票
3. 確保 DolphinDB 連線正常且資料庫已建立索引

### Q: 如何同時查詢多檔股票？

A: 有兩種方式：

**方式 1：批次查詢**
```python
stock_ids = ["2330", "2317", "2454"]
all_data = []

for stock_id in stock_ids:
    prices = api.get_stock_price(stock_id, start_date, end_date)
    all_data.append(prices)

combined = pd.concat(all_data, ignore_index=True)
```

**方式 2：先查詢全部再篩選**
```python
all_prices = api.get_range(start_date, end_date)
selected = all_prices[all_prices['stock_id'].isin(stock_ids)]
```

## 策略開發問題

### Q: 如何開發自己的策略？

A: 請參考：
1. [策略開發範例](examples/strategy.md)
2. [BaseStockStrategy API 文檔](api/strategy/base_stock_strategy.md)
3. [策略開發指南](../trader/strategies/README.md)

### Q: 策略回測時如何設定參數？

A: 在策略的 `__init__` 方法中設定：

```python
class MyStrategy(BaseStockStrategy):
    def __init__(self):
        super().__init__()
        self.init_capital = 1000000.0  # 初始資金
        self.max_holdings = 10  # 最大持倉數
        self.start_date = datetime.date(2024, 1, 1)
        self.end_date = datetime.date(2024, 12, 31)
```

### Q: 如何執行策略回測？

A: 使用 `run.py`：

```bash
python run.py --strategy YourStrategyName
```

策略名稱必須是類別名稱，且策略檔案必須放在 `trader/strategies/stock/` 目錄下。

### Q: 回測結果在哪裡？

A: 回測結果儲存在 `trader/backtest/results/<StrategyName>/` 目錄，包含：
- `trading_report.csv`: 交易報告
- `balance_curve.png`: 資產曲線圖
- `balance_and_benchmark_curve.png`: 資產與基準比較圖
- 其他圖表和日誌檔案

## 資料問題

### Q: 資料更新頻率？

A: 建議的更新頻率：
- **價格和籌碼資料**: 每日更新
- **月營收資料**: 每月更新（通常在每月 10 日後）
- **財報資料**: 每季更新（依申報期限）
- **Tick 資料**: 每日更新（資料量較大）

### Q: 如何檢查資料是否最新？

A: 查詢資料庫中最新日期的資料：

```python
from trader.api.stock_price_api import StockPriceAPI
import datetime

api = StockPriceAPI()
# 查詢最近幾天的資料
recent_prices = api.get_range(
    start_date=datetime.date.today() - datetime.timedelta(days=7),
    end_date=datetime.date.today()
)

if recent_prices.empty:
    print("資料可能需要更新")
else:
    latest_date = recent_prices['date'].max()
    print(f"最新資料日期: {latest_date}")
```

### Q: 資料庫檔案在哪裡？

A: 資料庫檔案位置由 `trader/config.py` 中的 `DB_PATH` 設定決定。預設通常在專案根目錄或 `data/` 目錄下。

## 效能問題

### Q: 查詢大量資料時記憶體不足？

A: 建議：
1. 分批查詢資料，而不是一次查詢全部
2. 查詢後立即處理，然後刪除不需要的變數
3. 使用 `del` 釋放記憶體
4. 考慮使用資料庫的篩選條件，減少查詢結果

### Q: 策略回測很慢？

A: 優化建議：
1. 預先載入需要的資料，避免在迴圈中重複查詢
2. 使用快取機制（如 `functools.lru_cache`）
3. 減少不必要的計算
4. 縮小回測日期範圍進行測試

## 錯誤處理

### Q: 遇到 "ModuleNotFoundError" 錯誤？

A: 確保：
1. 已安裝所有依賴
2. 已啟動正確的 conda 環境
3. Python 路徑設定正確

### Q: 遇到資料庫連線錯誤？

A: 檢查：
1. 資料庫檔案是否存在
2. 檔案權限是否正確
3. 是否有其他程式正在使用資料庫
4. DolphinDB 服務是否正常運行（如果使用 tick 資料）

### Q: 如何查看詳細的錯誤訊息？

A: 檢查日誌檔案：
- API 日誌：`trader/logs/` 目錄
- 策略回測日誌：`trader/backtest/results/<StrategyName>/` 目錄

## 其他問題

### Q: 如何貢獻程式碼或報告問題？

A: 歡迎提交 Issue 或 Pull Request 到專案的 GitHub 儲存庫。

### Q: 有更多問題？

A: 請參考：
- [README](../README.md)
- [架構分析報告](../ARCHITECTURE_REVIEW.md)
- [策略開發指南](../trader/strategies/README.md)

如果問題仍未解決，請提交 Issue 並附上：
- 錯誤訊息
- 相關程式碼
- 環境資訊（Python 版本、作業系統等）
