import shioaji as sj

from .notify import Notification
from .constant import OrderState


class Callback:
    """ Order callback """
    
    @staticmethod
    def order_callback(api: sj.Shioaji, token: str):
        """ 
        設置委託 or 成交回報的輸出格式
        
        Parameters
        - api: 永豐API
        - token: Line notify token
        """
        print("* Setting order callback...")
        
        def order_cb(stat, msg):
            if stat == OrderState.StockDeal:
                print(f"【Order Deal】 Stock: {msg['code']} | Volume: {msg['quantity']} | Price: {msg['price']} | Action: {msg['action']}")
                
                # Notify
                deal_info = {
                    'code': msg['code'],
                    'volume': msg['quantity'],
                    'price': msg['price'],
                    'action': msg['action']
                }
                Notification.post_deal_notify(token, deal_info)
        api.set_order_callback(order_cb)
        
        print("* Setting order callback successfully!")