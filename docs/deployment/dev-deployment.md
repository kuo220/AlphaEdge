# 開發部署（Dev Deployment）

此文件以目前 `AlphaEdge` 實際程式入口為準，不依賴 `docs_2` 的 collector / compose 架構。

## 1) 啟用環境

```bash
source .venv/bin/activate
```

## 2) 更新資料庫

### 全量（不含 tick，預設）

```bash
python -m tasks.update_db
# 或
python -m tasks.update_db --target no_tick
```

### 指定資料類型

```bash
python -m tasks.update_db --target chip price
python -m tasks.update_db --target fs mrr
python -m tasks.update_db --target finmind
```

### 更新 tick（需 DolphinDB 設定）

```bash
python -m tasks.update_db --target tick
```

## 3) 執行回測

策略名稱使用「類別名稱」，可先查看 `trader/strategies/stock/`。

```bash
python run.py --strategy MomentumStrategy
```

其他常見策略：

```bash
python run.py --strategy SimpleLongStrategy
python run.py --strategy MomentumTickStrategy
```

## 4) 檢視結果

回測結果輸出在：

- `trader/backtest/results/<StrategyName>/`

通常包含：

- `trading_report.csv`
- `balance_curve.png`
- `balance_and_benchmark_curve.png`
- `balance_mdd.png`
- `everyday_profit.png`
- `<StrategyName>.log`

## 5) 常用維運指令

```bash
# 刪除指定日期的 price 資料
python -m tasks.delete_price_data --date 2025-07-13

# 將 broker_trading CSV 載入 data.db
python -m tasks.load_broker_trading_to_db
```
