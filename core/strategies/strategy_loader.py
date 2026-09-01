import importlib
import inspect
import pkgutil
from types import ModuleType
from typing import Dict, Type

import core.strategies as strategies_pkg
from core.strategies.base import BaseStrategy

"""StrategyLoader: 自動載入 core/strategies/ 下所有市場的策略類別"""


class StrategyLoader:
    """自動載入 strategies 資料夾下所有策略類別"""

    @staticmethod
    def load_strategies() -> Dict[str, Type[BaseStrategy]]:
        """
        - Description:
            掃描 `core/strategies/` 下的所有商品類別子套件並載入其中的策略

            原本寫死只掃 `stock` 子套件；改為逐一掃描所有子套件後，
            新增一個商品類別（如 `core/strategies/futures/`）不需要修改本檔案。
        - Return:
            - Dict[str, Type[BaseStrategy]]
                類別名稱 → 策略類別
        """

        strategies: Dict[str, Type[BaseStrategy]] = {}

        for _, instrument_name, is_pkg in pkgutil.iter_modules(strategies_pkg.__path__):
            if not is_pkg:
                continue

            instrument_pkg: ModuleType = importlib.import_module(
                f"{strategies_pkg.__name__}.{instrument_name}"
            )

            for _, module_name, _ in pkgutil.iter_modules(instrument_pkg.__path__):
                module: ModuleType = importlib.import_module(
                    f"{instrument_pkg.__name__}.{module_name}"
                )

                for name, obj in inspect.getmembers(module, inspect.isclass):
                    # 只收「在該模組內定義」且「可實例化」的策略：
                    # 抽象基底（BaseStrategy／BaseStockStrategy）與被 import 進來的
                    # 其他模組類別都不算策略
                    if (
                        issubclass(obj, BaseStrategy)
                        and not inspect.isabstract(obj)
                        and obj.__module__ == module.__name__
                    ):
                        strategies[name] = obj  # 用類別名稱當 key

        return strategies

    @staticmethod
    def load_stock_strategies() -> Dict[str, Type[BaseStrategy]]:
        """相容別名：既有呼叫端沿用此名稱，行為等同 load_strategies()"""

        return StrategyLoader.load_strategies()
