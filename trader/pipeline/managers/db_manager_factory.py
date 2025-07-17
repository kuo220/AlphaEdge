from typing import Dict, Type

from trader.pipeline.managers import (
    BaseDatabaseManager,
    StockChipManager,
    StockTickManager,
)
from trader.pipeline.utils import InstrumentType, DataType


class DatabaseManagerFactory:
    """Factory class for selecting the appropriate database manager"""

    def __init__(self):
        self.db_managers: Dict[
            InstrumentType, Dict[DataType, Type[BaseDatabaseManager]]
        ] = {
            InstrumentType.STOCK: {
                DataType.CHIP: StockChipManager,
                DataType.TICK: StockTickManager,
            }
        }

    def get_manager(self, instrument: InstrumentType, data_type: DataType):
        """根據 Instrument 和 Data Type 選出適合的 Database Manager"""

        try:
            db_manager: BaseDatabaseManager = self.db_managers[instrument][data_type]
            return db_manager()

        except KeyError:
            raise ValueError(
                f"Invalid database selection for {instrument} -> {data_type}"
            )
