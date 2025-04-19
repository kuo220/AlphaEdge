from pathlib import Path

"""
run.py

This is the main entry point of the trading system.
It is responsible for executing either backtesting or live trading based on the selected mode.

Modules and strategy logic are imported from the internal package structure.
Make sure to run this file from the project root to ensure all relative imports work correctly.

Example:
    python run.py          # default behavior (e.g., backtest)
    python run.py live     # switch to live trading mode
"""

# 假設你是從某個 .py 執行檔所在位置開始找
db_path = Path(__file__).resolve().parent / 'database'
print(db_path)