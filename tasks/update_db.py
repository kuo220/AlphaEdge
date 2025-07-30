from trader.pipeline.updaters.stock_tick_updater import StockTickUpdater
from trader.pipeline.updaters.stock_chip_updater import StockChipUpdater
from trader.pipeline.updaters.stock_price_updater import StockPriceUpdater
from trader.pipeline.updaters.financial_statement_updater import (
    FinancialStatementUpdater,
)
from trader.pipeline.updaters.monthly_revenue_report_updater import (
    MonthlyRevenueReportUpdater,
)


"""
This script is used to update the stock databases (including ticks) all at once.
"""


stock_tick_updater: StockTickUpdater = StockTickUpdater()
stock_chip_updater: StockChipUpdater = StockChipUpdater()
stock_price_updater: StockPriceUpdater = StockPriceUpdater()
financial_statement_updater: FinancialStatementUpdater = FinancialStatementUpdater()
monthly_revenue_report_updater: MonthlyRevenueReportUpdater = MonthlyRevenueReportUpdater()



if __name__ == "__main__":
    pass
