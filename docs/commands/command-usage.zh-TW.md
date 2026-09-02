# 指令教學

本文件整理常用執行指令，包含資料更新（`tasks.update_db`）與回測（`run.py`）。

## 資料更新：`python -m tasks.update_db`

### 功能說明

`tasks.update_db` 是資料更新系統入口，透過 `--target` 指定要更新的資料類型，可單一或多選。
未指定 `--target` 時，預設為 `no_tick`（更新全部資料但不含 tick）。

### 參數

- `--target <target> [<target> ...]`：欲更新的資料類型，可指定一個或多個。

### Target 對照表


| 選項                        | 說明                            |
| ------------------------- | ----------------------------- |
| `tick`                    | 逐筆成交（Shioaji ticks）           |
| `chip`                    | 三大法人籌碼                        |
| `price`                   | 收盤價                           |
| `futures_price`           | 台期貨每日行情（寫入 `tw_futures.db`；商品見 `FUTURES_TARGET_PRODUCTS`） |
| `futures_stock_universe`  | 股票期貨標的池（寫入 `tw_futures.db`；每次執行留下一份當日快照） |
| `futures_stock_price`     | 股票期貨行情（商品清單取自標的池，預設只爬流動性前 N 檔） |
| `futures_continuous`      | 台期貨連續合約（由 `futures_price_daily` 建出，不連網路） |
| `futures_margin`          | 台期貨保證金（變動序列，寫入 `tw_futures.db`） |
| `futures_chip`            | 台期貨籌碼（三大法人、大額交易人、選擇權 PCR） |
| `futures_tick`            | 台期貨逐筆成交（Shioaji → DolphinDB；需 `[tick]` 相依與金鑰） |
| `margin`                  | 信用交易（融資融券餘額）              |
| `dividend`                | 除權除息計算結果表（含還原係數、現金股利） |
| `fs`                      | 財報（Financial Statement）       |
| `mrr`                     | 月營收報表（Monthly Revenue Report） |
| `finmind`                 | 全部 FinMind（台股總覽 + 證券商 + 券商分點） |
| `stock_info`              | FinMind 台股總覽（不含權證）            |
| `stock_info_with_warrant` | FinMind 台股總覽（含權證）             |
| `broker_info`             | FinMind 證券商資訊                 |
| `broker_trading`          | FinMind 券商分點統計                |
| `all`                     | 全部資料（含 tick）                  |
| `no_tick`                 | 全部資料（不含 `tick`，預設）。⚠️ **不排除 `futures_tick`**（見健檢 F-078） |


### 單一 target 範例

```bash
# 逐筆成交
python -m tasks.update_db --target tick

# 三大法人籌碼
python -m tasks.update_db --target chip

# 收盤價
python -m tasks.update_db --target price

# 信用交易（融資融券餘額）
python -m tasks.update_db --target margin

# 除權除息計算結果表（上市走證交所、上櫃走櫃買中心，皆為全歷史）
python -m tasks.update_db --target dividend

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

