from core.backtest.backtester import Backtester, new_event_counts
from core.backtest.datafeed.tw_stock_datafeed import TwStockDataFeed
from core.backtest.models.cost_model import CostConfig, StockCostModel
from core.backtest.models.fill_model import FillConfig, TwStockFillModel
from core.backtest.models.instrument_spec import TwStockSpec
from core.backtest.models.settlement_model import TwStockSettlementModel
from core.backtest.report.reporter import StockBacktestReporter
from core.managers.stock.position_manager import StockPositionManager
from core.models import StockAccount
from core.strategies.base import BaseStrategy
from core.strategies.stock import BaseStockStrategy
from core.utils import InstrumentType, Market, PositionType, ShortMethod

"""Backtester factory: 全專案唯一一處依（市場, 商品）組合分派的地方"""


def build_backtester(
    strategy: BaseStrategy,
    adjusted_price: bool = True,
) -> Backtester:
    """
    - Description:
        依策略宣告的（市場, 商品）組合組裝對應的 model 組合

        這是全專案唯一的分派點。新增一個組合只需在此加一個分支，
        `Backtester` 本身一行都不用改。

        **分派鍵是兩個欄位的組合而非單一欄位**：model 組合本來就是按組合
        實作的（`TwStockSpec`／`TwStockFillModel` ＝ TW ＋ STOCK），
        單靠 `market` 無法區分台股與美股的股票策略。
    - Parameters:
        - strategy: BaseStrategy
            要回測的策略；其 `market` ＋ `instrument_type` 兩欄位為分派鍵
        - adjusted_price: bool
            訊號是否使用還原價（後復權）。**預設 True**：未還原時除權息跳空會被
            當成真實漲跌，是資料正確性問題而非可選功能
            （見 `docs/exchanges/data_coverage.md`〈股價還原〉）。
            `Backtester` 那一層的預設維持 False——引擎不預設任何政策，
            要用哪種價格由 factory 這個「政策層」決定
    - Return:
        - Backtester
            已注入該（市場, 商品）組合對應 model 組合的引擎
    """

    if (strategy.market, strategy.instrument_type) == (
        Market.TW,
        InstrumentType.STOCK,
    ):
        return build_tw_stock_backtester(strategy, adjusted_price)

    raise ValueError(
        f"尚未支援的（市場, 商品）組合：{strategy.market}, {strategy.instrument_type}"
    )


def build_tw_stock_backtester(
    strategy: BaseStockStrategy,
    adjusted_price: bool = True,
) -> Backtester:
    """組裝台股的 model 組合"""

    account: StockAccount = StockAccount(strategy.init_capital)
    strategy.setup_account(account)

    cost_model: StockCostModel = StockCostModel(build_cost_config(strategy))
    position_manager: StockPositionManager = StockPositionManager(account, cost_model)

    instrument: TwStockSpec = TwStockSpec()

    # 事件計數由 factory 建立，引擎與 FillModel 共用同一個 dict
    event_counts: dict = new_event_counts()
    fill_model: TwStockFillModel = TwStockFillModel(
        instrument=instrument,
        event_counts=event_counts,
        config=strategy.fill_config or FillConfig(),
        check_borrowable=cost_model.config.short_constraint.check_borrowable,
    )

    settlement: TwStockSettlementModel = TwStockSettlementModel(
        position_manager=position_manager,
        cost_model=cost_model,
        prev_close=fill_model.prev_close,
        instrument=instrument,
        day_trade_uncovered_policy=strategy.day_trade_uncovered_policy,
        margin_call_policy=strategy.margin_call_policy,
        max_holding_days=strategy.max_holding_days,
        max_no_quote_days=strategy.max_no_quote_days,
    )

    return Backtester(
        strategy=strategy,
        account=account,
        position_manager=position_manager,
        instrument=instrument,
        fill_model=fill_model,
        cost_model=cost_model,
        settlement=settlement,
        data_feed=TwStockDataFeed(),
        reporter_cls=StockBacktestReporter,
        event_counts=event_counts,
        adjusted_price=adjusted_price,
    )


def build_cost_config(strategy: BaseStockStrategy) -> CostConfig:
    """
    - Description:
        依策略宣告推導成本設定：放空且允許當沖時一律走現股當沖沖賣

        原本是 `Backtester.build_cost_config()`，但「依策略宣告組裝 model」
        本來就是 factory 的職責；留在引擎會讓引擎知道台股的信用交易語意。
    - Parameters:
        - strategy: BaseStockStrategy
            要回測的台股策略
    - Return:
        - config: CostConfig
            本次回測使用的成本參數
    """

    is_day_trade: bool = (
        strategy.position_type == PositionType.SHORT and strategy.enable_intraday
    )
    short_method: ShortMethod = (
        ShortMethod.DAY_TRADE if is_day_trade else strategy.short_method
    )

    config: CostConfig = strategy.cost_config or CostConfig.default(
        short_method, is_day_trade
    )

    if strategy.short_constraint is not None:
        config.short_constraint = strategy.short_constraint

    return config
