import time
import requests
from loguru import logger
from fake_useragent import UserAgent
from requests.exceptions import ReadTimeout, ChunkedEncodingError
from typing import List, Dict, Optional, Union

from trader.pipeline.utils import URLManager


class RequestUtils:
    """Requests utils"""

    ses: Optional[requests.Session] = None  # Session

    @staticmethod
    def generate_random_header() -> Dict[str, str]:
        """產生隨機 headers 避免爬蟲被鎖"""

        ua: UserAgent = UserAgent()
        user_agent: str = ua.random
        headers: Dict[str, str] = {
            "Accept": "*/*",
            "Connection": "keep-alive",
            "User-Agent": user_agent,
        }
        return headers

    @classmethod
    def find_best_session(cls, url: str) -> Optional[requests.Session]:
        """嘗試建立可用的 requests.Session 連線"""

        for i in range(10):
            try:
                logger.info("獲取新的Session 第", i, "回合")
                headers = cls.generate_random_header()
                ses = requests.Session()
                ses.get(url, headers=headers, timeout=10)
                ses.headers.update(headers)
                logger.info("成功！")
                cls.ses = ses

                return ses
            except (ConnectionError, ReadTimeout) as error:
                logger.info(error)
                logger.info("失敗,10秒後重試")
                time.sleep(10)

        logger.info("您的網頁IP已經被證交所封鎖,請更新IP來獲取解鎖")
        logger.info(" 手機:開啟飛航模式,再關閉,即可獲得新的IP")
        logger.info("數據機：關閉然後重新打開數據機的電源")

    @classmethod
    def requests_get(cls, url: str, *args, **kwargs) -> Optional[requests.Response]:
        """使用共用 session 發送 GET 請求，內建重試機制"""

        if cls.ses is None:
            cls.find_best_session(url)

        for i in range(3):
            try:
                return cls.ses.get(url, timeout=10, **kwargs)
            except (ConnectionError, ReadTimeout, ChunkedEncodingError) as error:
                logger.info(error)
                logger.info(f"retry one more time after 60s {2 - i} times left")
                time.sleep(60)
                cls.find_best_session()
        return None

    @classmethod
    def requests_post(cls, url: str, *args, **kwargs) -> Optional[requests.Response]:
        """使用共用 session 發送 POST 請求，內建重試機制"""

        if cls.ses is None:
            cls.find_best_session(url)

        for i in range(3):
            try:
                return cls.ses.post(url, timeout=10, **kwargs)
            except (ConnectionError, ReadTimeout) as error:
                logger.info(error)
                logger.info(f"retry one more time after 60s {2 - i} times left")
                time.sleep(60)
                cls.find_best_session()
        return None
