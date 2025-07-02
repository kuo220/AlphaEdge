from abc import ABC, abstractmethod
import datetime

"""
Abstract base class for all crawlers that fetch data for a specific date.
Subclasses should implement the `crawl(date)` method.
"""

class BaseCrawler(ABC):
    """ Base Class of Data Crawler """

    def __init__(self):
        pass


    @abstractmethod
    def crawl(self, date: datetime.date) -> None:
        """ Crawl Data """
        pass