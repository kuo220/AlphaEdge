from core.pipeline.tw.loaders.finmind import (
    broker_info_loader,
    broker_trading_loader,
    schema,
    stock_info_loader,
)

"""
FinMind 入庫流程按資料集分檔

各子模組一律是**吃 `conn` 的模組層級函式**，不自己持有連線：`FinMindLoader`
的 `connect()`／`disconnect()` 會換掉 `self.conn`，子模組若把連線存成自己的屬性，
斷線重連後就會拿著一個已關閉的連線。

對外的單一入口仍是 `core.pipeline.tw.loaders.finmind_loader.FinMindLoader`（門面）。
"""

__all__ = [
    "broker_info_loader",
    "broker_trading_loader",
    "schema",
    "stock_info_loader",
]
