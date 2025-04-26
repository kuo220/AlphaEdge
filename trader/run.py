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

import threading
import time

def worker(name):
    print(f"{name} 開始工作")
    time.sleep(2)  # 模擬 I/O 延遲
    print(f"{name} 完成工作")

# 建立兩個 Thread
t1 = threading.Thread(target=worker, args=("線程1",))
t2 = threading.Thread(target=worker, args=("線程2",))

# 啟動線程
t1.start()
t2.start()

# 等待線程結束（可選）
t1.join()
t2.join()

print("主程式結束")
