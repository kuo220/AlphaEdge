from .managers.stock_chip_manager import StockChipManager


class Updater:
    """ 更新 Database 的 API """

    def __init__(self):
        self.stock_chip_updater: StockChipManager = StockChipManager()


    def update_stock_chip(self):
        pass