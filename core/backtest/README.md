# 回測系統說明

AlphaEdge 的回測系統提供了完整的策略回測功能，支援多種回測級別和詳細的績效分析。

## 目錄

- [回測系統說明](#回測系統說明)
  - [目錄](#目錄)
  - [回測級別](#回測級別)
  - [回測流程](#回測流程)
  - [回測結果](#回測結果)
  - [績效指標](#績效指標)
  - [使用方式](#使用方式)

## 回測級別

AlphaEdge 支援四種回測級別（KBar 級別）：

1. **TICK**: 逐筆成交資料回測
   - 使用 `StockTickAPI` 取得逐筆成交資料
   - 適合需要精確價格和時間的策略
   - 可參考 `core/strategies/stock/momentum_strategy_1.py` 範例

2. **DAY**: 日線資料回測
   - 使用 `StockPriceAPI` 取得日線收盤價資料
   - 適合基於日線技術指標的策略
   - 可參考 `core/strategies/stock/momentum_strategy_1.py` 或 `core/strategies/stock/simple_long_strategy.py` 範例

3. **MIX**: 混合級別回測
   - 同時使用 TICK 和 DAY 資料
   - 目前尚未完全實作

4. **ALL**: 使用所有可用資料
   - 同時載入 TICK 和 DAY 資料 API
   - 適合需要同時使用多種資料來源的策略

在策略中設定回測級別：

```python
self.scale: str = Scale.DAY  # 或 Scale.TICK
```

## 回測流程

回測系統的執行流程如下：

1. **初始化策略**: 載入策略類別並初始化
2. **設定帳戶**: 建立虛擬帳戶，設定初始資金
3. **載入資料 API**: 根據回測級別載入對應的資料 API
4. **資料適配**: 透過 `StockQuoteAdapter`（`core/adapters/stock_quote_adapter.py`）將日線／Tick API 資料轉成統一的 `StockQuote`
5. **執行回測**: 逐日（或逐筆）執行策略邏輯
   - 檢查停損訊號
   - 檢查平倉訊號
   - 檢查開倉訊號
   - 執行訂單
6. **生成報告**: 計算績效指標並生成視覺化圖表

## 部位大小與檔數上限

「這一單買幾張」與「總共可以持有幾檔」是**兩層把關**，責任分工如下：

| 層級 | 由誰負責 | 做什麼 |
|------|----------|--------|
| 策略 | `check_open_signal()` | 選標的、決定**參考價**（`close`／`open`／tick 價皆可） |
| 部位大小模型 | `EqualWeightSizer`（`core/backtest/models/sizing.py`） | 依剩餘名額均分餘額、換算張數 |
| 引擎 | `Backtester.check_max_holdings()` | **硬上限**：超過 `max_holdings` 的開倉單一律剔除並計數 |

### 策略要寫的部分

`calculate_position_size()` 的 `BUY` 分支**不需要自己算張數**，交給 `self.sizer`：

```python
candidates: List[Tuple[StockQuote, float]] = [
    (stock_quote, stock_quote.close) for stock_quote in stock_quotes  # 參考價由策略決定
]

for stock_quote, ref_price, open_volume in self.sizer.size(
    self.account, candidates, self.max_holdings
):
    orders.append(StockOrder(..., price=ref_price, volume=open_volume))
```

`self.sizer` 由 `BaseStockStrategy` 預設為 `EqualWeightSizer()`；要換配置演算法（波動度加權等），在策略的 `__init__` 覆寫該欄位即可，呼叫端不動。

### 預設的等權公式

```
可開檔數 = max(0, max_holdings - 現有持倉檔數)   # max_holdings 為 None 時不限制
每檔資金 = account.balance / 可開檔數
張數     = int(每檔資金 / (參考價 × Units.LOT))   # 無條件捨去
下單條件 = 張數 >= 1；參考價 <= 0 者跳過
```

**`int()` 的無條件捨去與「至少 1 張」的門檻不可改動**——它們直接決定 LONG 回歸 baseline 的 915 筆結果。

這段公式原本在五支策略內各寫一遍，收斂時發現兩處已經漂移，一併定案（2026-08-09）：

| 項目 | 收斂前 | 收斂後 |
|------|--------|--------|
| `max_holdings is None` | 收斂前五支動能策略中有一支為「不開倉」，其餘四支為「不限制」 | 一律**不限制**（多數派 4:1，且與 `Optional[int]` 的直覺一致） |
| 參考價 `<= 0` | `_1`／`_3` 無檢查，遇收盤價為 0 會 `ZeroDivisionError` **中斷整場回測** | 一律**跳過該檔**，不影響其他候選 |

兩者都不改變既有回測結果：前者的分支在五支策略上皆跑不到（都在 `__init__` 明確設了 `max_holdings`），後者只在資料異常時觸發。

### 引擎側硬上限

`max_holdings` 是真正的風控，不是「策略願意遵守才生效」的建議值。策略即使不呼叫 sizer，超額的開倉單仍會在 `execute_open_signal()` 內被剔除，並以 `logger.warning` ＋ `event_counts["rejected_max_holdings"]` 留痕——**禁止靜默丟棄**。`max_holdings` 為 `None` 時不做任何截斷。

## 回測結果

回測完成後，系統會自動產生以下內容：

### 1. 交易報告 (`trading_report.csv`)

包含所有交易記錄、損益統計等詳細資訊。

### 2. 圖表分析

- **資產曲線圖** (`balance_curve.png`): 顯示資產隨時間的變化
- **資產與基準比較圖** (`balance_and_benchmark_curve.png`): 比較策略表現與基準（如大盤指數）
- **最大回撤圖** (`balance_mdd.png`): 顯示最大回撤情況
- **每日損益圖** (`everyday_profit.png`): 顯示每日損益分布

### 3. 日誌檔案 (`<StrategyName>.log`)

記錄回測過程中的所有資訊、警告和錯誤。

### 儲存位置

回測結果儲存路徑：`core/backtest/results/<StrategyName>/`

## 績效指標

回測系統會自動計算以下績效指標：

- **總報酬率**: 策略的總收益
- **年化報酬率**: 年化後的報酬率
- **Sharpe Ratio**: 風險調整後報酬率
- **最大回撤 (MDD)**: 從高點到低點的最大跌幅
- **勝率**: 獲利交易的比例
- **平均獲利/虧損**: 平均每筆交易的獲利和虧損
- **交易次數**: 總交易筆數

## 使用方式

### 基本語法

```bash
python run.py --strategy <StrategyName>
```

### 參數說明

- `--mode`: 執行模式，可選 `backtest` 或 `live`，預設為 `backtest`
- `--strategy`: 指定要使用的策略類別名稱（必填）

### 使用範例

```bash
# 執行回測模式，使用名為 "MomentumStrategy1" 的策略
python run.py --strategy MomentumStrategy1

# 執行實盤模式（目前尚未實作）
python run.py --mode live --strategy MomentumStrategy1
```

### 注意事項

- Strategy Name 是 Class 的名稱
- 策略會自動從 `core/strategies/stock/` 目錄載入
- 回測前請確認資料庫中有所需的資料（使用 `python -m tasks.update_db` 更新資料）
- 回測結果會儲存在 `core/backtest/results/<StrategyName>/` 目錄

## 相關文檔

- [策略開發指南](../strategies/README.md)
- [專案 README](../../README.md)
