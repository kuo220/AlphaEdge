import sqlite3
import os
import pandas as pd
import datetime
from pathlib import Path


class Chip:
    """ Institutional investors chip API """
    
    def __init__(self, db_path: str=str(Path(__file__).resolve().parents[1] / 'database'), db_name: str="chip.db", table_name: str="chip"):
        self.db_path = db_path
        self.db_name = db_name
        self.table_name = table_name
        
        self.conn = sqlite3.connect(f'{db_path}/{db_name}')
        
    
    def get(self, start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame:
        """ 取得所有股票的三大法人籌碼 """
        
        if start_date > end_date:
            return pd.DataFrame()
        
        query = f""" 
        SELECT * FROM {self.table_name} WHERE 日期 BETWEEN '{start_date}' AND '{end_date}'
        """
        df = pd.read_sql_query(query, self.conn)
        return df
    
    
    def get_stock_chip(self, stock_id: str, start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame:
        """ 取得指定個股的三大法人籌碼 """
        
        if start_date > end_date:
            return pd.DataFrame()
        
        query = f""" 
        SELECT * FROM {self.table_name} WHERE 證券代號 = '{stock_id}' AND 日期 BETWEEN '{start_date}' AND '{end_date}'
        """
        df = pd.read_sql_query(query, self.conn)
        return df

    
    def get_net_chip(self, start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame:
        """ 取得所有股票的三大法人淨買賣超 """
        
        if start_date > end_date:
            return pd.DataFrame()
        
        df = self.get(start_date, end_date)
        df = df.loc[:, ('日期', '證券代號', '證券名稱', '外資買賣超股數', '投信買賣超股數', '自營商買賣超股數')]
        return df
        
    
    def get_stock_net_chip(self, stock_id: str, start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame:
        """ 取得指定個股的三大法人淨買賣超 """
        
        if start_date > end_date:
            return pd.DataFrame()
        
        df = self.get_stock_chip(stock_id, start_date, end_date)
        df = df.loc[:, ('日期', '證券代號', '證券名稱', '外資買賣超股數', '投信買賣超股數', '自營商買賣超股數')]
        return df