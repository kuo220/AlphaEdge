from abc import ABC, abstractmethod

"""Abstract base class for all crawlers that fetch data for a specific date"""


class BaseDataCrawler(ABC):
    """Base Class of Data Crawler"""

    def __init__(self):
        pass

    @abstractmethod
    def setup(self, *args, **kwargs) -> None:
        """Set Up the Config of Crawler"""
        pass

    @abstractmethod
    def crawl(self, *args, **kwargs) -> None:
        """Crawl Data"""
        pass
