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
| `fs` | Financial statements |
| `mrr` | Monthly revenue report |
| `finmind` | All FinMind datasets (stock info + brokers + broker trading) |
| `stock_info` | FinMind stock info (without warrants) |
| `stock_info_with_warrant` | FinMind stock info (with warrants) |
| `broker_info` | FinMind broker info |
| `broker_trading` | FinMind broker trading stats |
| `all` | All datasets (including tick) |
| `no_tick` | All datasets except tick (default) |

### Single Target Examples

```bash
# tick-by-tick trades
python -m tasks.update_db --target tick

# institutional chip data
python -m tasks.update_db --target chip

# closing prices
python -m tasks.update_db --target price

# financial statements
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
