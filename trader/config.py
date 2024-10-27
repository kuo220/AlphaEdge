import datetime


config = {
    # 執行模式
    "execute_mode": "backtest",                 # {"execute", "backtest"} 兩種模式
    "is_simulation": True,                      # 是否永豐api的模擬模式
    
    # 回測參數
    "start_date": datetime.datetime.now(),      # 回測開始日期
    "end_date": datetime.datetime.now(),        # 回測結束日期
    
    # 共同參數
    "api_num": 1,                               # api數量
    "api_key": [],                              # api_key在.env的變數名稱
    "api_secret_key": [],                       # api_secret_key在.env的變數名稱
    "line_token": "",                           # line_token在.env的變數名稱
    "stock_buy_num": 1,                         # 買入股票檔數
    "trade_record_path": "",                    # 交易紀錄存放路徑
    
    # 市場
    "market": "stock"                           # {"stock", "future"} 股票 or 期貨
}