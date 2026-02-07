import time
from typing import Dict, List, Optional, Union

import requests
from fake_useragent import UserAgent
from loguru import logger
from requests.exceptions import ChunkedEncodingError, ReadTimeout

from trader.pipeline.utils import URLManager


class RequestUtils:
    """Requests utils"""

    # Session 建立與 HTTP 請求常數
    SESSION_INIT_MAX_ATTEMPTS: int = 10
    REQUEST_TIMEOUT_SECONDS: int = 10
    SESSION_RETRY_DELAY_SECONDS: int = 10
    HTTP_MAX_RETRIES: int = 3
    HTTP_RETRY_DELAY_SECONDS: int = 60

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

        for i in range(cls.SESSION_INIT_MAX_ATTEMPTS):
            try:
                logger.info(f"獲取新的Session 第 {i} 回合")
                headers: Dict[str, str] = cls.generate_random_header()
                ses: requests.Session = requests.Session()
                ses.get(url, headers=headers, timeout=cls.REQUEST_TIMEOUT_SECONDS)
                ses.headers.update(headers)
                logger.info("成功！")
                cls.ses = ses

                return ses
            except (ConnectionError, ReadTimeout) as error:
                logger.info(error)
                logger.info("失敗,10秒後重試")
                time.sleep(cls.SESSION_RETRY_DELAY_SECONDS)

        logger.info("您的網頁IP已經被證交所封鎖,請更新IP來獲取解鎖")
        logger.info(" 手機:開啟飛航模式,再關閉,即可獲得新的IP")
        logger.info("數據機：關閉然後重新打開數據機的電源")

    @classmethod
    def requests_get(cls, url: str, *args, **kwargs) -> Optional[requests.Response]:
        """使用共用 session 發送 GET 請求，內建重試機制"""

        if cls.ses is None:
            cls.find_best_session(url)

        for i in range(cls.HTTP_MAX_RETRIES):
            try:
                return cls.ses.get(url, timeout=cls.REQUEST_TIMEOUT_SECONDS, **kwargs)
            except (ConnectionError, ReadTimeout, ChunkedEncodingError) as error:
                logger.info(error)
                logger.info(
                    f"retry one more time after 60s {cls.HTTP_MAX_RETRIES - 1 - i} times left"
                )
                time.sleep(cls.HTTP_RETRY_DELAY_SECONDS)
                cls.find_best_session(url)
        return None

    @classmethod
    def requests_post(cls, url: str, *args, **kwargs) -> Optional[requests.Response]:
        """使用共用 session 發送 POST 請求，內建重試機制"""

        if cls.ses is None:
            cls.find_best_session(url)

        for i in range(cls.HTTP_MAX_RETRIES):
            try:
                return cls.ses.post(
                    url, timeout=cls.REQUEST_TIMEOUT_SECONDS, **kwargs
                )
            except (ConnectionError, ReadTimeout) as error:
                logger.info(error)
                logger.info(
                    f"retry one more time after 60s {cls.HTTP_MAX_RETRIES - 1 - i} times left"
                )
                time.sleep(cls.HTTP_RETRY_DELAY_SECONDS)
                cls.find_best_session(url)
        return None
