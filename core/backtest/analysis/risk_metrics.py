import math
from typing import List, Optional, Sequence

"""
風險調整後報酬的共用公式

**單獨成檔是為了讓前端與 reporter 用同一份**（見
`backlog/前端指標與報表同源化.md` S3）：同一個指標算兩次、寫在兩個地方，
最後一定會出現「報表說 1.2、前端說 0.8」而沒有人知道哪個對。

原本 `StockBacktestAnalyzer` 的實作有四個問題（健檢 F-068），四個都會讓
數字看起來合理但實際錯誤：

1. **單位不一致**：分子是 `record.roi`（百分比，例如 `2.31`），分母的無風險
   利率是 `0.02`（小數）。兩者差 100 倍，相減等於幾乎沒有扣無風險利率。
2. **沒有年化**：Sharpe 的慣例是年化值，未年化的數字無法與任何外部參考比較。
3. **以「每筆交易」為樣本**：交易筆數與時間無關，一年交易 5 次與 500 次算出
   的「波動度」不可比，年化更無從談起。應以**日報酬**為樣本。
4. **Sortino 的下檔標準差算錯**：舊版對「低於門檻的那些報酬」取 `np.std`，
   那是它們**彼此之間**的離散度；正確定義是相對於門檻的偏差平方，
   除以**全樣本**筆數再開根號。
"""


# 一年的交易日數；年化係數為 √TRADING_DAYS_PER_YEAR
TRADING_DAYS_PER_YEAR: int = 252


def compute_period_returns(equity_curve: Sequence[float]) -> List[float]:
    """
    - Description:
        由權益曲線算出逐期簡單報酬率（小數，非百分比）

        前一期權益為 0 或負數時跳過該期：報酬率在那裡沒有定義，
        補 0 會讓破產的帳戶看起來「那天很平穩」。
    - Parameters:
        - equity_curve: Sequence[float]
            權益序列（第一筆通常是初始資金）
    - Return:
        - List[float]
            逐期報酬率
    """

    returns: List[float] = []
    for previous, current in zip(equity_curve, equity_curve[1:]):
        if previous > 0:
            returns.append(current / previous - 1)
    return returns


def compute_annualized_sharpe(
    returns: Sequence[float],
    risk_free_rate: float = 0.0,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> Optional[float]:
    """
    - Description:
        年化 Sharpe ratio

        `(平均超額報酬 / 超額報酬標準差) × √periods_per_year`。
        **無風險利率與報酬率同為小數**，且先換算成單期再相減。
    - Parameters:
        - returns: Sequence[float]
            逐期報酬率（小數）
        - risk_free_rate: float
            年化無風險利率（小數，例如 0.02 表示 2%）
        - periods_per_year: int
            一年幾期
    - Return:
        - Optional[float]
            年化 Sharpe；樣本不足兩期或標準差為 0 時為 None
            （零筆交易回 None 而不是 0——「沒有資料」與「風險調整後報酬為零」
            是兩件完全不同的事）
    """

    if len(returns) < 2:
        return None

    period_rf: float = risk_free_rate / periods_per_year
    excess: List[float] = [value - period_rf for value in returns]

    mean: float = sum(excess) / len(excess)
    variance: float = sum((value - mean) ** 2 for value in excess) / (len(excess) - 1)
    std: float = math.sqrt(variance)

    if std == 0:
        return None

    return round(mean / std * math.sqrt(periods_per_year), 4)


def compute_annualized_sortino(
    returns: Sequence[float],
    risk_free_rate: float = 0.0,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> Optional[float]:
    """
    - Description:
        年化 Sortino ratio

        與 Sharpe 的差別只在分母：**只罰下檔波動**，且分母是
        「低於門檻的偏差平方和 ÷ **全樣本**筆數」再開根號——不是對低於門檻的
        那幾期取標準差（那是它們彼此之間的離散度，與門檻無關）。
    - Parameters:
        - returns: Sequence[float]
            逐期報酬率（小數）
        - risk_free_rate: float
            年化無風險利率（小數），同時作為下檔門檻（MAR）
        - periods_per_year: int
            一年幾期
    - Return:
        - Optional[float]
            年化 Sortino；樣本不足兩期或完全沒有下檔波動時為 None
    """

    if len(returns) < 2:
        return None

    period_rf: float = risk_free_rate / periods_per_year
    excess: List[float] = [value - period_rf for value in returns]

    mean: float = sum(excess) / len(excess)
    downside_sum: float = sum(min(value, 0.0) ** 2 for value in excess)
    downside_deviation: float = math.sqrt(downside_sum / len(excess))

    if downside_deviation == 0:
        return None

    return round(mean / downside_deviation * math.sqrt(periods_per_year), 4)
