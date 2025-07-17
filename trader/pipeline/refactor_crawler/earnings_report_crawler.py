import pandas as pd
import logging as L
from io import StringIO
from datetime import date
from financials_api.crawlers.data_crawler import DataCrawler
from financials_api.crawlers.crawler_helpers import generate_random_header, requests_get


class MonthlyEarningsReportCrawler(DataCrawler):
    def __init__(self):
        super().__init__()

    def crawl(self, date: date):
        listed = self.crawl_listed_companies(date)
        otc = self.crawl_otc_companies(date)
        return listed.append(otc)

    def crawl_listed_companies(self, date_: date):
        assert date_ not in [date(2011, 2, 10), date(2012, 1, 10)]
        url = f"https://mopsov.twse.com.tw/nas/t21/sii/t21sc03_{date_.year - 1911}_{date_.month}.html"
        L.info(f"上市: {url}")

        # 偽瀏覽器
        headers = generate_random_header()

        # 下載該年月的網站，並用pandas轉換成 dataframe
        try:
            r = requests_get(url, headers=headers, verify="./certs.cer")
            r.encoding = "big5"
        except:
            L.warning("**WARRN: requests cannot get html")
            return None

        try:
            html_df = pd.read_html(StringIO(r.text))
        except:
            L.warning("**WARRN: Pandas cannot find any table in the HTML file")
            return None

        # 處理一下資料
        if html_df[0].shape[0] > 500:
            df = html_df[0].copy()
        else:
            df = pd.concat(
                [df for df in html_df if df.shape[1] <= 11 and df.shape[1] > 5]
            )
        # 超靠北公司代號陷阱
        try:
            df.rename(columns={"公司 代號": "公司代號"}, inplace=True)
        except:
            pass
        try:
            df.rename(columns={"上月比較 增減(%)": "上月比較增減(%)"}, inplace=True)
        except:
            pass
        try:
            df.rename(columns={"去年同月 增減(%)": "去年同月增減(%)"}, inplace=True)
        except:
            pass
        try:
            df.rename(columns={"前期比較 增減(%)": "前期比較增減(%)"}, inplace=True)
        except:
            pass

        if "levels" in dir(df.columns):
            df.columns = df.columns.get_level_values(1)
        else:
            df = df[list(range(0, 10))]
            column_index = df.index[(df[0] == "公司代號")][0]
            df.columns = df.iloc[column_index]

        df["當月營收"] = pd.to_numeric(df["當月營收"], "coerce")
        df = df[~df["當月營收"].isnull()]
        df = df[df["公司代號"] != "合計"]
        df = df[df["公司代號"] != "總計"]

        next_month = date(
            date_.year + int(date_.month / 12), ((date_.month % 12) + 1), 10
        )
        df["date"] = pd.to_datetime(next_month)

        df = df.rename(columns={"公司代號": "stock_id"})
        df = df.set_index(["stock_id", "date"])
        df = df.apply(lambda s: pd.to_numeric(s, errors="coerce"))
        df = df[df.columns[df.isnull().all() == False]]

        return df

    def crawl_otc_companies(self, date_: date):
        url = f"https://mopsov.twse.com.tw/nas/t21/otc/t21sc03_{date_.year - 1911}_{date_.month}.html"
        L.info(f"上櫃: {url}")

        # 偽瀏覽器
        headers = generate_random_header()

        # 下載該年月的網站，並用pandas轉換成 dataframe
        try:
            r = requests_get(url, headers=headers, verify="./certs.cer")
            r.encoding = "big5"
        except:
            L.warning("**WARRN: requests cannot get html")
            return None

        try:
            html_df = pd.read_html(StringIO(r.text))
        except:
            L.warning("**WARRN: Pandas cannot find any table in the HTML file")
            return None

        # 處理一下資料
        if html_df[0].shape[0] > 500:
            df = html_df[0].copy()
        else:
            df = pd.concat(
                [df for df in html_df if df.shape[1] <= 11 and df.shape[1] > 5]
            )
        # 超靠北公司代號陷阱
        try:
            df.rename(columns={"公司 代號": "公司代號"}, inplace=True)
        except:
            pass
        try:
            df.rename(columns={"上月比較 增減(%)": "上月比較增減(%)"}, inplace=True)
        except:
            pass
        try:
            df.rename(columns={"去年同月 增減(%)": "去年同月增減(%)"}, inplace=True)
        except:
            pass
        try:
            df.rename(columns={"前期比較 增減(%)": "前期比較增減(%)"}, inplace=True)
        except:
            pass
        if "levels" in dir(df.columns):
            df.columns = df.columns.get_level_values(1)
        else:
            df = df[list(range(0, 10))]
            column_index = df.index[(df[0] == "公司代號")][0]
            df.columns = df.iloc[column_index]

        df["當月營收"] = pd.to_numeric(df["當月營收"], "coerce")
        df = df[~df["當月營收"].isnull()]
        df = df[df["公司代號"] != "合計"]
        df = df[df["公司代號"] != "總計"]

        next_month = date(
            date_.year + int(date_.month / 12), ((date_.month % 12) + 1), 10
        )
        df["date"] = pd.to_datetime(next_month)

        df = df.rename(columns={"公司代號": "stock_id"})
        df = df.set_index(["stock_id", "date"])
        df = df.apply(lambda s: pd.to_numeric(s, errors="coerce"))
        df = df[df.columns[df.isnull().all() == False]]

        return df


if __name__ == "__main__":
    crawler = MonthlyEarningsReportCrawler()
    df = crawler.crawl(date=date(2024, 4, 10))
    print(df)
    # print(df.loc[("2330", "2024-05-10")])
