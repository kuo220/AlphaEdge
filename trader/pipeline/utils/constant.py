from enum import Enum


class InstrumentType(str, Enum):
    STOCK = "Stock"
    FUTURE = "Future"
    OPTION = "Option"


class DataType(str, Enum):
    PRICE = "Price"
    CHIP = "Chip"
    TICK = "Tick"
