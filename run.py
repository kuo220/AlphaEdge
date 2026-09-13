import argparse
import sys
from typing import Dict, Type

from core.backtest.backtester import Backtester
from core.backtest.factory import build_backtester
from core.config import SHOW_FIGURES_ENV_VAR, resolve_show_figures
from core.strategies.base import BaseStrategy
from core.strategies.strategy_loader import StrategyLoader

"""Main entry point of the trading system: run backtest or live trading from project root"""


# -----------------------------------------------------------------------
# run.py 使用方式說明
# -----------------------------------------------------------------------
# Description: 本檔案為交易系統主程式入口，用於執行指定策略的回測或實盤
# Parameters: --mode (backtest | live), --strategy (策略類別名稱，必填)
# Example: python run.py --strategy MeanReversion
# Notes: Strategy Name 為 Class 名稱
#
# -----------------------------------------------------------------------
# 退出碼
# -----------------------------------------------------------------------
# 0  回測正常結束
# 2  用法錯誤：策略名找不到（與 argparse 自己的用法錯誤同碼，缺 --strategy
#    本來就回 2，兩者對呼叫端是同一類問題，不必再多記一個號碼）
# 1  `--mode live` 尚未實作（NotImplementedError 的預設退出碼）
#
# **舊版兩者都回 0**：找不到策略只 `print` 後 `return`，`--mode live` 是 `pass`。
# 目前 `run.py` 只有人手動跑所以還沒出事，但一旦接進批次（例如每晚重跑策略），
# 「策略名打錯」與「回測跑完」在退出碼上長得一模一樣——那是最典型的假綠燈。
#


# 用法錯誤的退出碼；與 argparse 自己的用法錯誤同碼（缺必填參數時它就回 2）
EXIT_STRATEGY_NOT_FOUND: int = 2


def parse_arguments() -> argparse.Namespace:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Trading System"
    )

    # `live` 保留在 choices 裡（它是規劃中的模式，`--mode` 這個參數才有意義），
    # 但 help 必須講明尚未實作——否則 `--help` 看起來像已經支援實盤
    parser.add_argument(
        "--mode",
        choices=["backtest", "live"],
        default="backtest",
        help="執行模式；`live`（實盤）尚未實作，指定它會以 NotImplementedError 結束",
    )
    parser.add_argument(
        "--strategy", type=str, required=True, help="Name of the strategy class"
    )
    # 回測畫完的五張圖要不要在瀏覽器開起來。**預設不開**：
    # 舊版寫死開啟，每跑一次回測就彈出 5 個分頁，批次掃參數時一次開幾十個，
    # 在無頭環境（CI、容器、nohup）更是直接失敗。圖本來就會存成 PNG。
    show_group = parser.add_mutually_exclusive_group()
    show_group.add_argument(
        "--show",
        dest="show",
        action="store_true",
        default=None,
        help="回測結束後在瀏覽器開啟圖表",
    )
    show_group.add_argument(
        "--no-show",
        dest="show",
        action="store_false",
        help=f"不開啟圖表（未指定時依環境變數 {SHOW_FIGURES_ENV_VAR}，預設不開）",
    )

    return parser.parse_args()


def main() -> None:
    args: argparse.Namespace = parse_arguments()
    strategy_name: str = args.strategy

    strategies: Dict[str, Type[BaseStrategy]] = StrategyLoader.load_strategies()

    if strategy_name not in strategies:
        # 錯誤訊息走 stderr、退出碼非 0：這兩件事缺一不可——訊息印在 stdout
        # 會混進正常輸出，退出碼 0 則讓呼叫端完全看不出失敗
        print(
            f"Strategy '{strategy_name}' not found. "
            "Please check the spelling or ensure it is registered.",
            file=sys.stderr,
        )
        available: str = ", ".join(sorted(strategies)) or "(none)"
        print(f"Available strategies: {available}", file=sys.stderr)
        sys.exit(EXIT_STRATEGY_NOT_FOUND)

    # Initialize strategy
    strategy: BaseStrategy = strategies[strategy_name]()

    # Backtest or Live Trading
    if args.mode == "backtest":
        backtester: Backtester = build_backtester(strategy)
        # 命令列旗標優先於環境變數；兩者都沒給就是不開圖
        backtester.show_figures = (
            resolve_show_figures() if args.show is None else args.show
        )
        backtester.run()
    elif args.mode == "live":
        raise NotImplementedError(
            "實盤模式（--mode live）尚未實作。"
            "目前 `core/utils/account.py` 只有 Shioaji 帳戶工具，沒有下單迴圈；"
            "在那之前請用 --mode backtest。"
        )


if __name__ == "__main__":
    main()
