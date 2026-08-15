import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf
from loguru import logger

from core.backtest.datafeed.base import BaseDataFeed
from core.models import StockAccount, StockOrder, StockPosition, StockQuote
from core.strategies.stock import BaseStockStrategy
from core.utils import Action, Market, PositionType, Scale, Units


class OvernightLeadEventStrategy(BaseStockStrategy):
    """
    Event-driven overnight lead-signal strategy for 2330.

    Features (available before TW open):
    - Previous US session return of TSM
    - Previous US session return of ^SOX
    - Previous US session return of TWD=X

    Signal rule:
    - pred > 0: target long 2330
    - pred <= 0: target flat
    """

    TARGET_STOCK_ID: str = "2330"

    TRAIN_END: datetime.date = datetime.date(2020, 12, 31)
    VAL_START: datetime.date = datetime.date(2021, 1, 1)
    VAL_END: datetime.date = datetime.date(2021, 12, 31)
    TEST_START: datetime.date = datetime.date(2022, 1, 1)
    MODEL_DATA_START: datetime.date = datetime.date(2020, 1, 1)
    MODEL_DATA_END: datetime.date = datetime.date(2026, 4, 25)

    def __init__(self):
        super().__init__()

        # Strategy meta
        self.strategy_name: str = "OvernightLeadEvent"
        self.market: str = Market.STOCK
        self.position_type: str = PositionType.LONG
        self.enable_intraday: bool = False

        # Account
        self.init_capital: float = 1_000_000.0
        self.max_holdings: int = 1

        # Backtest range
        self.scale: str = Scale.DAY
        # Align event-driven evaluation window to RAST test period.
        self.start_date: datetime.date = self.TEST_START
        self.end_date: datetime.date = self.MODEL_DATA_END

        # Signal cache: {date: 0/1}
        self.signal_by_date: Dict[datetime.date, int] = {}
        self.alpha: float = float("nan")

        self._build_signals()

    def setup_account(self, account: StockAccount) -> None:
        self.account = account

    def setup_apis(self, feed: BaseDataFeed) -> None:
        """宣告本策略要用的資料源；實例由 DataFeed 統一持有"""

        if self.scale == Scale.DAY:
            self.price = feed.price

    @staticmethod
    def _ridge_fit_predict(
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_pred: np.ndarray,
        alpha: float,
    ) -> Tuple[np.ndarray, np.ndarray]:
        n, p = X_train.shape
        X1 = np.c_[np.ones(n), X_train]
        reg = np.eye(p + 1)
        reg[0, 0] = 0.0
        coef = np.linalg.solve(X1.T @ X1 + alpha * reg, X1.T @ y_train)
        y_hat = np.c_[np.ones(len(X_pred)), X_pred] @ coef
        return coef, y_hat

    @staticmethod
    def _tune_alpha(
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        grid: np.ndarray,
    ) -> float:
        best_alpha = float(grid[0])
        best_mse = np.inf
        for a in grid:
            _, y_hat = OvernightLeadEventStrategy._ridge_fit_predict(
                X_train, y_train, X_val, float(a)
            )
            mse = float(np.mean((y_val - y_hat) ** 2))
            if mse < best_mse:
                best_mse = mse
                best_alpha = float(a)
        return best_alpha

    def _build_signals(self) -> None:
        """Train ridge and create date->signal map for backtest dates."""
        # 2330 與 strategy_lab 一致：SQLite 收盤；美股特徵仍用 yfinance。
        tw_px = self.price.get_close_series(
            self.TARGET_STOCK_ID, self.MODEL_DATA_START, self.MODEL_DATA_END
        )
        if tw_px.empty:
            raise RuntimeError(
                f"No DB price rows for {self.TARGET_STOCK_ID} in "
                f"{self.MODEL_DATA_START}~{self.MODEL_DATA_END}."
            )
        tw_px = tw_px.astype(float).sort_index()
        tw_px.index = pd.to_datetime(tw_px.index).tz_localize(None).normalize()

        us_tickers = ["TSM", "^SOX", "TWD=X"]
        df = yf.download(
            us_tickers,
            start=self.MODEL_DATA_START.strftime("%Y-%m-%d"),
            end=(self.MODEL_DATA_END + datetime.timedelta(days=1)).strftime("%Y-%m-%d"),
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=True,
        )
        if df.empty:
            raise RuntimeError(
                "yfinance returned empty dataset for US tickers (OvernightLeadEvent)."
            )

        close = (
            df["Close"].copy()
            if isinstance(df.columns, pd.MultiIndex)
            else df[["Close"]]
        )
        if not isinstance(df.columns, pd.MultiIndex):
            close.columns = us_tickers[:1]
        close = close.sort_index()
        close.index = pd.to_datetime(close.index).tz_localize(None).normalize()

        rets = close.pct_change()
        us_calendar = close["TSM"].dropna().index

        rows: List[dict] = []
        for ts in tw_px.index:
            d = pd.Timestamp(ts).normalize()
            prev_us = us_calendar[us_calendar < d]
            if len(prev_us) == 0:
                continue
            us_d = prev_us.max()
            try:
                r_tsm = float(rets.loc[us_d, "TSM"])
                r_sox = float(rets.loc[us_d, "^SOX"])
                r_fx = float(rets.loc[us_d, "TWD=X"])
            except (KeyError, ValueError):
                continue
            if any(np.isnan([r_tsm, r_sox, r_fx])):
                continue
            idx = tw_px.index.get_indexer([d], method="pad")[0]
            if idx <= 0:
                continue
            r_tw = float(tw_px.iloc[idx] / tw_px.iloc[idx - 1] - 1.0)
            if np.isnan(r_tw):
                continue
            rows.append(
                {
                    "date": d.date(),
                    "r_tsm_us": r_tsm,
                    "r_sox_us": r_sox,
                    "r_twd": r_fx,
                    "r_2330": r_tw,
                }
            )

        panel = pd.DataFrame(rows).dropna()
        panel = panel[
            (panel["date"] >= self.MODEL_DATA_START)
            & (panel["date"] <= self.MODEL_DATA_END)
        ]
        panel = panel.drop_duplicates(subset=["date"], keep="last").sort_values("date")
        if panel.empty:
            raise RuntimeError("No aligned panel rows produced for OvernightLeadEvent.")

        x_cols = ["r_tsm_us", "r_sox_us", "r_twd"]
        train = panel[panel["date"] <= self.TRAIN_END]
        val = panel[(panel["date"] >= self.VAL_START) & (panel["date"] <= self.VAL_END)]
        if train.empty or val.empty:
            raise RuntimeError(
                "Training/validation split is empty for OvernightLeadEvent."
            )

        X_tr = train[x_cols].values.astype(float)
        y_tr = train["r_2330"].values.astype(float)
        X_va = val[x_cols].values.astype(float)
        y_va = val["r_2330"].values.astype(float)

        alpha_grid = np.logspace(-4, 3, 30)
        self.alpha = self._tune_alpha(X_tr, y_tr, X_va, y_va, alpha_grid)

        fit = panel[panel["date"] <= self.VAL_END]
        X_fit = fit[x_cols].values.astype(float)
        y_fit = fit["r_2330"].values.astype(float)
        coef, _ = self._ridge_fit_predict(X_fit, y_fit, X_fit, self.alpha)

        pred = np.c_[np.ones(len(panel)), panel[x_cols].values.astype(float)] @ coef
        panel = panel.copy()
        panel["signal"] = (pred > 0.0).astype(int)
        self.signal_by_date = {
            d: int(s) for d, s in zip(panel["date"], panel["signal"])
        }

        logger.info(
            f"[OvernightLeadEvent] signals ready, rows={len(panel)}, alpha={self.alpha:.6f}"
        )

    def check_open_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        if not stock_quotes:
            return []
        quote = next(
            (q for q in stock_quotes if q.stock_id == self.TARGET_STOCK_ID),
            None,
        )
        if quote is None:
            return []
        if self.account.check_has_position(self.TARGET_STOCK_ID):
            return []

        signal = self.signal_by_date.get(quote.date, 0)
        if signal != 1:
            return []
        return self.calculate_position_size([quote], Action.BUY)

    def check_close_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        if not stock_quotes:
            return []
        quote = next(
            (q for q in stock_quotes if q.stock_id == self.TARGET_STOCK_ID),
            None,
        )
        if quote is None:
            return []
        if not self.account.check_has_position(self.TARGET_STOCK_ID):
            return []

        signal = self.signal_by_date.get(quote.date, 0)
        if signal == 1:
            return []
        return self.calculate_position_size([quote], Action.SELL)

    def check_stop_loss_signal(
        self, stock_quotes: List[StockQuote]
    ) -> List[StockOrder]:
        # Keep stop-loss out of this baseline signal model.
        return []

    def calculate_position_size(
        self, stock_quotes: List[StockQuote], action: Action
    ) -> List[StockOrder]:
        orders: List[StockOrder] = []
        if not stock_quotes:
            return orders

        quote = stock_quotes[0]
        if action == Action.BUY:
            if quote.cur_price <= 0:
                return orders
            buy_lots = int(self.account.balance / (quote.cur_price * Units.LOT))
            if buy_lots < 1:
                return orders
            orders.append(
                StockOrder(
                    stock_id=quote.stock_id,
                    date=quote.date,
                    action=Action.BUY,
                    position_type=PositionType.LONG,
                    price=quote.cur_price,
                    volume=buy_lots,
                )
            )
            return orders

        if action == Action.SELL:
            position: Optional[StockPosition] = self.account.get_first_open_position(
                quote.stock_id
            )
            if position is None or position.volume <= 0:
                return orders
            orders.append(
                StockOrder(
                    stock_id=quote.stock_id,
                    date=quote.date,
                    action=Action.SELL,
                    position_type=position.position_type,
                    price=quote.cur_price,
                    volume=position.volume,
                )
            )
        return orders
