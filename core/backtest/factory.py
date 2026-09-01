from loguru import logger

from core.backtest.backtester import Backtester, new_event_counts
from core.backtest.datafeed.futures_datafeed import TwFuturesDataFeed
from core.backtest.datafeed.tw_stock_datafeed import TwStockDataFeed
from core.backtest.models.cost_model import (
    CostConfig,
    FuturesCostConfig,
    StockCostModel,
    TwFuturesCostModel,
)
from core.backtest.models.fill_model import (
    FillConfig,
    FuturesFillConfig,
    TwFuturesFillModel,
    TwStockFillModel,
)
from core.backtest.models.instrument_spec import TwFuturesSpec, TwStockSpec
from core.backtest.models.settlement_model import (
    TwFuturesSettlementModel,
    TwStockSettlementModel,
)
from core.backtest.report.futures_reporter import FuturesBacktestReporter
from core.backtest.report.reporter import StockBacktestReporter
from core.managers.futures.position_manager import (
    FuturesMarginConfig,
    FuturesPositionManager,
)
from core.managers.stock.position_manager import StockPositionManager
from core.models import FuturesAccount, StockAccount
from core.strategies.base import BaseStrategy
from core.strategies.futures import BaseFuturesStrategy
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

    if (strategy.market, strategy.instrument_type) == (
        Market.TW,
        InstrumentType.FUTURE,
    ):
        # `adjusted_price` 不往下傳：期貨沒有除權息還原的概念，見
        # `build_tw_futures_backtester()`
        return build_tw_futures_backtester(strategy)

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


def build_tw_futures_backtester(strategy: BaseFuturesStrategy) -> Backtester:
    """
    - Description:
        組裝台期貨的 model 組

        **與台股那一組的四個差異**（都是期貨的記帳語意造成的，不是實作偏好）：

        1. **`adjusted_price` 一律為 False**：期貨沒有除權息，不存在還原價。
        2. **成本設定由 `FuturesCostConfig` 提供**，且**同一個物件**同時交給
           `FuturesPositionManager` 與 `TwFuturesCostModel`——費率兩處各填一份
           必然漂移。本階段費率全為 0，實際費率屬 Phase2-1。
        3. **保證金設定由策略提供**，未提供時退回「契約價值 × 比率」的近似。
           近似的誤差跨年份實測為 +143% ~ −38%（見
           `backlog/台期貨保證金ETL.md` S5），故此處明確發出警告；接上
           `FuturesMarginAPI` 查表屬 Phase2-2。
        4. **`SettlementModel` 不需要 `cost_model`**：期貨在收盤後只做逐日盯市，
           不像台股要在此計提借券費與稅差。
    - Parameters:
        - strategy: BaseFuturesStrategy
            要回測的台期貨策略
    - Return:
        - Backtester
            已注入台期貨 model 組的引擎
    """

    account: FuturesAccount = FuturesAccount(strategy.init_capital)
    strategy.setup_account(account)

    # 成本與保證金設定：與 PositionManager 共用同一個物件
    cost_config: FuturesCostConfig = strategy.cost_config or FuturesCostConfig.default()
    margin_config: FuturesMarginConfig = (
        strategy.margin_config or FuturesMarginConfig.default()
    )

    if margin_config.api is None:
        logger.warning(
            f"[{strategy.strategy_name}] 未帶入保證金 API，本次回測以"
            f"「契約價值 × {margin_config.initial_margin_ratio:.0%}」近似原始保證金"
            f"——跨年份誤差實測為 +143% ~ −38%，僅適合跑通流程（查表屬 Phase2-2）"
        )

    cost_model: TwFuturesCostModel = TwFuturesCostModel(cost_config)
    position_manager: FuturesPositionManager = FuturesPositionManager(
        account,
        cost_model=cost_model,
        margin_config=margin_config,
    )

    instrument: TwFuturesSpec = TwFuturesSpec()

    # 事件計數由 factory 建立，引擎與 FillModel 共用同一個 dict
    event_counts: dict = new_event_counts()
    fill_model: TwFuturesFillModel = TwFuturesFillModel(
        instrument=instrument,
        event_counts=event_counts,
        config=strategy.fill_config or FuturesFillConfig(),
    )

    settlement: TwFuturesSettlementModel = TwFuturesSettlementModel(
        position_manager=position_manager,
        instrument=instrument,
    )

    return Backtester(
        strategy=strategy,
        account=account,
        position_manager=position_manager,
        instrument=instrument,
        fill_model=fill_model,
        cost_model=cost_model,
        settlement=settlement,
        data_feed=TwFuturesDataFeed(),
        reporter_cls=FuturesBacktestReporter,
        event_counts=event_counts,
        adjusted_price=False,
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
