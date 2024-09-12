import pandas as pd
import numpy as np
import os
import shioaji as sj
from utils.constant import Action, Status


class Account:
    """ Account Information """
    
    # API login
    @staticmethod
    def API_login(api: sj.Shioaji, api_key: str, api_secret_key: str):
        """ API 登入 """
        
        print("API logging in...")
        api.login(api_key=api_key, secret_key=api_secret_key, contracts_timeout=30000)
        print("API logging in successfully!")


    # API logout
    @staticmethod
    def API_logout(api: sj.Shioaji):
        """ API 登出 """
        
        print("API logging out...")
        api.logout()
        print("API logging out successfully!")
    
    
    # Calculate capital after T+2
    @staticmethod
    def get_settlement_capital(api: sj.Shioaji) -> float:
        """ 計算 T+2 後的本金（帳戶可用的總資金） """
        
        balance = api.account_balance().acc_balance
        settlements = pd.DataFrame([s.__dict__ for s in api.settlements(api.stock_account)])
        total_capital = balance + settlements.loc[1:2, 'amount'].sum()
        return total_capital
    
    
    @staticmethod
    def get_invest_capital(api: sj.Shioaji, capital: float) -> float:
        """ 計算預計投入的資金 """
        
        total_capital = Account.get_settlement_capital(api) # 帳戶可用的總資金
        settlements = pd.DataFrame([s.__dict__ for s in api.settlements(api.stock_account)]) 
        capital_quota = capital + settlements.loc[2, 'amount'] # 目前剩餘的投資額度
        invest_capital = total_capital if total_capital <= capital_quota else capital_quota
        return invest_capital
    
    
    @staticmethod
    def get_realized_pnl(api: sj.Shioaji) -> int:
        """ 計算已實現損益 """
        
        pnl_df = pd.DataFrame(s.__dict__ for s in api.list_profit_loss(api.stock_account))
        realized_pnl = round(pnl_df.pnl.sum()) if len(pnl_df) > 0 else 0
        return realized_pnl
        

    @staticmethod
    def get_unrealized_pnl(api: sj.Shioaji) -> int:
        """ 計算未實現損益 """
        
        positions_df = pd.DataFrame(s.__dict__ for s in api.list_positions(api.stock_account))
        unrealized_pnl = round(positions_df.pnl.sum()) if len(positions_df) > 0 else 0
        return unrealized_pnl
        
        
    @staticmethod
    def generate_trade_record(api: sj.Shioaji, trade_record_path: str):
        """ 製作投資紀錄表 """
        
        columns_name = ["date", "stock_id", "order_action", "seqno", "volume", "buy_price", "sell_price", "pnl"]
        trade_record_df: pd.DataFrame = pd.DataFrame(columns=columns_name)

        api.update_status(api.stock_account)
        trade_list = api.list_trades()
        pnl_list = api.list_profit_loss()

        # Create trading record
        for trade in trade_list:
            if trade.status.status == Status.Filled:
                # 計算平均成交價
                ave_deal_price = round(sum(deal.price * deal.quantity for deal in trade.status.deals) / trade.order.quantity, 2)

                trade_record = pd.DataFrame([[trade.status.order_datetime, 
                                              trade.contract.code,
                                              trade.order.action, 
                                              trade.order.seqno, 
                                              trade.order.quantity, 
                                              ave_deal_price if trade.order.action == Action.Buy else np.nan, 
                                              ave_deal_price if trade.order.action == Action.Sell else np.nan, 
                                              0]],
                                            columns=columns_name)
                trade_record_df = pd.concat([trade_record_df, trade_record], ignore_index=True)
            
        # Add pnl to trading record
        for trade in pnl_list:
            trade_record_df.loc[trade_record_df['seqno'] == trade.seqno, 'pnl'] = trade.pnl

        if os.path.exists(trade_record_path):
            exist_trade_record = pd.read_csv(trade_record_path)
            new_trade_record = pd.concat([exist_trade_record, trade_record_df], ignore_index=True)
            new_trade_record.to_csv(trade_record_path, index=False)
        else:
            trade_record_df.to_csv(trade_record_path, index=False)