import os
import shutil
import zipfile
import logging as L
from datetime import date
from financials_api.crawlers.data_crawler import DataCrawler
from financials_api.crawlers.crawler_helpers import FiscalDate
from financials_api.crawlers.crawler_helpers import download_url, to_fiscal_date


class FinancialStatementCrawler(DataCrawler):
    def __init__(self):
        super().__init__()
        root_dir = os.getcwd()
        self.temp_file_path = os.path.join(root_dir, "temp.zip")
        self.local_html_dir = os.path.join(root_dir, "data", "financial_statement")

    def crawl(self, date: date):
        fiscal_date = to_fiscal_date(date)
        self.download_from_mops(fiscal_date)
        self.unzip_and_filter_htmls(fiscal_date)

    def download_from_mops(self, fiscal_date: FiscalDate):
        """download data from Market Observation Post System"""
        year, season = fiscal_date.year, fiscal_date.quarter
        assert year >= 2019
        url = (
            f"https://mopsov.twse.com.tw/server-java/FileDownLoad?step=9&fileName="
            f"tifrs-{year}Q{season}.zip&filePath=/home/html/nas/ifrs/{year}/"
        )
        L.info(f"downloading from {url} to {self.temp_file_path}")
        download_url(url, self.temp_file_path)
        L.info("finish download")

    def unzip_and_filter_htmls(self, fiscal_date: FiscalDate):
        path = os.path.join(
            self.local_html_dir, f"{fiscal_date.year}{fiscal_date.quarter}"
        )

        if os.path.isdir(path):
            shutil.rmtree(path)

        L.info("create new dir")

        zipfiles = zipfile.ZipFile(open(self.temp_file_path, "rb"))
        zipfiles.extractall(path=path)

        L.info("extract all files")

        fnames = [f for f in os.listdir(path) if f[-5:] == ".html"]
        fnames = sorted(fnames)

        newfnames = [f.split("-")[5] + ".html" for f in fnames]

        for old_fname, new_fname in zip(fnames, newfnames):
            ticker_name = os.path.splitext(os.path.basename(new_fname))[0]
            if len(ticker_name) != 4:
                # [CHECK] bypass ticker such as 000538 for some reason
                L.info(f"remove strange code id {new_fname}")
                os.remove(os.path.join(path, old_fname))
                continue

            if not os.path.exists(os.path.join(path, new_fname)):
                os.rename(os.path.join(path, old_fname), os.path.join(path, new_fname))
            else:
                os.remove(os.path.join(path, old_fname))


if __name__ == "__main__":
    L.basicConfig(level=L.INFO)
    crawler = FinancialStatementCrawler()
    df = crawler.crawl(date=date(2025, 3, 17))
