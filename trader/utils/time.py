import datetime
from typing import List
from dateutil.rrule import rrule, DAILY, MONTHLY
import shioaji as sj
from shioaji.data import Ticks


class TimeUtils:
    """處理各式關於時間問題的工具"""

    @staticmethod
    def get_last_trading_date(api: sj.Shioaji, date: datetime.date) -> datetime.date:
        """取得前一個交易日日期"""

        stock_test: str = "2330"  # 以 2330 判斷前一天是否有開盤
        last_trading_date: datetime.date = date - datetime.timedelta(days=1)
        tick: Ticks = api.ticks(
            contract=api.Contracts.Stocks[stock_test],
            date=last_trading_date.strftime("%Y-%m-%d"),
            query_type=sj.constant.TicksQueryType.LastCount,
            last_cnt=1,
        )

        while len(tick.close) == 0:
            last_trading_date = last_trading_date - datetime.timedelta(days=1)
            tick = api.ticks(
                contract=api.Contracts.Stocks[stock_test],
                date=last_trading_date.strftime("%Y-%m-%d"),
                query_type=sj.constant.TicksQueryType.LastCount,
                last_cnt=1,
            )
        return last_trading_date

    @staticmethod
    def get_time_diff_in_sec(
        start_time: datetime.datetime, end_time: datetime.datetime
    ) -> float:
        """計算兩時間的時間差（秒數）"""

        time_diff: float = (end_time - start_time).total_seconds()
        time_diff = time_diff if time_diff >= 0 else 0
        return time_diff

    @staticmethod
    def convert_ad_to_roc_year(year: int | str) -> str:
        """將西元年轉換成民國年"""

        try:
            year_int = int(year)
            if year_int < 1912:
                raise ValueError("民國元年從 1912 年開始，請輸入有效的西元年份")
            return str(year_int - 1911)
        except (ValueError, TypeError):
            raise ValueError(f"無效的年份輸入：{year}")

    @staticmethod
    def convert_roc_to_ad_year(year: int | str) -> str:
        """將民國年轉為西元年"""

        try:
            return int(year) + 1911
        except (ValueError, TypeError):
            raise ValueError(f"無效的年份輸入：{year}")

    @staticmethod
    def generate_date_range(
        start_date: datetime.date, end_date: datetime.date
    ) -> List[datetime.date]:
        """產生從 start_date 到 end_date 的每日日期清單"""
        return [dt.date() for dt in rrule(DAILY, dtstart=start_date, until=end_date)]

    @staticmethod
    def generate_month_range(
        start: int | datetime.date, end: int | datetime.date
    ) -> List[int | datetime.date]:
        """
        產生從 start_date 到 end_date 的每月清單（取每月的起始日）
        - 若 start/end 為 datetime.date：返回從 start 到 end 的每月日期列表（取每月的起始日）
        - 若 start/end 為 int：返回從 start 年到 end 年的 12 個月份（1~12）為單位的 flat list
        """

        if isinstance(start, int) and isinstance(end, int):
            if not (1 <= start <= 12 and 1 <= end <= 12):
                raise ValueError("月份應在 1 到 12 之間")
            return list(range(start, end + 1))
        elif isinstance(start, datetime.date) and isinstance(end, datetime.date):
            return [dt.date() for dt in rrule(MONTHLY, dtstart=start, until=end)]
        else:
            raise ValueError("start 和 end 必須是 int 或 datetime.date")

    @staticmethod
    def generate_year_range(start_year: int, end_year: int) -> List[int]:
        """產生從 start_year 到 end_year 的所有年份"""
        return [year for year in range(start_year, end_year + 1)]

    @staticmethod
    def generate_season_range(start_season: int, end_season: int) -> List[int]:
        """產生從 start_season 到 end_season 的所有季度"""
        return [season for season in range(start_season, end_season + 1)]

    @staticmethod
    def format_date(date: datetime.date, sep: str = "") -> str:
        """Format date as 'YYYY{sep}MM{sep}DD'"""
        return date.strftime(f"%Y{sep}%m{sep}%d")
