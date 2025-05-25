from quantxlab.data import Data
import pandas as pd
import numpy as np
import datetime
import os
import plotly.express as px
from .strategy import Strategy

        
# Transaction record
class TransactionData():
    def __init__(self, stock_id, stock_share, stock_volume, buy_date, buy_price, sell_date=None, sell_price=None, profit=0, roi=0):
        self.stock_id = stock_id
        self.stock_share = stock_share
        self.stock_volume = stock_volume
        self.buy_date = buy_date
        self.buy_price = buy_price
        self.sell_date = sell_date
        self.sell_price = sell_price
        self.profit = profit
        self.ROI = roi

class EnergyStrategy(Strategy):
    def __init__(self, data, params: dict):
        self.data = data
        self.params = params
        self.start_date = params['start_date']
        self.end_date = params['end_date']
        self.initial_capital = params['capital']
        self.accumulated_capital = params['capital']
        self.sell_time = params['sell_time']
        self.buy_stock_num = params['buy_stock_num']
        self.volume_limit = params['volume_limit']
        self.is_volume_sort = params['is_volume_sort']
        self.stocks_inventory = []
        self.transaction_record = pd.DataFrame()
        
    def get_type(self) -> str:
        """ 
        - Description: return the name of the strategy
        - Return: string
        """
        return "Energy_Strategy"
    
    def get_params(self) -> dict:
        """ 
        - Description: return the parameters
        - Return: dict
        """
        return self.params
    
    def backtest(self) -> None:
        """ 
        - Description: run back test with the strategy
        """
        current_date = self.start_date
        
        print("----- Backtest Start -----")
        print(f"* {self.start_date.strftime('%Y/%m/%d')} ~ {self.end_date.strftime('%Y/%m/%d')}")
        print(f"* Initial Capital: {self.initial_capital}")
        print(f"* Initial Accumulated Capital: {self.accumulated_capital}")
        print(f"* Sell Mode: {self.sell_time}")
        print(f"* Stock Number To Buy Limit: {self.buy_stock_num}\n")
        
        while current_date <= self.end_date:
            print(f"--- {current_date.strftime('%Y/%m/%d')} ---")
            
            self.data.date = current_date
            current_date += datetime.timedelta(days=1)
            
            close_price = self.data.get('price', '收盤價', 1)
             
            # Stock market closure
            if close_price.index.date != self.data.date:
                print("Stock Market Close\n")
                continue
            
            # Sell all stocks in inventory
            if len(self.stocks_inventory) > 0:
                self.sell_stocks()
                
            # Buy stocks
            # TODO: limit up
            if len(self.stocks_inventory) < self.buy_stock_num:
                 
                if len(stock_list.columns) > 0:
                    _, _ = self.produce_portfolio(stock_list, self.accumulated_capital)
                else:
                    print("Select no stocks, pass to next trading date\n")
        
        # Print Result
        print(f"* Total Profit: {self.transaction_record['Profit'].sum()}, "
              f"Total ROI(%): {round(self.transaction_record['Profit'].sum() / self.initial_capital * 100, 2)}%, "
              f"Win Ratio(%): {round(len(self.transaction_record[self.transaction_record['Profit'] > 0]['Profit']) / len(self.transaction_record['Profit']) * 100)}%")
        
        self.summarize_transaction_stats()
            
    
    def run(self) -> pd.DataFrame:
        """ 
        - Description: Energy strategy
        - Return:
            - stocks: pd.Series
        """
        
        # Check whether stock data is in the database, ex: price, volume, equity
        def check_data_exist(data: pd.DataFrame, stock_list: list) -> list:
            valid_stock_list = []
            
            for stock in stock_list:
                if stock not in data.columns.tolist():
                    print(f"Lost data on {stock}")
                else:
                    valid_stock_list.append(stock)
            return valid_stock_list
        
        # Check whether stock close price is in the database of next day
        # Ensure that all stocks bought today can be selled tomorrow
        def check_data_exist_next_day(stock_list: pd.DataFrame) -> pd.DataFrame:
            current_date = self.data.date
            
            if self.sell_time == "open":
                current_price = self.data.get('price', '開盤價', 1)
            else:
                current_price = self.data.get('price', '收盤價', 1)
            
            print(f"* Current trading date: {current_date}")
            
            self.data.date += datetime.timedelta(days=1)
            
            # Find the next trading day
            if self.sell_time == "open":
                next_price = self.data.get('price', '開盤價', 1)
            else:
                next_price = self.data.get('price', '收盤價', 1)
            
            while current_price.index == next_price.index:
                self.data.date += datetime.timedelta(days=1)
                next_price = self.data.get('price', '收盤價', 1)
                
            print(f"* Next trading date: {self.data.date}\n")
            
            # Delete the stock if its price is NaN data at next trading day
            valid_stock_list = []
            for stock in stock_list.columns:
                if (stock in next_price.columns) and (not next_price[stock].isna().values):
                    valid_stock_list.append(stock)
                else:
                    print(f"Stock ID: {stock} has no price at next trading day")
            
            self.data.date = current_date 
            return stock_list[valid_stock_list]

        
        close_price = self.data.get('price', '收盤價', 3)
        volume = round(self.data.get('price', '成交股數', 1) / 1000)
        
        # TODO: stock equity
        stock_equity = self.data.get('balance_sheet', '普通股股本', 1) / 10e8
        # stock_equity = self.data.get('balance_sheet', '普通股股本', 1) / 10e4

        # 過濾列名，只保留 1101 到 9958 之間的ID，且不含英文字母且僅有四位數字
        filtered_columns = [col for col in close_price.columns if col.isdigit() and len(col) == 4 and 1101 <= int(col) <= 9958]

        # 根據篩選後的列名重新建立DataFrame
        close_price = close_price[filtered_columns]
        
        # Condition 1: 當日漲 > 9% 的股票
        today_increase = ((close_price - close_price.shift(periods=1)) / close_price.shift(periods=1) * 100).iloc[-1:]
        today_increase_nine_up = today_increase.iloc[-1] > 9
        today_increase_nine_up_stocks = today_increase.loc[:, today_increase_nine_up].columns

        # Condition 2: 昨日漲 < 9% 的股票
        yesterday_increase = ((close_price - close_price.shift(periods=1)) / close_price.shift(periods=1) * 100).iloc[-2:-1]
        yesterday_increase_less_nine = yesterday_increase.iloc[-1] < 9
        yesterday_increase_less_nine_stocks = yesterday_increase.loc[:, yesterday_increase_less_nine].columns

        # Condition 1 & Condition 2
        selected_stocks = set(today_increase_nine_up_stocks) & set(yesterday_increase_less_nine_stocks)
        valid_stock_list = check_data_exist(close_price, list(selected_stocks))
        selected_stocks = close_price.iloc[-1:][valid_stock_list]

        # Condition 3: 篩出成交量 >= 5000
        valid_stock_list = check_data_exist(volume, selected_stocks.columns)
        volume_5000_up = volume[valid_stock_list].iloc[-1] >= 5000
        selected_stocks = selected_stocks.iloc[-1:][valid_stock_list].loc[:, volume_5000_up]
        
        # Condition 4: 篩出股本 <= 20億
        valid_stock_list = check_data_exist(stock_equity, selected_stocks.columns)
        stock_equity_less_20e = stock_equity[valid_stock_list].iloc[-1] <= 20
        # stock_equity_less_80e = stock_equity[valid_stock_list].iloc[-1] <= 80
        selected_stocks = selected_stocks.iloc[-1:][valid_stock_list].loc[:, stock_equity_less_20e]
        # selected_stocks -> pd.DataFrame
        
        # Ensure the stock can be sold tomorrow
        if len(selected_stocks.columns) > 0:
            selected_stocks = check_data_exist_next_day(selected_stocks)

        # if is_volume_sort == True, then 根據成交量對 selected_stocks 進行排序
        if self.is_volume_sort and len(selected_stocks.columns) > 0:
            # 提取選中股票的最後一日成交量
            selected_volume = volume[selected_stocks.columns].iloc[-1]
            
            # 根據成交量進行排序
            sorted_stocks_by_volume = selected_volume.sort_values(ascending=False)
            
            # 印出排序後的股票代號及其成交量
            print("Sorted stocks by volume:")
            for stock, vol in sorted_stocks_by_volume.items():
                print(f"Stock ID: {stock}, Volume: {vol}")
            
            # 重新排序 selected_stocks 和 close_price
            sorted_stock_list = sorted_stocks_by_volume.index.tolist()
            selected_stocks = selected_stocks[sorted_stock_list]
            # close_price = close_price[sorted_stock_list]
            print(len(selected_stocks.columns), "stocks selected\n")
            
        # TODO: limit up
        if len(self.stocks_inventory) == 0:
            if len(selected_stocks.columns) < self.buy_stock_num:
                return close_price[selected_stocks.columns].iloc[-1:]
            else:
                return close_price[selected_stocks.columns].iloc[-1:, :self.buy_stock_num]
        else:
            if len(selected_stocks.columns) < self.buy_stock_num - len(self.stocks_inventory):
                return close_price[selected_stocks.columns].iloc[-1:]
            else:
                return close_price[selected_stocks.columns].iloc[-1:, :(self.buy_stock_num - len(self.stocks_inventory))]
            
    
    # Buy stocks
    def produce_portfolio(self, stock_list: pd.DataFrame, total_invest_money=1000000, lowest_fee=20, discount=0.3, add_cost=0) -> tuple[pd.Series, float]:
        """ 
        - Description: Buy stocks chosen by the strategy
        - Parameters:
            - stock_list: pd.Dataframe, become pd.Series after slicing
                Stocks to buy
            - total_invest_money: int
                Initial capital to invest
            - lowest_fee
                Minimum transaction fee for buying a single stock (unit: NT dollars).
            - discount
                Discount for QuantX on transaction fee.
            - add cost
                The additional cost for diversifying portfolio.
            - volume_list: pd.Series
                The volume of stocks to buy

        - Return:
            - stocks: tuple[pd.Series, float]
        """
        
        close_price = self.data.get('price', '收盤價', 1)
        volume = round(self.data.get('price', '成交股數', 1) / 1000)

        valid_stock_list = []
        
        # check stock close price exists
        for stock in stock_list.columns:
            if stock not in close_price.columns.tolist():
                print(f"Lost close price data on {stock}")
            else:
                valid_stock_list.append(stock)
                
        stock_list = close_price.iloc[-1][valid_stock_list]
        volume_list = volume.iloc[-1][valid_stock_list]

        # Get volume limit for each stock
        volume_limit_list = (volume_list * self.volume_limit).astype(int)
        
        invest_amount_per_stock = total_invest_money / len(stock_list)
        threshold_with_minimum_fee_rate = (lowest_fee - add_cost) / (0.001425 * discount)
        
        # consider the minimum buying fee
        while invest_amount_per_stock < threshold_with_minimum_fee_rate:
            stock_list = stock_list[stock_list != stock_list.max()]
            invest_amount_per_stock = total_invest_money / len(stock_list)
        
        # 假設有兩檔都無法買，刪掉最貴的那支股票後再判斷一次
        invest_amount_per_stock = total_invest_money / len(stock_list)
        stock_cannot_buy_1000_shares = (np.floor(invest_amount_per_stock / (stock_list * 1000)) == 0).any()

        # Shares to buy
        selected_stock = np.floor(invest_amount_per_stock / (stock_list * 1000))
        # buy_percent = round(selected_stock / volume_limit_list * 100, 2)
        
        # make sure the volume of stocks to buy is less than the volume limit
        selected_stock = np.minimum(selected_stock, volume_limit_list)

        while stock_cannot_buy_1000_shares:
            stock_list = stock_list[stock_list != stock_list.max()]
            invest_amount_per_stock = total_invest_money / len(stock_list)
            
            stock_cannot_buy_1000_shares = (np.floor(invest_amount_per_stock / (stock_list * 1000)) == 0).any()
            selected_stock = np.floor(invest_amount_per_stock / (stock_list * 1000))
        
        # print buy result
        print("=== Buy Stocks ===")
        print(f"{'Stock ID':<9} {'Shares':<7} {'Invest':<6}")
        for stock_id, shares in selected_stock.items():
            print(f"{stock_id:<9} {shares:<7} {round(close_price.iloc[-1].loc[stock_id] * shares * 1000):<6}")
        print()
        
        # Create transaction record
        for stock_id in selected_stock.index:
            stock_share = int(selected_stock[stock_id])
            buy_price = stock_list[stock_id]
            transaction = TransactionData(stock_id, stock_share, volume[stock_id], self.data.date.strftime('%Y/%m/%d'), buy_price)
            self.stocks_inventory.append(transaction)
        
        return selected_stock, (selected_stock * stock_list * 1000).sum()
    
    # Sell stocks
    def sell_stocks(self) -> None:
        """ 
        - Description: sell stocks
        - Parameters:
            - discount
                Discount for QuantX on transaction fee.
            - sell_time:
                1. open: sell all stocks at open price
                2. close: sell all stocks at close price
                3. either: if open_price 5% up, then sell at close price, else sell at open price
                4. limit_up_hold: if stock limit up, then hold
        """
        
        def calculate_friction_cost(buy_price, sell_price, stock_share, transaction_fee_rate=0.001425, security_exchange_tax_rate=0.003, fee_discount=0.3):
            """
            For long position, the friction costs should contains:
                - buy fee (券買手續費 = 成交價 x 成交股數 x 手續費率 x discount)
                - sell fee (券賣手續費 = 成交價 x 成交股數 x 手續費率 x discount)
                - sell tax (券賣證交稅 = 成交價 x 成交股數 x 證交稅率)
            """
            buy_fee = buy_price * stock_share * 1000 * transaction_fee_rate * fee_discount
            sell_fee = sell_price * stock_share * 1000 * (transaction_fee_rate * fee_discount + security_exchange_tax_rate)
            return buy_fee, sell_fee


        print("=== Sell Stocks ===")
        print(f"* Stock Number In Inventory: {len(self.stocks_inventory)}\n")
            
        open_price = self.data.get('price', '開盤價', 1)
        close_price = self.data.get('price', '收盤價', 2)
        volume = round(self.data.get('price', '成交股數', 1) / 1000)
        
        stock_sell_list = []
        original_accumulated_capital = self.accumulated_capital
        
        for stock in self.stocks_inventory:
            if self.sell_time == "open":
                sell_price = open_price.iloc[-1][stock.stock_id]
            elif self.sell_time == "close":
                sell_price = close_price.iloc[-1][stock.stock_id]
            elif self.sell_time == "either":
                # calculate the increase of open price
                increase_ratio = round((open_price.iloc[-1] - close_price.iloc[-2]) / close_price.iloc[-2] * 100, 2)
                if increase_ratio[stock.stock_id] >= 5:
                    sell_price = close_price.iloc[-1][stock.stock_id]
                else:
                    sell_price = open_price.iloc[-1][stock.stock_id]
                    
            # TODO: limit up
            elif self.sell_time == "limit_up_hold":
                open_increase_ratio = round((open_price / close_price.iloc[-1:] - 1) * 100, 2).iloc[-1]
                close_increase_ratio = round((close_price / close_price.shift(periods=1) - 1) * 100, 2).iloc[-1]
                
                if open_increase_ratio[stock.stock_id] >= 9 and close_increase_ratio[stock.stock_id] >= 9.5:
                    print(f"- Stock ID: {stock.stock_id}")
                    print(f"  - Limit up stock: {stock.stock_id}, Increase ratio: {close_increase_ratio[stock.stock_id]}")
                    print("  - Status: Hold")
                    continue
                sell_price = open_price.iloc[-1][stock.stock_id]
            
            # if stock sell price is nan, then hold until tomorrow
            if np.isnan(sell_price):
                print(f"* Sell price is NaN: {{stock.stock_id}}")
                continue
                
            buy_fee, sell_fee = calculate_friction_cost(stock.buy_price, sell_price, stock.stock_share)
            total_cost = buy_fee + sell_fee
            total_profit = round((sell_price - stock.buy_price) * stock.stock_share * 1000 - total_cost)
            roi = round(total_profit / (stock.buy_price * stock.stock_share * 1000) * 100, 2)
            
            self.accumulated_capital += total_profit
            
            stock.volume = volume.iloc[-1][stock.stock_id]
            stock.sell_date = self.data.date.strftime('%Y/%m/%d')
            stock.sell_price = sell_price
            stock.profit = total_profit
            stock.ROI = roi
            
            record_col_name = ["Stock ID", "Shares", "Buy Date", "Buy Price", "Sell Date", "Sell Price", "Profit", "Profit(%)", "Accumulated Capital"]
            record = pd.Series([stock.stock_id, stock.stock_share, stock.buy_date, stock.buy_price, 
                                stock.sell_date, stock.sell_price, stock.profit, stock.ROI, self.accumulated_capital], index=record_col_name)
            self.transaction_record = pd.concat([self.transaction_record, record.to_frame().T], ignore_index=True)

            # print sell result
            print(f"- Stock ID: {stock.stock_id}")
            print(f"  - Buy Price: {stock.buy_price}, Sell Price: {stock.sell_price}, Profit: {stock.profit}, Profit(%): {stock.ROI}")
            
            # Warning message for selling too many stocks
            if stock.stock_share > stock.volume * self.volume_limit:
                print(f"  - Volume Limit: {round(stock.volume * self.volume_limit)}, Sell Volume: {stock.stock_share}, Ratio: {round(stock.stock_share * 100 / stock.volume, 2)}%\n")
                
            print(f"  - Before Sell Accumulated Capital: {self.accumulated_capital - total_profit}")
            print(f"  - After Sell Accumulated Capital: {self.accumulated_capital}")
            print(f"  - Accumulated Capital: {self.accumulated_capital}")
            print("  - Status: Sold")
            
            stock_sell_list.append(stock)
            
        # print today total profit 
        print(f"- Today Total Profit: {self.accumulated_capital - original_accumulated_capital}")
        
        # remove stocks that are sold
        for stock in stock_sell_list:
            self.stocks_inventory.remove(stock)
        
        # print stocks that are held
        print("\n* Remain Stocks In Inventory")
        if len(self.stocks_inventory) != 0:
            for stock in self.stocks_inventory:
                print(f"  - Stock ID: {stock.stock_id}")
            print()
        else:
            print("  - Empty\n")

    def summarize_transaction_stats(self) -> None:
        """ 
        - Description: plot the charts with statistic
        """
        
        if self.transaction_record.empty:
            return
        
        # set figure layout
        def set_fig_layout(fig, title: str="", xaxis_title: str="", yaxis_title: str="") -> None:
            fig.update_layout(
                title = title,
                xaxis_title = xaxis_title,
                yaxis_title = yaxis_title
            )
        
        def set_fig_info(fig, info_context: str=""):
            fig.add_annotation(
                xref = 'paper',
                yref = 'paper',
                x = 1,
                y = 1,
                text = info_context.replace("\n", "<br>"),
                showarrow = False,
                font = dict(
                    size = 15,
                    color = 'white',
                ),
                align = 'left',
                bordercolor = 'black',
                borderwidth = 1,
                borderpad = 5,
                bgcolor = 'black',
                opacity = 0.5 
            )

        # make directory
        # add begin date, end date, capital, buy_stock_num to the file path
        file_path = os.path.join('result', self.params['output_dir'], f"{self.start_date.strftime('%Y%m%d')}_{self.end_date.strftime('%Y%m%d')}_{self.params['capital']}_{self.buy_stock_num}_stocks")
        if not os.path.exists(file_path):
            os.makedirs(file_path)
        
        # Add sell date as transaction record index and save as .csv file
        self.transaction_record.index = self.transaction_record.loc[:, 'Sell Date']
        transaction_record_path = os.path.join(file_path, f'transaction_record_{self.buy_stock_num}.csv')
        self.transaction_record.to_csv(transaction_record_path)
        
        # Plot the transaction statistics
        # Fig1: Accumulated capital
        accumulated_capital_fig = px.line(self.transaction_record, x='Sell Date', y='Accumulated Capital')
        accumulated_capital_path = os.path.join(file_path, f'accumulated_capital_{self.buy_stock_num}.png')
    
        total_profit = self.transaction_record['Profit'].sum()
        total_roi = round(self.transaction_record['Profit'].sum() / self.initial_capital * 100, 2)
        win_ratio = round(len(self.transaction_record[self.transaction_record['Profit'] > 0]['Profit']) / len(self.transaction_record['Profit']) * 100)
        invest_info = f"Total Profit: {total_profit}\n" + \
                      f"Total ROI(%): {total_roi}%\n" + \
                      f"Win Ratio(%): {win_ratio}%"
        
        set_fig_layout(fig=accumulated_capital_fig, title=f"Return (Initial Capital: {self.initial_capital}, {self.start_date.strftime('%Y/%m/%d')} ~ {self.end_date.strftime('%Y/%m/%d')})", xaxis_title='Date', yaxis_title='Accumulated Capital')
        set_fig_info(accumulated_capital_fig, info_context=invest_info)
        accumulated_capital_fig.show()
        accumulated_capital_fig.write_image(accumulated_capital_path)
        
        # Fig2: Every day profit
        everyday_profit_fig = px.bar(self.transaction_record, x='Sell Date', y='Profit')
        everyday_profit_path = os.path.join(file_path, f'everyday_profit_{self.buy_stock_num}.png')
        set_fig_layout(fig=everyday_profit_fig, title=f"Everyday Every Stock's Profit ({self.start_date.strftime('%Y/%m/%d')} ~ {self.end_date.strftime('%Y/%m/%d')})", xaxis_title='Date', yaxis_title='Profit')
        everyday_profit_fig.show()
        everyday_profit_fig.write_image(everyday_profit_path)
        
        
        # Fig3: MDD
        # benchmark: 0050
        current_date = self.data.date
        self.data.date = self.end_date

        close_price = self.data.get('price', '收盤價', (self.end_date - self.start_date).days)
        self.data.date = current_date
        
        benchmark_price = close_price[self.params["benchmark_id"]][self.start_date:self.end_date]
        mdd_0050 = ((benchmark_price / benchmark_price.cummax() - 1) * 100)
        
        # Accumulated capital MDD
        accumulated_capital = self.transaction_record['Accumulated Capital'].groupby(self.transaction_record['Accumulated Capital'].index).last().astype(float)
        mdd = ((accumulated_capital / accumulated_capital.cummax() - 1) * 100)
        
        dates = mdd.index
        mdd_df = pd.DataFrame({
            'Date': dates,
            'Energy Strategy MDD': pd.Series(mdd, index=dates).values,
            f'{self.params["benchmark_id"]} MDD': pd.Series(mdd_0050, index=dates).values
        })
        
        mdd_fig = px.line(mdd_df, x='Date', y=['Energy Strategy MDD', f'{self.params["benchmark_id"]} MDD'])
        mdd_fig_path = os.path.join(file_path, f'MDD_{self.buy_stock_num}.png')
        set_fig_layout(fig=mdd_fig, title=f"MDD ({self.start_date.strftime('%Y/%m/%d')} ~ {self.end_date.strftime('%Y/%m/%d')})", xaxis_title='Date', yaxis_title='MDD')
        mdd_fig.show()
        mdd_fig.write_image(mdd_fig_path)
        
        # Fig4: Compare with benchmark
        # benchmark everyday net worth
        benchmark_buy_price = benchmark_price.iloc[0]
        benchmark_buy_shares = np.floor(self.initial_capital / (benchmark_buy_price * 1000))

        if benchmark_buy_shares > 0:
            benchmark_net_worth = benchmark_price / benchmark_price.iloc[0] * self.initial_capital
            
            net_worth_df = pd.DataFrame({
                'Date': dates,
                'Energy Strategy Net Worth': pd.Series(accumulated_capital, index=dates).values,
                f'{self.params["benchmark_id"]} Net Worth': pd.Series(benchmark_net_worth, index=dates).values
            })
            
            net_worth_fig = px.line(net_worth_df, x='Date', y=['Energy Strategy Net Worth', f'{self.params["benchmark_id"]} Net Worth'])
            net_worth_fig_path = os.path.join(file_path, f'net_worth_{self.buy_stock_num}.png')
            
            benchmark_roi = round((benchmark_price.iloc[-1] / benchmark_price.iloc[0] - 1) * 100, 2)
            compare_info = f'Strategy Total ROI(%): {total_roi}%\n' + \
                           f'{self.params["benchmark_id"]} Total ROI(%): {benchmark_roi}%'
            
            set_fig_layout(fig=net_worth_fig, title=f"Energy Strategy & {self.params['benchmark_id']} Net Worth ({self.start_date.strftime('%Y/%m/%d')} ~ {self.end_date.strftime('%Y/%m/%d')})", xaxis_title='Date', yaxis_title='Net Worth')
            set_fig_info(fig=net_worth_fig, info_context=compare_info)
            net_worth_fig.show()
            net_worth_fig.write_image(net_worth_fig_path)