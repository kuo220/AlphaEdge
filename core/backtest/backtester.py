import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Type

import pandas as pd
from loguru import logger

from core.backtest.datafeed.base import BaseDataFeed
from core.backtest.models.cost_model import BaseCostModel
from core.backtest.models.fill_model import BaseFillModel
from core.backtest.models.instrument_spec import InstrumentSpec
from core.backtest.models.settlement_model import BaseSettlementModel
from core.backtest.report.base import BaseBacktestReporter
from core.config import BACKTEST_RESULT_DIR_PATH
from core.managers.base.position_manager import BasePositionManager
from core.models import (
    BaseAccount,
    BaseOrder,
    BasePosition,
    BaseQuote,
    BaseTradeRecord,
)
from core.strategies.base import BaseStrategy
from core.utils import (
    Action,
    BarExecutionOrder,
    PositionType,
    Scale,
    TimeUtils,
)
from core.utils.log_manager import LogManager

"""Backtesting engine that simulates trading based on strategy signals"""


def new_event_counts() -> Dict[str, int]:
    """
    建立事件計數器

    放空策略的尾部風險不能被平均掉，需單獨計數。六個 key 與報表相容，不可更名。
    由 factory 建立後同時交給引擎與 FillModel，兩邊共用同一個 dict。
    """

    return {
        "rejected_direction": 0,  # 方向不合法被剔除的訂單
        "rejected_fill_price": 0,  # 成交價不合理被拒的訂單
        "forced_cover_day_trade": 0,  # 當沖日終強制回補
        "forced_cover_margin_call": 0,  # 維持率追繳強制回補
        "forced_cover_max_holding": 0,  # 超過最長持有天數強制回補
        "forced_cover_suspended": 0,  # 停券日強制回補
        "forced_cover_no_quote": 0,  # 連續無報價（停牌／下市）強制出場
        "limit_up_cover_failed": 0,  # 漲停鎖死無法回補
        "rejected_max_holdings": 0,  # 超過最大持倉檔數被引擎剔除的開倉單
        "rejected_no_borrow": 0,  # 融券餘額不足被拒的放空開倉單
        "rejected_volume_cap": 0,  # 超過當日成交量上限被拒的訂單
        "truncated_by_volume": 0,  # 超過當日成交量上限被縮量的訂單
    }


class Backtester:
    """
    Backtest Framework: Tick and Daily price intervals

    **唯一引擎，市場無關，無子類**：市場差異全部由注入的 model 決定
    （`InstrumentSpec` / `FillModel` / `CostModel` / `SettlementModel` / `DataFeed`）。
    新增一個市場不需要修改本檔案，只需在 factory 組出另一組 model。
    """

    # === Init & Data Loading ===
    def __init__(
        self,
        strategy: BaseStrategy,
        account: BaseAccount,
        position_manager: BasePositionManager,
        instrument: InstrumentSpec,
        fill_model: BaseFillModel,
        cost_model: BaseCostModel,
        settlement: BaseSettlementModel,
        data_feed: BaseDataFeed,
        reporter_cls: Type[BaseBacktestReporter],
        event_counts: Optional[Dict[str, int]] = None,
        adjusted_price: bool = False,
    ):
        self.strategy: BaseStrategy = strategy  # 要回測的策略
        self.account: BaseAccount = account  # 虛擬帳戶資訊
        self.position_manager: BasePositionManager = position_manager  # 倉位管理器

        # 可插拔的市場行為
        self.instrument: InstrumentSpec = instrument  # 商品規格
        self.fill_model: BaseFillModel = fill_model  # 成交價可信度
        self.cost_model: BaseCostModel = cost_model  # 手續費／稅／持有成本
        self.settlement: BaseSettlementModel = settlement  # 一根 bar 收盤後的強制動作
        self.data_feed: BaseDataFeed = data_feed  # 資料載入與交易日判定
        self.reporter_cls: Type[BaseBacktestReporter] = reporter_cls  # 報表產生器

        # 回測參數
        self.scale: str = self.strategy.scale  # 回測 KBar 級別
        self.max_holdings: Optional[int] = self.strategy.max_holdings  # 最大持倉檔數
        self.start_date: datetime.date = self.strategy.start_date  # 回測起始日
        self.cur_date: datetime.date = self.strategy.start_date  # 回測當前日
        self.end_date: datetime.date = self.strategy.end_date  # 回測結束日

        # 回測結果輸出目錄
        self.strategy_result_dir: Optional[Path] = None  # 策略回測結果資料夾

        # 含未實現損益的每日權益序列（只認已實現損益會低估留倉放空的 MDD）
        self.daily_equity: List[Dict[str, Any]] = []

        # 事件統計：由 factory 傳入時與 FillModel 共用同一個 dict
        self.event_counts: Dict[str, int] = (
            event_counts if event_counts is not None else new_event_counts()
        )

        # 是否以還原價（後復權）計算訊號。
        # **預設關閉**：開啟會改變所有策略的訊號，LONG baseline 必然失效，
        # 須單獨重產（重產的代價見 `docs/backtest/multi-market-engine.md`〈回歸護欄〉）
        self.adjusted_price: bool = adjusted_price

        self.setup()

    @property
    def intraday_range(self) -> Dict[str, Tuple[float, float]]:
        """Tick 級別的當日累計高低點；狀態由 FillModel 持有"""

        return self.fill_model.intraday_range

    @property
    def prev_close(self) -> Dict[str, float]:
        """前一交易日收盤價；狀態由 FillModel 持有"""

        return self.fill_model.prev_close

    def setup(self) -> None:
        """Set Up the Config of Backtester"""

        # 確保每個 strategy 有獨立的結果資料夾
        self.strategy_result_dir: Path = (
            Path(BACKTEST_RESULT_DIR_PATH) / self.strategy.strategy_name
        )
        self.strategy_result_dir.mkdir(parents=True, exist_ok=True)

        # Set Log File Path
        LogManager.setup_backtest_logger(self.strategy.strategy_name)

        # load backtest dataset
        self.load_datasets()

    def load_datasets(self) -> None:
        """
        - Description:
            載入回測資料，並把資料源交給策略

            **API 實例全專案只建一次**：先由 DataFeed 建立，再交給策略取用，
            策略不自行 new（見 backlog Phase2-7）。
        """

        self.data_feed.setup(self.strategy)
        self.strategy.setup_apis(self.data_feed)

    # === Direction Setting ===
    def get_allowed_directions(self) -> Set[PositionType]:
        """取得允許的訂單方向白名單；策略未指定時等同其宣告方向"""

        return self.strategy.allowed_directions or {self.strategy.position_type}

    def get_execution_order(self) -> BarExecutionOrder:
        """
        - Description:
            決定單根 K 棒內的執行順序；策略顯式指定時一律以策略為準

            放空當沖必須「先開後平」才可能同日結清，其餘情境維持既有的「先平後開」
        - Return:
            - order: BarExecutionOrder
        """

        if self.strategy.bar_execution_order is not None:
            return self.strategy.bar_execution_order

        if (
            self.strategy.position_type == PositionType.SHORT
            and self.strategy.enable_intraday
        ):
            return BarExecutionOrder.OPEN_THEN_CLOSE

        return BarExecutionOrder.CLOSE_THEN_OPEN

    @staticmethod
    def resolve_open_action(position_type: PositionType) -> Action:
        """開倉動作：LONG 為買進、SHORT 為賣出（依訂單方向，不看策略）"""

        return Action.BUY if position_type == PositionType.LONG else Action.SELL

    @staticmethod
    def resolve_close_action(position_type: PositionType) -> Action:
        """平倉動作：LONG 為賣出、SHORT 為買進回補"""

        return Action.SELL if position_type == PositionType.LONG else Action.BUY

    # === Order Validation ===
    def validate_orders(self, orders: List[BaseOrder], stage: str) -> List[BaseOrder]:
        """
        - Description:
            檢查訂單方向是否合法，不合法者剔除並記錄，禁止靜默丟棄
        - Parameters:
            - orders: List[BaseOrder]
                策略回傳的訂單
            - stage: str
                "open" 或 "close"，決定期望的動作
        - Return:
            - valid_orders: List[BaseOrder]
                通過檢查的訂單
        """

        allowed: Set[PositionType] = self.get_allowed_directions()
        valid_orders: List[BaseOrder] = []

        for order in orders:
            if order.position_type not in allowed:
                logger.warning(
                    f"[Validate Order] {order.symbol} 方向 {order.position_type} "
                    f"不在策略允許的 {allowed} 內，已剔除"
                )
                self.event_counts["rejected_direction"] += 1
                continue

            expected_action: Action = (
                self.resolve_open_action(order.position_type)
                if stage == "open"
                else self.resolve_close_action(order.position_type)
            )
            if order.action != expected_action:
                logger.warning(
                    f"[Validate Order] {order.symbol} {stage} 動作應為 {expected_action}，"
                    f"實際為 {order.action}，已剔除"
                )
                self.event_counts["rejected_direction"] += 1
                continue

            valid_orders.append(order)

        return valid_orders

    def enrich_orders(self, orders: List[BaseOrder]) -> List[BaseOrder]:
        """補上市場專屬的訂單欄位；規則由 CostModel 實作（見 backlog Phase2-4）"""

        return self.cost_model.enrich_orders(orders)

    def validate_fill_price(self, order: BaseOrder, quote: BaseQuote) -> bool:
        """成交價合理性檢查；規則由 FillModel 實作（見 backlog Phase2-2）"""

        return self.fill_model.validate(order, quote)

    def apply_fill_model(
        self, order: BaseOrder, quote: Optional[BaseQuote]
    ) -> Optional[BaseOrder]:
        """
        - Description:
            套用市場執行假設（券源、滑價、成交量上限），回傳實際可成交的訂單

            未啟用任何假設時回傳原物件本身，行為與導入前逐筆相同。
            查無報價時直接放行——那是資料缺口，不是成交假設該處理的事。
        - Parameters:
            - order: BaseOrder
                策略產生的訂單
            - quote: Optional[BaseQuote]
                同一標的的當根 bar 報價
        - Return:
            - Optional[BaseOrder]
                可成交的訂單；不可成交時為 None
        """

        if quote is None:
            return order

        return self.fill_model.fill(order, quote)

    def get_price_range(
        self, quote: BaseQuote
    ) -> Tuple[Optional[float], Optional[float]]:
        """取得該報價可成交的價格區間；規則由 FillModel 實作"""

        return self.fill_model.get_price_range(quote)

    def update_intraday_range(self, quotes: List[BaseQuote]) -> None:
        """累計 Tick 級別的當日高低點；狀態由 FillModel 持有"""

        self.fill_model.update_intraday_range(quotes)

    def update_prev_close(self, quotes: List[BaseQuote]) -> None:
        """收盤後記錄當日收盤價；狀態由 FillModel 持有"""

        self.fill_model.on_bar_close(quotes)

    # === Main Backtest Loop ===
    def run(self) -> None:
        """Execute Backtest"""

        logger.info("========== Backtest Start ==========")
        logger.info(f"* Strategy Name: {self.strategy.strategy_name}")
        logger.info(
            f"* Backtest Period: {self.start_date.strftime('%Y/%m/%d')} ~ {self.end_date.strftime('%Y/%m/%d')}"
        )
        logger.info(f"* Initial Capital: {self.strategy.init_capital}")
        logger.info(f"* Backtest Scale: {self.scale}")

        # load backtest period
        dates: List[datetime.date] = TimeUtils.generate_date_range(
            start_date=self.start_date, end_date=self.end_date
        )

        for date in dates:
            logger.info(f"--- {date.strftime('%Y/%m/%d')} ---")

            if not self.data_feed.is_market_open(date):
                logger.info("* Market Close\n")
                continue

            if self.scale == Scale.TICK:
                self.run_tick_backtest(date)

            elif self.scale == Scale.DAY:
                self.run_day_backtest(date)

        self.account.update_account_status()

        logger.info(f"""
            1. Initial Capital: {int(self.account.init_capital)}
            2. Balance: {int(self.account.balance)}
            3. Total realized pnl: {int(self.account.realized_pnl)}
            4. ROI: {round(self.account.roi, 2)}%
            """)

        # Generate Backtest Report
        self.generate_backtest_report()

        # 關閉資料連線（原本全專案的 conn 從不 close，見 backlog Phase2-7）
        self.data_feed.close()

    def run_tick_backtest(self, date: datetime.date) -> None:
        """Tick 級別的回測架構"""

        quotes: List[BaseQuote] = self.data_feed.get_quotes(date, Scale.TICK)

        if not quotes:
            return

        self.fill_model.on_bar_open(quotes)
        self.execute_bar(date, quotes)

    def run_day_backtest(self, date: datetime.date) -> None:
        """日 K 級別的回測架構"""

        quotes: List[BaseQuote] = self.data_feed.get_quotes(
            date, Scale.DAY, adjusted=self.adjusted_price
        )

        if not quotes:
            return

        self.execute_bar(date, quotes)

    def execute_bar(self, date: datetime.date, quotes: List[BaseQuote]) -> None:
        """
        - Description:
            單一時間切片的完整流程：依設定的執行順序開平倉，再做收盤後的部位檢查
        - Parameters:
            - date: datetime.date
                當前交易日
            - quotes: List[BaseQuote]
                當根 bar 的報價
        """

        # 除權息日的漲跌停基準由交易所另行公告，須在下任何單之前覆寫，
        # 否則整段漲跌停區間會沿用偏高的前一交易日收盤而失準
        self.fill_model.apply_price_limit_basis(
            self.data_feed.get_price_limit_basis(date)
        )
        self.fill_model.apply_short_balance(self.data_feed.get_short_balance(date))

        if self.get_execution_order() == BarExecutionOrder.OPEN_THEN_CLOSE:
            self.execute_open_signal(quotes)
            self.execute_close_signal(quotes)
        else:
            self.execute_close_signal(quotes)
            self.execute_open_signal(quotes)

        # 一根 bar 收盤後由市場規則強制執行的動作
        # 台股：當沖強制回補 ＋ 借券費計提 ＋ 維持率追繳
        # 期貨：每日結算 ＋ 保證金追繳 ＋ 到期換月
        self.settlement.on_bar_close(date, quotes, self.account, self.event_counts)

        self.snapshot_daily_equity(date, quotes)
        self.update_prev_close(quotes)

    # === Signal Execution ===
    def execute_open_signal(self, quotes: List[BaseQuote]) -> List[BasePosition]:
        """若倉位數量未達到限制且有開倉訊號，則執行開倉"""

        # Get open orders
        open_orders: List[BaseOrder] = self.strategy.check_open_signal(quotes)

        # 方向驗證 → 補值 → 成交價驗證，最後才進倉位管理器
        open_orders = self.enrich_orders(self.validate_orders(open_orders, "open"))
        quote_map: Dict[str, BaseQuote] = {q.symbol: q for q in quotes}

        # Execute open orders
        open_positions: List[BasePosition] = []
        for order in open_orders:
            if not self.check_max_holdings(order):
                continue

            quote: Optional[BaseQuote] = quote_map.get(order.symbol)
            if quote and not self.validate_fill_price(order, quote):
                continue

            filled_order: Optional[BaseOrder] = self.apply_fill_model(order, quote)
            if filled_order is None:
                continue

            open_position: Optional[BasePosition] = self.position_manager.open_position(
                filled_order
            )
            if open_position:
                open_positions.append(open_position)
        return open_positions

    def check_max_holdings(self, order: BaseOrder) -> bool:
        """
        - Description:
            引擎側的持倉檔數硬上限

            `max_holdings` 原本只是「策略願意遵守才生效」的建議值——引擎讀進來
            卻從未使用，實際上限由每支策略自己在 `calculate_position_size()` 內
            把關。一支新策略只要不呼叫 sizer 就能無限開倉，且不會有任何警告。

            本檢查讓它成為真正的風控。既有策略本來就自我約束，此處不應觸發；
            **若 LONG 回歸因此破線，代表現有策略確實有超額開倉，屬實錯**。
        - Parameters:
            - order: BaseOrder
                待執行的開倉單
        - Return:
            - bool
                True 表示可以開倉
        """

        # None 表示不限制（與 EqualWeightSizer 的語意一致）
        if self.max_holdings is None:
            return True

        if self.account.get_position_count() < self.max_holdings:
            return True

        logger.warning(
            f"[Max Holdings] {order.symbol} 開倉單超過持倉檔數上限 "
            f"{self.max_holdings}，已剔除"
        )
        self.event_counts["rejected_max_holdings"] += 1
        return False

    def execute_close_signal(self, quotes: List[BaseQuote]) -> List[BaseTradeRecord]:
        """執行平倉邏輯：先判斷停損訊號，後判斷一般平倉"""

        # Find symbols with existing positions
        positions: List[BaseQuote] = [
            q for q in quotes if self.account.check_has_position(q.symbol)
        ]

        if not positions:
            return

        quote_map: Dict[str, BaseQuote] = {q.symbol: q for q in quotes}

        # Get stop loss orders
        stop_loss_orders: List[BaseOrder] = self.strategy.check_stop_loss_signal(
            positions
        )
        stop_loss_orders = self.validate_orders(stop_loss_orders, "close")

        # Close records
        close_records: List[BaseTradeRecord] = []

        # Execute stop loss orders
        for order in stop_loss_orders:
            # 平倉同樣套用市場執行假設（滑價、成交量上限）；
            # 但**不做**價格合理性檢查——那是既有的開倉專屬擋板，
            # 若在此新增會讓原本必定成交的平倉單可能被拒，改變既有行為
            filled_order: Optional[BaseOrder] = self.apply_fill_model(
                order, quote_map.get(order.symbol)
            )
            if filled_order is None:
                continue

            close_positions: List[BaseTradeRecord] = (
                self.position_manager.close_position(filled_order)
            )
            close_records.extend(close_positions)

        # After executing stop loss, recheck the remaining positions
        remaining_positions: List[BaseQuote] = [
            q for q in quotes if self.account.check_has_position(q.symbol)
        ]

        # Get close orders
        close_orders: List[BaseOrder] = self.strategy.check_close_signal(
            remaining_positions
        )
        close_orders = self.validate_orders(close_orders, "close")

        # Execute close orders
        for order in close_orders:
            filled_order: Optional[BaseOrder] = self.apply_fill_model(
                order, quote_map.get(order.symbol)
            )
            if filled_order is None:
                continue

            close_positions: List[BaseTradeRecord] = (
                self.position_manager.close_position(filled_order)
            )
            close_records.extend(close_positions)

        return close_records

    # === Daily Equity ===
    def snapshot_daily_equity(
        self, date: datetime.date, quotes: List[BaseQuote]
    ) -> float:
        """
        - Description:
            記錄含未實現損益的每日權益，並更新各部位的未實現損益

            只認已實現損益的權益曲線會把「持倉期間的逆勢」完全抹平，
            而那正是放空最大的風險來源（見 backlog §7.7 註）。
        - Parameters:
            - date: datetime.date
                當前交易日
            - quotes: List[BaseQuote]
                當根 bar 的報價
        - Return:
            - equity: float
                當日權益（現金 + 部位價值）
        """

        quote_map: Dict[str, BaseQuote] = {q.symbol: q for q in quotes}
        position_value: float = 0.0

        for position in self.account.get_positions():
            price: float = self.settlement.get_mark_price(position, quote_map)
            units: int = self.instrument.to_units(position.volume)

            if position.position_type == PositionType.SHORT:
                # 開倉時只扣了保證金與成本，賣出價款留作擔保品
                position.unrealized_pnl = round((position.price - price) * units, 2)
                position_value += position.margin + position.unrealized_pnl
            else:
                position.unrealized_pnl = round((price - position.price) * units, 2)
                position_value += price * units

            cost_basis: float = position.price * units
            position.unrealized_roi = (
                round(position.unrealized_pnl / cost_basis * 100, 2)
                if cost_basis
                else 0.0
            )

        equity: float = round(self.account.balance + position_value, 2)
        self.daily_equity.append({"Date": date, "Equity": equity})
        return equity

    # === Report ===
    def generate_backtest_report(self) -> None:
        """Generate backtest report"""

        # Generate Backtest Report (Chart)
        reporter: BaseBacktestReporter = self.reporter_cls(
            self.strategy, self.strategy_result_dir
        )
        reporter.trading_report = reporter.generate_trading_report()

        # 逐日權益交給 reporter，四張圖才有辦法用盯市口徑（否則 MDD 被低估）
        reporter.daily_equity = self.daily_equity

        # 多空分開統計與事件計數（放空的尾部風險不可被平均掉）
        reporter.generate_direction_summary()
        reporter.generate_event_report(self.event_counts)

        if self.daily_equity:
            reporter.save_report(
                pd.DataFrame(self.daily_equity),
                f"{self.strategy.strategy_name}_daily_equity.csv",
            )

        reporter.plot_balance_curve()
        reporter.plot_balance_and_benchmark_curve()
        reporter.plot_balance_mdd()
        reporter.plot_everyday_profit()
        reporter.plot_everyday_equity_change()
