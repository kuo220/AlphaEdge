import sqlite3
import pandas as pd
import os
from pathlib import Path
import datetime
import requests
from crawler.shared_list import table_without_stockid



class Data():
    
    def __init__(self, date = datetime.datetime.now().date()):

        self.macro_eco_db = table_without_stockid

        # 開啟資料庫
        data_path = Path(__file__).resolve().parents[3] / 'Data' / 'data.db'
        
        self.conn = sqlite3.connect(str(data_path))
        cursor = self.conn.execute('SELECT name FROM sqlite_master WHERE type = "table"')

        # 找到所有的table名稱
        table_names = [t[0] for t in list(cursor)]

        # 找到所有的column名稱，對應到的table名稱
        self.col2table = {}
        for tname in table_names:

            # 獲取所有column名稱
            c = self.conn.execute('PRAGMA table_info(' + tname + ');')
            for cname in [i[1] for i in list(c)]:

                # 將column名稱對應到的table名稱assign到self.col2table中
                if cname not in self.col2table:
                    self.col2table[cname] = [tname]
                else:
                    self.col2table[cname].append(tname)
        # 初始self.date（使用data.get時，可以獲得self.date以前的所有資料（以防拿到未來數據）
        self.date = date
        
        # 假如self.cache是true的話，
        # 使用data.get的資料，會被儲存在self.data中，之後再呼叫data.get時，就不需要從資料庫裡面找，
        # 直接調用self.data中的資料即可
        self.cache = False
        self.data = {}
        
        # 先將每個table的所有日期都拿出來
        self.dates = {}

        # 對於每個table，都將所有資料的日期取出
        for tname in table_names:
            c = self.conn.execute('PRAGMA table_info(' + tname + ');')
            cnames = [i[1] for i in list(c)]
            if 'date' in cnames:
                if tname == 'price':
                    # 假如table是股價的話，則觀察這三檔股票的日期即可（不用所有股票日期都觀察，節省速度）
                    s1 = ("""SELECT DISTINCT date FROM %s where stock_id='0050'"""%('price'))
                    s2 = ("""SELECT DISTINCT date FROM %s where stock_id='1101'"""%('price'))
                    s3 = ("""SELECT DISTINCT date FROM %s where stock_id='2330'"""%('price'))

                    # 將日期抓出來並排序整理，放到self.dates中
                    df = (pd.read_sql(s1, self.conn)
                          .append(pd.read_sql(s2, self.conn))
                          .append(pd.read_sql(s3, self.conn))
                          .drop_duplicates('date').sort_values('date'))
                    df['date'] = pd.to_datetime(df['date'])
                    df = df.set_index('date')
                    self.dates[tname] = df
                else:
                    # 將日期抓出來並排序整理，放到self.dates中
                    s = ("""SELECT DISTINCT date FROM '%s'"""%(tname))
                    self.dates[tname] = pd.read_sql(s, self.conn, parse_dates=['date'], index_col=['date']).sort_index()
        #print('Data: done')

        # 只留上市櫃股票list
        # url = "https://isin.twse.com.tw/isin/class_main.jsp?owncode=&stockname=&isincode=&market=1&issuetype=1&industry_code=&Page=1&chklike=Y"
        #
        # response = requests.get(url)
        # listed = pd.read_html(response.text)[0]
        # listed.columns = listed.iloc[0, :]
        # listed = listed[["有價證券代號", "有價證券名稱", "市場別", "產業別", "公開發行/上市(櫃)/發行日"]]
        # listed = listed.iloc[1:]
        #
        # stock_1 = listed["有價證券代號"]
        #
        # self.stocklist = stock_1.tolist()
        #
        # self.stocklist.remove('8480')
        # self.stocklist.remove('2424')
        # self.stocklist.remove('6225')
        # self.stocklist.remove('6671')
        # self.stocklist.remove('1592')
        
        
    def get(self, table, name, n):
        
        # 確認名稱是否存在於資料庫
        if name not in self.col2table or n == 0:
            print('Data: **ERROR: cannot find', name, 'in database')
            return pd.DataFrame()
        if table not in self.col2table[name]:
            print('Data: **ERROR: cannot find', name, 'in table', table)
            return pd.DataFrame()
        
        # 找出欲爬取的時間段（startdate, enddate）
        df = self.dates[table].loc[:self.date].iloc[-n:]

        try:
            startdate = df.index[-1]
            enddate = df.index[0]
        except:
            print('Data: **WARRN: data cannot be retrieve completely:', name)
            enddate = df.iloc[0]
        
        # 假如該時間段已經在self.data中，則直接從self.data中拿取並回傳即可
        if (table, name) in self.data and self.contain_date(table, name, enddate, startdate):
            return self.data[(table, name)][enddate:startdate]
        
        # 從資料庫中拿取所需的資料 總經資料沒有stock_id
        if table in self.macro_eco_db:
            s = ("""SELECT date, [%s] FROM %s WHERE date BETWEEN '%s' AND '%s'"""%(name,
                table, str(enddate.strftime('%Y-%m-%d')),
                str((self.date + datetime.timedelta(days=1)).strftime('%Y-%m-%d'))))
            ret = pd.read_sql(s, self.conn, parse_dates=['date']).set_index('date')[name]
        else:
            s = ("""SELECT stock_id, date, [%s] FROM %s WHERE date BETWEEN '%s' AND '%s'"""%(name,
                table, str(enddate.strftime('%Y-%m-%d')),
                str((self.date + datetime.timedelta(days=1)).strftime('%Y-%m-%d'))))
            ret = pd.read_sql(s, self.conn, parse_dates=['date']).pivot(index='date', columns='stock_id')[name]

        # 只留上市櫃股票
        # ret = ret[self.stocklist]

        # 將這些資料存入cache，以便將來要使用時，不需要從資料庫額外調出來
        if self.cache:
            self.data[(table, name)] = ret
        return ret

    def get_stock_id_date_ohlcva(self, table, names, stock_id, n):

        # 確認名稱是否存在於資料庫
        for name in names:
            if name not in self.col2table or n == 0:
                print('Data: **ERROR: cannot find', name, 'in database')
                return pd.DataFrame()
        if table not in self.col2table[name]:
            print('Data: **ERROR: cannot find', name, 'in table', table)
            return pd.DataFrame()

        # 找出欲爬取的時間段（startdate, enddate）
        df = self.dates[table].loc[:self.date].iloc[-n:]

        try:
            startdate = df.index[-1]
            enddate = df.index[0]
        except:
            print('Data: **WARRN: data cannot be retrieve completely:', name)
            enddate = df.iloc[0]


        s = ("""SELECT stock_id, date, [%s], [%s], [%s], [%s], [%s], [%s] FROM %s WHERE stock_id IN (%s) and date BETWEEN '%s' AND '%s'"""
                                                                                            % (names[0], names[1], names[2], names[3], names[4], names[5],
                                                                                            table,
                                                                                            stock_id,
                                                                                            str(enddate.strftime('%Y-%m-%d')),
                                                                                            str((self.date + datetime.timedelta(days=1)).strftime('%Y-%m-%d'))))
        ret = pd.read_sql(s, self.conn, parse_dates=['date'])

        # 只留上市櫃股票
        # ret = ret[self.stocklist]

        # 將這些資料存入cache，以便將來要使用時，不需要從資料庫額外調出來
        return ret
    def get_stock_id_date_margin_transactions(self, table, stock_id, n):


        # 找出欲爬取的時間段（startdate, enddate）
        df = self.dates[table].loc[:self.date].iloc[-n:]

        try:
            startdate = df.index[-1]
            enddate = df.index[0]
        except:
            print('Data: **WARRN: data cannot be retrieve completely:')
            enddate = df.iloc[0]


        s = ("""SELECT * FROM %s WHERE stock_id IN (%s) and date BETWEEN '%s' AND '%s'"""
                                                                                            % (
                                                                                            table,
                                                                                            stock_id,
                                                                                            str(enddate.strftime('%Y-%m-%d')),
                                                                                            str((self.date + datetime.timedelta(days=1)).strftime('%Y-%m-%d'))))
        ret = pd.read_sql(s, self.conn, parse_dates=['date'])

        # 只留上市櫃股票
        # ret = ret[self.stocklist]

        # 將這些資料存入cache，以便將來要使用時，不需要從資料庫額外調出來
        return ret
    
    # 確認該資料區間段是否已經存在self.data
    def contain_date(self,table, name, startdate, enddate):
        if (table, name) not in self.data:
            return False
        if self.data[(table, name)].index[0] <= startdate <= enddate <= self.data[(table, name)].index[-1]:
            return True
        
        return False