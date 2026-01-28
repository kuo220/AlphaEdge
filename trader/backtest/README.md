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
   - 可參考 `trader/strategies/stock/momentum_tick_strategy.py` 範例

2. **DAY**: 日線資料回測
   - 使用 `StockPriceAPI` 取得日線收盤價資料
   - 適合基於日線技術指標的策略
   - 可參考 `trader/strategies/stock/momentum_strategy.py` 或 `trader/strategies/stock/simple_long_strategy.py` 範例

3. **MIX**: 混合級別回測
   - 同時使用 TICK 和 DAY 資料
   - 目前尚未完全實作

4. **ALL**: 使用所有可用資料
   - 同時載入 TICK 和 DAY 資料 API
   - 適合需要同時使用多種資料來源的策略

在策略中設定回測級別：

```python
self.scale: str = Scale.DAY  # 或 Scale.TICK, Scale.MIX, Scale.ALL
```

## 回測流程

回測系統的執行流程如下：

1. **初始化策略**: 載入策略類別並初始化
2. **設定帳戶**: 建立虛擬帳戶，設定初始資金
3. **載入資料 API**: 根據回測級別載入對應的資料 API
4. **執行回測**: 逐日（或逐筆）執行策略邏輯
   - 檢查停損訊號
   - 檢查平倉訊號
   - 檢查開倉訊號
   - 執行訂單
5. **生成報告**: 計算績效指標並生成視覺化圖表

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

回測結果儲存路徑：`trader/backtest/results/<StrategyName>/`

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
# 執行回測模式，使用名為 "MomentumStrategy" 的策略
python run.py --strategy MomentumStrategy

# 執行實盤模式（目前尚未實作）
python run.py --mode live --strategy MomentumStrategy
```

### 注意事項

- Strategy Name 是 Class 的名稱
- 策略會自動從 `trader/strategies/stock/` 目錄載入
- 回測前請確認資料庫中有所需的資料（使用 `python -m tasks.update_db` 更新資料）
- 回測結果會儲存在 `trader/backtest/results/<StrategyName>/` 目錄

## 相關文檔

- [策略開發指南](../strategies/README.md)
- [專案 README](../../README.md)
- [API 文檔](../../docs/README.md)
