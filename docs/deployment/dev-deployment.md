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

策略名稱使用「類別名稱」，可先查看 `core/strategies/stock/`。

```bash
python run.py --strategy MomentumStrategy1
```

其他常見策略：

```bash
python run.py --strategy SimpleLongStrategy
python run.py --strategy MomentumStrategy1
```

## 4) 檢視結果

回測結果輸出在：

- `results/<StrategyName>/`

通常包含：

所有檔名都以策略名稱為前綴：

| 檔案 | 內容 |
|------|------|
| `<StrategyName>_trading_report.csv` | 已平倉交易的逐筆明細與損益 |
| `<StrategyName>_direction_summary.csv` | 多空分開的勝率、損益與成本統計 |
| `<StrategyName>_event_report.csv` | 強制回補、斷頭、拒單等事件計數 |
| `<StrategyName>_daily_equity.csv` | 含未實現損益的逐日權益序列 |
| `<StrategyName>_balance_curve.png` | 資產曲線 |
| `<StrategyName>_networth.png` | 策略與 benchmark（`0050`）淨值比較 |
| `<StrategyName>_mdd.png` | 最大回撤 |
| `<StrategyName>_everyday_profit.png` | 每日損益 |
| `<StrategyName>_everyday_equity_change.png` | 每日權益變化 |

日誌另外落在 `logs/backtest/`。

## 5) 常用維運指令

```bash
# 刪除指定日期的 price 資料
python -m tasks.delete_price_data --date 2025-07-13

# 將 broker_trading CSV 載入 tw_stock.db
python -m tasks.load_broker_trading_to_db
```
