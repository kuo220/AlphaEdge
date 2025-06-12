import importlib
import pkgutil
import inspect
from typing import Dict, Type

from trader.strategies.stock import BaseStockStrategy
import trader.strategies.stock as stock_strategies_pkg



class StrategyLoader:
    """ 自動載入 strategies 資料夾下所有策略類別 """
    
    @staticmethod
    def load_all_stock_strategies() -> Dict[str, Type[BaseStockStrategy]]:
        """ 載入所有 stock 策略 """
        
        stock_strategies = {}
        
        for _, module_name, _ in pkgutil.iter_modules(stock_strategies_pkg.__path__):
            full_module_path = f"{stock_strategies_pkg.__name__}.{module_name}"
            module = importlib.import_module(full_module_path)

            for name, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, BaseStockStrategy) and obj is not BaseStockStrategy:
                    stock_strategies[name] = obj  # 用類別名稱當 key

        return stock_strategies