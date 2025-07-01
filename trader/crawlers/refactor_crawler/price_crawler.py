import pandas as pd
import logging as L
from io import StringIO
from datetime import date
from financials_api.crawlers.data_crawler import DataCrawler
from financials_api.crawlers.crawler_helpers import requests_post

class PriceCrawler(DataCrawler):
    def __init__(self):
        super().__init__()

    def crawl(self, date: date):
        listed = self.crawl_listed_companies(date)
        otc = self.crawl_otc_companies(date)
        return listed.append(otc)

    def crawl_listed_companies(self, date: date):
        """ listed companies(上市) """
        datestr = date.strftime('%Y%m%d')

        try:
            url = 'https://www.twse.com.tw/exchangeReport/MI_INDEX?response=csv&date=' + datestr + '&type=ALLBUT0999'
            r = requests_post(url)
            L.info("上市", url)
        except Exception as e:
            L.info('**WARRN: cannot get stock price at', datestr)
            L.info(e)
            return None

        content = r.text.replace('=', '')

        lines = content.split('\n')
        lines = list(filter(lambda l: len(l.split('",')) > 10, lines))
        content = "\n".join(lines)

        if content == '':
            return None

        df = pd.read_csv(StringIO(content))
        df = df.astype(str)
        df = df.apply(lambda s: s.str.replace(',', ''))
        df['date'] = pd.to_datetime(date)
        df = df.rename(columns={'證券代號': 'stock_id'})
        df = df.set_index(['stock_id', 'date'])

        df = df.apply(lambda s: pd.to_numeric(s, errors='coerce'))
        df = df[df.columns[df.isnull().all() == False]]
        df = df[~df['收盤價'].isnull()]

        # df1 = crawl_price_cttc(date)

        # df = df.append(df1)

        return df

    def crawl_otc_companies(self, date: date):
        """ over-the-counter(上櫃) """
        # 上櫃資料從96/7/2以後才提供
        # 109/4/30以後csv檔的column不一樣
        datestr = date.strftime('%Y%m%d')

        try:
            url = 'https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php?l=zh-tw&o=csv&d=' + str(
                date.year - 1911) + "/" + datestr[4:6] + "/" + datestr[6:] + '&se=EW&s=0,asc,0'
            r = requests_post(url)
            L.info("上櫃", url)
        except Exception as e:
            L.info('**WARRN: cannot get stock price at', datestr)
            L.info(e)
            return None

        content = r.text.replace('=', '')

        lines = content.split('\n')
        lines = list(filter(lambda l: len(l.split('",')) > 10, lines))
        content = "\n".join(lines)

        if content == '':
            return None

        df = pd.read_csv(StringIO(content))
        df = df.astype(str)
        df = df.apply(lambda s: s.str.replace(',', ''))
        if datestr >= str(20200430):
            df.drop(df.columns[[14, 15, 16]],
                    axis=1,
                    inplace=True)
            df.columns = ["stock_id", "證卷名稱", "收盤價", "漲跌價差", "開盤價", "最高價", "最低價", "成交股數",
                        "成交金額", "成交筆數", "最後揭示買價", "最後揭示買量", "最後揭示賣價", "最後揭示賣量"]
        else:
            df.drop(df.columns[[12, 13, 14]],
                    axis=1,
                    inplace=True)
            df.columns = ["stock_id", "證卷名稱", "收盤價", "漲跌價差", "開盤價", "最高價", "最低價", "成交股數",
                        "成交金額", "成交筆數", "最後揭示買價", "最後揭示賣價"]

        df['date'] = pd.to_datetime(date)

        df = df.set_index(['stock_id', 'date'])

        df = df.apply(lambda s: pd.to_numeric(s, errors='coerce'))
        df = df[df.columns[df.isnull().all() == False]]
        df = df[~df['收盤價'].isnull()]

        return df

if __name__ == "__main__":
    crawler = PriceCrawler()
    df = crawler.crawl(date=date(2025, 3, 17))
    print(df)
    print(df.loc[("0050", "2025-03-17")])