import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RESULTS_ROOT = PROJECT_ROOT / "core" / "backtest" / "results"
_env_results_root = os.getenv("ALPHAEDGE_BACKTEST_RESULTS")
if _env_results_root:
    RESULTS_ROOT = Path(_env_results_root).expanduser()
else:
    RESULTS_ROOT = DEFAULT_RESULTS_ROOT

# 允許舊檔名與新版輸出並存，避免前端因命名差異讀不到
CHART_FILE_CANDIDATES = {
    "資產曲線": ["*balance_curve.png", "balance_curve.png"],
    "資產與基準比較": [
        "*balance_and_benchmark_curve.png",
        "*networth.png",
        "balance_and_benchmark_curve.png",
        "networth.png",
    ],
    "最大回撤": ["*balance_mdd.png", "*mdd.png", "balance_mdd.png", "mdd.png"],
    "每日損益": ["*everyday_profit.png", "everyday_profit.png"],
    # 盯市口徑的每日權益變化（F-084：reporter 早就在畫，前端一直沒讀）
    "每日權益變化": [
        "*everyday_equity_change.png",
        "everyday_equity_change.png",
    ],
}

CSV_FILE_CANDIDATES = ["*trading_report.csv", "trading_report.csv"]

# reporter 另外落地的三份 CSV（F-084）。前端**只讀不算**，指標一律以這些為準：
# - daily_equity：逐日盯市權益，資產曲線／每日損益／MDD 的唯一來源
# - direction_summary：多空分開的績效統計，總覽的勝率／損益／平均 ROI 取自此
# - event_report：強制回補、拒單等尾部事件計數
DAILY_EQUITY_FILE_CANDIDATES = ["*daily_equity.csv", "daily_equity.csv"]
DIRECTION_SUMMARY_FILE_CANDIDATES = [
    "*direction_summary.csv",
    "direction_summary.csv",
]
EVENT_REPORT_FILE_CANDIDATES = ["*event_report.csv", "event_report.csv"]
