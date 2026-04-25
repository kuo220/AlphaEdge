# 指令教學

本文件整理常用執行指令，包含資料更新（`tasks.update_db`）與回測（`run.py`）。

## 資料更新：`python -m tasks.update_db`

### 功能說明

`tasks.update_db` 是資料更新系統入口，透過 `--target` 指定要更新的資料類型，可單一或多選。
未指定 `--target` 時，預設為 `no_tick`（更新全部資料但不含 tick）。

### 參數

- `--target <target> [<target> ...]`：欲更新的資料類型，可指定一個或多個。

### Target 對照表

| 選項 | 說明 |
| --- | --- |
| `tick` | 逐筆成交（Shioaji ticks） |
| `chip` | 三大法人籌碼 |
| `price` | 收盤價 |
| `fs` | 財報（Financial Statement） |
| `mrr` | 月營收報表（Monthly Revenue Report） |
| `finmind` | 全部 FinMind（台股總覽 + 證券商 + 券商分點） |
| `stock_info` | FinMind 台股總覽（不含權證） |
| `stock_info_with_warrant` | FinMind 台股總覽（含權證） |
| `broker_info` | FinMind 證券商資訊 |
| `broker_trading` | FinMind 券商分點統計 |
| `all` | 全部資料（含 tick） |
| `no_tick` | 全部資料（不含 tick，預設） |

### 單一 target 範例

```bash
# 逐筆成交
python -m tasks.update_db --target tick

# 三大法人籌碼
python -m tasks.update_db --target chip

# 收盤價
python -m tasks.update_db --target price

# 財報
python -m tasks.update_db --target fs

# 月營收報表
python -m tasks.update_db --target mrr

# 全部 FinMind（台股總覽 + 證券商 + 券商分點）
python -m tasks.update_db --target finmind

# FinMind 台股總覽（不含權證）
python -m tasks.update_db --target stock_info

# FinMind 台股總覽（含權證）
python -m tasks.update_db --target stock_info_with_warrant

# FinMind 證券商資訊
python -m tasks.update_db --target broker_info

# FinMind 券商分點統計
python -m tasks.update_db --target broker_trading

# 全部資料（含 tick）
python -m tasks.update_db --target all

# 全部資料（不含 tick，等同預設）
python -m tasks.update_db --target no_tick

# 預設（等同 no_tick）
python -m tasks.update_db
```

### 多個 target 組合範例

```bash
python -m tasks.update_db --target chip price
python -m tasks.update_db --target chip price tick
python -m tasks.update_db --target stock_info broker_trading
```

## 回測：`python run.py --strategy <StrategyClassName>`

將 `<StrategyClassName>` 替換為你的策略類別名稱。

```bash
python run.py --strategy <StrategyClassName>
```
