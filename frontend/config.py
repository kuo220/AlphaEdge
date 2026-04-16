from pathlib import Path
import os


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RESULTS_ROOT = PROJECT_ROOT / "trader" / "backtest" / "results"
RESULTS_ROOT = Path(
    os.getenv("ALPHAEDGE_BACKTEST_RESULTS", str(DEFAULT_RESULTS_ROOT))
).expanduser()

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
}

CSV_FILE_CANDIDATES = ["*trading_report.csv", "trading_report.csv"]
