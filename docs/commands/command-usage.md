# Command Usage Guide

This document collects common runtime commands, including data updates (`tasks.update_db`) and backtesting (`run.py`).

## Data Update: `python -m tasks.update_db`

### Overview

`tasks.update_db` is the entrypoint of the data update pipeline. Use `--target` to choose one or more update targets.
If `--target` is omitted, the default is `no_tick` (all updates except tick data).

### Parameter

- `--target <target> [<target> ...]`: one or multiple update targets.

### Target Reference

| Option | Description |
| --- | --- |
| `tick` | Tick-by-tick trades (Shioaji ticks) |
| `chip` | Institutional chip data |
| `price` | Closing prices |
| `futures_price` | TAIFEX daily futures quotes（寫入 `tw_futures.db`；商品見 `FUTURES_TARGET_PRODUCTS`）|
| `futures_stock_universe` | 股票期貨標的池（寫入 `tw_futures.db`；每次執行留下一份當日快照）|
| `futures_stock_price` | 股票期貨行情（商品清單取自標的池，預設只爬流動性前 N 檔）|
| `futures_continuous` | 台期貨連續合約（由 `futures_price_daily` 建出，不連網路，整段重建）|
| `futures_margin` | 台期貨保證金（變動序列，寫入 `tw_futures.db`）|
| `futures_chip` | 台期貨籌碼（三大法人、大額交易人、選擇權 PCR）|
| `futures_tick` | 台期貨逐筆成交（Shioaji → DolphinDB；需 `[tick]` 相依與金鑰）|
| `margin` | Margin trading balances (financing / short-selling balances) |
| `dividend` | Ex-dividend / ex-rights table (adjustment factors + cash dividends) |
| `fs` | Financial statements（含權益變動表；該表逐檔查詢，首次回補以小時計，見下方說明） |
| `mrr` | Monthly revenue report |
| `finmind` | All FinMind datasets (stock info + brokers + broker trading) |
| `stock_info` | FinMind stock info (without warrants) |
| `stock_info_with_warrant` | FinMind stock info (with warrants) |
| `broker_info` | FinMind broker info |
| `broker_trading` | FinMind broker trading stats |
| `all` | All datasets (including tick) |
| `no_tick` | All datasets except `tick` (default). ⚠️ `futures_tick` is **not** excluded (見健檢 F-078) |

### Single Target Examples

```bash
# tick-by-tick trades
python -m tasks.update_db --target tick

# institutional chip data
python -m tasks.update_db --target chip

# closing prices
python -m tasks.update_db --target price

# margin trading balances
python -m tasks.update_db --target margin

# TAIFEX daily futures quotes（寫入 tw_futures.db，非 tw_stock.db）
# 一次只能查一個商品、日盤與夜盤要分開查，故請求數 = 商品數 × 2 × 交易日數；
# 起點為 DEFAULT_FUTURES_START_DATE（2015-01-01），單檔 TX 首次回補約 6,100 次請求。
python -m tasks.update_db --target futures_price

# 股票期貨標的池（寫入 tw_futures.db）
# 整份清單一次 GET 就結束，同一天重跑不會產生第二份快照。
# 來源沒有掛牌日／下市日欄位，兩者由快照序列差分推得，故建議每日更新——
# 快照愈稀疏，推出來的日期誤差愈大。
# 下游要取商品清單一律用 FuturesStockUniverseUpdater.get_active_products()，
# 不要另外手寫清單。
python -m tasks.update_db --target futures_stock_universe

# ex-dividend / ex-rights table (TWSE for listed, TPEx for OTC; full history)
python -m tasks.update_db --target dividend

# financial statements
# 四張報表中的權益變動表（equity_change）是逐檔查詢：一個年季約 2,000 次請求、約 0.9 小時，
# 歷史尚有 55 個年季未回補，整段跑完約 50 小時。中斷後重跑只補差集（resume 以「該年季
# 已入庫的 stock_id」為準），要分段跑就直接呼叫 update_equity_changes() 指定較窄的年季。
# 資料形狀與已知限制見 docs/pipeline/equity-change.md。
python -m tasks.update_db --target fs

# monthly revenue report
python -m tasks.update_db --target mrr

# all FinMind datasets
python -m tasks.update_db --target finmind

# FinMind stock info (without warrants)
python -m tasks.update_db --target stock_info

# FinMind stock info (with warrants)
python -m tasks.update_db --target stock_info_with_warrant

# FinMind broker info
python -m tasks.update_db --target broker_info

# FinMind broker trading stats
python -m tasks.update_db --target broker_trading

# all datasets (including tick)
python -m tasks.update_db --target all

# all datasets except tick (same as default)
python -m tasks.update_db --target no_tick

# default behavior (same as no_tick)
python -m tasks.update_db
```

### Multi-Target Examples

```bash
python -m tasks.update_db --target chip price
python -m tasks.update_db --target chip price tick
python -m tasks.update_db --target stock_info broker_trading
```

## Backtest: `python run.py --strategy <StrategyClassName>`

Replace `<StrategyClassName>` with your strategy class name.

```bash
python run.py --strategy <StrategyClassName>
```
