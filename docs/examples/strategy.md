# 策略開發範例

本頁面提供開發交易策略的範例。

## 基本策略結構

所有策略都必須繼承 `BaseStockStrategy` 並實作所有抽象方法。

```python
from trader.strategies.stock import BaseStockStrategy
from trader.models import StockAccount, StockOrder, StockQuote
from trader.utils import Action, Scale, PositionType
from typing import List
import datetime

class MyStrategy(BaseStockStrategy):
    def __init__(self):
        super().__init__()
        
        # 策略基本設定
        self.strategy_name = "MyStrategy"
        self.scale = Scale.DAY
        self.init_capital = 1000000.0
        self.max_holdings = 10
        
        # 回測設定
        self.start_date = datetime.date(2024, 1, 1)
        self.end_date = datetime.date(2024, 12, 31)
        
        # 載入 API
        self.setup_apis()
    
    def setup_account(self, account: StockAccount):
        self.account = account
    
    def setup_apis(self):
        from trader.api.stock_price_api import StockPriceAPI
        self.price = StockPriceAPI()
    
    def check_open_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        # 實作開倉邏輯
        pass
    
    def check_close_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        # 實作平倉邏輯
        pass
    
    def check_stop_loss_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        # 實作停損邏輯
        pass
    
    def calculate_position_size(self, stock_quotes: List[StockQuote], action: Action) -> List[StockOrder]:
        # 實作部位計算邏輯
        pass
```

## 簡單的移動平均策略

```python
from trader.strategies.stock import BaseStockStrategy
from trader.models import StockAccount, StockOrder, StockQuote
from trader.utils import Action, Scale, PositionType, Units
from typing import List, Optional
import datetime

class MovingAverageStrategy(BaseStockStrategy):
    """簡單的移動平均交叉策略"""
    
    def __init__(self):
        super().__init__()
        
        self.strategy_name = "MovingAverageStrategy"
        self.scale = Scale.DAY
        self.init_capital = 1000000.0
        self.max_holdings = 5
        
        self.start_date = datetime.date(2024, 1, 1)
        self.end_date = datetime.date(2024, 12, 31)
        
        # 策略參數
        self.short_period = 5  # 短期移動平均天數
        self.long_period = 20  # 長期移動平均天數
        
        self.setup_apis()
    
    def setup_account(self, account: StockAccount):
        self.account = account
    
    def setup_apis(self):
        from trader.api.stock_price_api import StockPriceAPI
        self.price = StockPriceAPI()
    
    def _calculate_ma(self, stock_id: str, date: datetime.date, period: int) -> Optional[float]:
        """計算移動平均"""
        end_date = date
        start_date = date - datetime.timedelta(days=period * 2)  # 多取一些資料
        
        prices = self.price.get_stock_price(stock_id, start_date, end_date)
        
        if len(prices) < period:
            return None
        
        prices = prices.sort_values('date')
        return prices['close'].tail(period).mean()
    
    def check_open_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        """當短期均線向上穿越長期均線時開倉"""
        open_orders = []
        
        for quote in stock_quotes:
            # 檢查是否已有持倉
            if self.account.check_has_position(quote.stock_id):
                continue
            
            # 計算移動平均
            short_ma = self._calculate_ma(quote.stock_id, quote.date, self.short_period)
            long_ma = self._calculate_ma(quote.stock_id, quote.date, self.long_period)
            
            if short_ma is None or long_ma is None:
                continue
            
            # 檢查是否向上穿越
            if short_ma > long_ma:
                open_orders.append(quote)
        
        return self.calculate_position_size(open_orders, Action.BUY)
    
    def check_close_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        """當短期均線向下穿越長期均線時平倉"""
        close_orders = []
        
        for quote in stock_quotes:
            if not self.account.check_has_position(quote.stock_id):
                continue
            
            short_ma = self._calculate_ma(quote.stock_id, quote.date, self.short_period)
            long_ma = self._calculate_ma(quote.stock_id, quote.date, self.long_period)
            
            if short_ma is None or long_ma is None:
                continue
            
            # 檢查是否向下穿越
            if short_ma < long_ma:
                close_orders.append(quote)
        
        return self.calculate_position_size(close_orders, Action.SELL)
    
    def check_stop_loss_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        """虧損超過 10% 時停損"""
        stop_loss_orders = []
        
        for quote in stock_quotes:
            if not self.account.check_has_position(quote.stock_id):
                continue
            
            position = self.account.get_first_open_position(quote.stock_id)
            if position is None:
                continue
            
            # 計算虧損比例
            loss_pct = (quote.close / position.price - 1)
            
            if loss_pct < -0.10:  # 虧損超過 10%
                stop_loss_orders.append(quote)
        
        return self.calculate_position_size(stop_loss_orders, Action.SELL)
    
    def calculate_position_size(
        self, stock_quotes: List[StockQuote], action: Action
    ) -> List[StockOrder]:
        """計算下單數量"""
        orders = []
        
        if action == Action.BUY:
            available_position_cnt = max(
                0, self.max_holdings - self.account.get_position_count()
            )
            
            if available_position_cnt > 0:
                per_position_size = self.account.balance / available_position_cnt
                
                for quote in stock_quotes:
                    open_volume = int(
                        per_position_size / (quote.close * Units.LOT)
                    )
                    
                    if open_volume >= 1:
                        orders.append(
                            StockOrder(
                                stock_id=quote.stock_id,
                                date=quote.date,
                                action=action,
                                position_type=PositionType.LONG,
                                price=quote.cur_price,
                                volume=open_volume,
                            )
                        )
                        available_position_cnt -= 1
                        
                        if available_position_cnt == 0:
                            break
        
        elif action == Action.SELL:
            for quote in stock_quotes:
                position = self.account.get_first_open_position(quote.stock_id)
                if position is None:
                    continue
                
                orders.append(
                    StockOrder(
                        stock_id=quote.stock_id,
                        date=quote.date,
                        action=action,
                        position_type=position.position_type,
                        price=quote.cur_price,
                        volume=position.volume,
                    )
                )
        
        return orders
```

## 使用多種資料的策略

```python
from trader.strategies.stock import BaseStockStrategy
from trader.models import StockAccount, StockOrder, StockQuote
from trader.utils import Action, Scale, PositionType
from typing import List
import datetime

class MultiDataStrategy(BaseStockStrategy):
    """使用多種資料來源的策略"""
    
    def __init__(self):
        super().__init__()
        
        self.strategy_name = "MultiDataStrategy"
        self.scale = Scale.DAY
        self.init_capital = 1000000.0
        self.max_holdings = 10
        
        self.start_date = datetime.date(2024, 1, 1)
        self.end_date = datetime.date(2024, 12, 31)
        
        self.setup_apis()
    
    def setup_account(self, account: StockAccount):
        self.account = account
    
    def setup_apis(self):
        from trader.api.stock_price_api import StockPriceAPI
        from trader.api.stock_chip_api import StockChipAPI
        from trader.api.monthly_revenue_report_api import MonthlyRevenueReportAPI
        
        self.price = StockPriceAPI()
        self.chip = StockChipAPI()
        self.mrr = MonthlyRevenueReportAPI()
    
    def check_open_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        """結合價格、籌碼和月營收的開倉條件"""
        open_orders = []
        
        # 取得當日籌碼資料
        chips = self.chip.get(stock_quotes[0].date)
        chips_dict = {row['stock_id']: row for _, row in chips.iterrows()}
        
        # 取得當月月營收資料
        mrr = self.mrr.get(
            year=stock_quotes[0].date.year,
            month=stock_quotes[0].date.month
        )
        mrr_dict = {row['stock_id']: row for _, row in mrr.iterrows()}
        
        for quote in stock_quotes:
            if self.account.check_has_position(quote.stock_id):
                continue
            
            # 條件1: 價格上漲
            if quote.close <= quote.open:
                continue
            
            # 條件2: 外資買超
            chip_data = chips_dict.get(quote.stock_id)
            if chip_data is None or chip_data.get('foreign_buy', 0) <= 0:
                continue
            
            # 條件3: 月營收成長
            mrr_data = mrr_dict.get(quote.stock_id)
            if mrr_data is None:
                continue
            
            # 簡單的月營收成長判斷（需要更多歷史資料來比較）
            # 這裡只是範例
            
            open_orders.append(quote)
        
        return self.calculate_position_size(open_orders, Action.BUY)
    
    # ... 其他方法類似
```

## 執行策略回測

```bash
# 執行回測
python run.py --strategy MovingAverageStrategy
```

## 最佳實踐

1. **參數化**: 將策略參數設為類別屬性，方便調整
2. **資料驗證**: 在使用資料前檢查是否為空
3. **錯誤處理**: 適當處理 API 查詢失敗的情況
4. **效能優化**: 避免在迴圈中重複查詢相同資料
5. **日誌記錄**: 使用 loguru 記錄重要的決策過程

## 相關文檔

- [BaseStockStrategy API](../api/strategy/base_stock_strategy.md)
- [資料 API](../api/overview.md)
- [策略開發指南](../../trader/strategies/README.md)
