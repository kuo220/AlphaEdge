import datetime

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

"""
* 所有資料爬蟲起始日（除了 Tick）
- From: 2013 (ROC: 102)/1/1 ~ present

* 財報申報期限
一般行業：
- Q1：5月15日
- Q2：8月14日
- Q3：11月14日
- 年報：3月31日


* Shioaji 台股 ticks 資料時間表：
- From: 2020/03/02 ~ Today
- 目前資料庫資料時間：
- From 2020/04/01 ~ 2024/05/10

"""

start_date: datetime.date = datetime.date(2013, 1, 1)
end_date: datetime.date = datetime.date.today()



stock_tick_updater: StockTickUpdater = StockTickUpdater()
stock_chip_updater: StockChipUpdater = StockChipUpdater()
stock_price_updater: StockPriceUpdater = StockPriceUpdater()
financial_statement_updater: FinancialStatementUpdater = FinancialStatementUpdater()
monthly_revenue_report_updater: MonthlyRevenueReportUpdater = (
    MonthlyRevenueReportUpdater()
)


if __name__ == "__main__":
    pass
