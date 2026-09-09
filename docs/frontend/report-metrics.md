# 前端指標與報表同源化（2026-09-09 完成紀錄）

> **本文件是「前端指標與報表同源化」的完成紀錄**，原為
> `backlog/前端指標與報表同源化.md`，四個步驟全數完成後於 2026-09-09 依
> [`manage-backlog` 規範 §5](../../.claude/skills/manage-backlog/SKILL.md#5-完成後的處理)
> 移入 `docs/`。對應[健檢紀錄](../dev/health-check-2026-09.md)的
> F-067／F-082（A 級）／F-083／F-084／F-085。
>
> **留著的原因是三個決定，它們的理由在程式碼裡看不到全貌**：為什麼前端只准
> import `core` 的一個模組、為什麼 `STOCK_SPLITS` 不能照原訂做法刪、
> 以及 Sortino 換公式後數字為何會變。護欄本身在測試裡
> （`tests/test_frontend_*.py`、`tests/backtest/test_reporting.py`）。

## Abstract

- **背景／問題**：[全專案架構與邏輯健檢（2026-09）](../dev/health-check-2026-09.md) S16 抓到 **A 級** F-082：`frontend/app.py` 自行重算指標且與 `core/backtest/report/` 不同源——`平均 ROI` 把已是百分比的 `ROI` 欄再 ×100（實測 `Foreign-Sell-Short-Day-Trade` 報表平均 0.82% 會顯示 82.1%）、資產曲線與日報酬以 `Sell Date` 排序（SHORT 的 `Sell Date` 是開倉日）、權益口徑用已實現累積餘額而非報表的盯市 `daily_equity`、IR 讀的 benchmark 欄位不存在。另有 F-083（本機預設結果目錄指向已不存在的 `core/backtest/results`）、F-084（三份 CSV 與第 5 張圖未讀）、F-085（指標函式無法被測試 import）、F-067（reporter 連線不關、每次開 5 個瀏覽器分頁）。
- **目標**：前端**只讀不算**——所有指標來自 reporter 已落地的 CSV；必要的計算集中在 `frontend/services/` 並與 `core/backtest/analysis/` 共用同一份公式；本機不設環境變數也能開。
- **範圍界線**：不改 reporter 的輸出欄位名（baseline 綁定）；不做新圖表。
- **驗收標準**：以 `results/Foreign-Sell-Short-Day-Trade/` 為 fixture，前端顯示的平均 ROI、勝率、MDD 與 `direction_summary.csv`／`daily_equity.csv` 逐值相同；`pytest tests/test_frontend_*.py` 全綠；`streamlit run frontend/app.py` 不設環境變數即列出 `results/` 下的策略。

> **驗收結果（2026-09-09）**：四步全部完成。`pytest -m "not slow"` **961 passed**
> （開工時 943）；`tests/test_frontend_*.py` 共 34 條全綠；`./scripts/run_regression.sh`
> 雙線通過且無 skip。
>
> ⚠️ **本機沒有安裝 streamlit**（`frontend/requirements.txt` 尚不存在，屬
> [測試護欄](../../backlog/測試護欄與本機CI容器一致性.md) S2 的 F-093），因此
> `streamlit run frontend/app.py` 這條驗收**無法直接執行**。改以替身取代
> Streamlit 模組實跑整條 render 路徑，等價驗到：不設任何環境變數即列出
> 5 個策略、0 次 `st.error`、9 個指標全部有值且與 reporter 的 CSV 逐值相同
> （勝率 59.76%、平均 ROI 0.82%、最大回撤 −11.43%）。

## 進度追蹤表

| 編號 | 步驟名稱 | 產出檔案 | 驗證方式 | 狀態 | 備註／中斷點 |
|------|----------|----------|----------|:----:|--------------|
| S1 | 指標改讀 reporter 輸出：`daily_equity`／`direction_summary`／`event_report`；ROI 不乘 100；一律 `Exit Date` 排序 | `frontend/app.py`、`frontend/services/report_loader.py`、`frontend/config.py`、`tests/test_frontend_report_loader.py` | fixture 對數（見驗收標準）；SHORT 報表的資產曲線單調依平倉順序 | ✅ | **2026-09-09 完成**（`3215a30`）：平均 ROI 由 82.06% 修正為 0.82%，14 條 fixture 對數測試 |
| S2 | 結果目錄預設與環境變數統一 | `frontend/config.py`、`docker-compose.yml`、`frontend/Dockerfile`、`docs/setup/dev-setup.md`、`tests/test_frontend_config.py` | 本機預設 `PROJECT_ROOT/results`；`ALPHAEDGE_RESULTS_DIR` 為主、舊名相容一版並警告 | ✅ | **2026-09-09 完成**（`ec628b7`）：不設環境變數即列出 5 個策略，7 條測試 |
| S3 | 指標函式搬 `services/metrics.py` 並與 `core/backtest/analysis` 共用公式、補測試 | `frontend/services/metrics.py`（新增）、`frontend/static/theme.css`（新增）、`core/backtest/analysis/__init__.py`、`tests/test_frontend_metrics.py`（新增） | Sharpe／Sortino／MDD 手算範例測試；`app.py` 不再定義任何計算函式 | ✅ | **2026-09-09 完成**（`ca15639`）：**Sortino 因換用正確公式而改變**（2.014 → 3.378）；13 條測試 |
| S4 | reporter 可維護性：關連線、`show` 開關、benchmark 改用還原價 | `core/backtest/report/{reporter,futures_reporter}.py`、`run.py`、`core/backtest/backtester.py`、`core/config/settings.py` | 回測結束無殘留連線；批次模式不開瀏覽器；LONG 回歸不變 | ✅ | **2026-09-09 完成**（`b19b17d`）：⚠️ **`STOCK_SPLITS` 未刪**，理由見 S4 完成紀錄 |

## 步驟詳述

### S1. 指標改讀 reporter 輸出 ✅

- **目的**：F-082、F-084。
- **做法**：`report_loader` 增讀三份 CSV；總覽區塊的勝率／損益／平均 ROI 取自 `direction_summary.csv`（或以 `Realized PnL`／`ROI` 直接平均，不乘 100）；資產曲線、每日損益、MDD 讀 `daily_equity.csv`；事件計數區塊顯示 `event_report.csv`；第 5 張圖加入圖片頁；`_extract_starting_capital` 改 `首列 Cumulative Balance − Realized PnL`；缺檔時明確提示而非畫 0。
- **產出**：見進度表。
- **驗證方式**：fixture 對數測試。
- **相依**：無。

> **✅ 完成紀錄（2026-09-09，commit `3215a30`）**
>
> 以 `results/Foreign-Sell-Short-Day-Trade/` 為 fixture 逐值比對，四個錯全部修掉：
>
> | 指標 | 修正前 | 修正後 |
> |------|:---:|:---:|
> | 平均 ROI | 82.06% | **0.82%** |
> | 起始資金 | 1,011,269 | **1,000,000** |
> | 最大回撤 | 未顯示 | **−11.43%**（盯市口徑）|
>
> **`Information Ratio` 直接移除**：它讀的 benchmark 欄位在任何報表裡都不存在，
> 舊版等於拿 NaN 充數。改顯示最大回撤，並在 caption 說明 IR 需要基準的日報酬序列。
>
> ⚠️ **實作時抓到一個自己種下的 bug**：依 `Exit Date` 排序時 pandas 預設的
> `quicksort` **不穩定**，會打亂同一天平倉的多筆，而 `Cumulative Balance` 是
> 依列序累加的——本 fixture 從第 60 列起就對不上。必須指定 `kind="stable"`。
> 這條已固化為測試（`test_sort_by_exit_date_keeps_balance_monotonic`）。
>
> 讀取與彙總全部放進 `report_loader.py`（純資料、不含 Streamlit 呼叫）才測得到。
> 缺檔一律顯示明確訊息並說明「為什麼不能改用另一個口徑湊」，不再靜靜畫 0。

### S2. 結果目錄預設與環境變數統一 ✅

- **目的**：F-083。
- **做法**：`frontend/config.py` 預設改 `PROJECT_ROOT / "results"`（不 import `core`，避免前端映像必須帶 `core/`）；環境變數統一 `ALPHAEDGE_RESULTS_DIR`，`ALPHAEDGE_BACKTEST_RESULTS` 保留一版相容並 warning；compose／Dockerfile／docs 同步。
- **產出**：見進度表。
- **驗證方式**：本機不設變數即可列出策略。
- **相依**：無。

> **✅ 完成紀錄（2026-09-09，commit `ec628b7`）**
>
> 預設值改 `PROJECT_ROOT / "results"`、環境變數統一為 `ALPHAEDGE_RESULTS_DIR`，
> 舊名 `ALPHAEDGE_BACKTEST_RESULTS` 只在新名未設時生效並發出 `DeprecationWarning`。
> compose／Dockerfile／`dev-setup.md`／`prod-deployment.md`／README／SKILL 同步。
>
> **修正前實測會在 `st.stop` 就結束**（整頁「找不到任何回測結果資料夾」），
> 修正後以 `env -u` 清掉兩個變數仍列出 5 個策略、0 次 `st.error`。
>
> 路徑解析抽成 `resolve_results_root(env)`，環境變數來源可注入才測得到。
> `frontend/config.py` **刻意不 import `core`**（前端映像只 COPY `frontend/`），
> 代價是「兩邊算出同一個路徑」沒有 import 可以保證，改由一條測試盯住。

### S3. 指標函式搬 `services/` 並共用公式 ✅

- **目的**：F-085。
- **做法**：`_extract_*`／`_calc_*` 搬到 `frontend/services/metrics.py`；年化 Sharpe／Sortino 的實作放 `core/backtest/analysis/`，前端 import；CSS 抽成 `frontend/static/theme.css`。
- **產出**：見進度表。
- **驗證方式**：新測試。
- **相依**：S1。

> **✅ 完成紀錄（2026-09-09，commit `ca15639`）**
>
> **Sortino 的數字因此變了：fixture 由 2.014 變成 3.378**。舊版對「低於門檻的
> 那幾期」取 `std(ddof=0)`，那是它們**彼此之間**的離散度；正確定義是相對門檻的
> 偏差平方、除以**全樣本**筆數再開根號。Sharpe 未變（樣本 1,459 筆，`ddof`
> 差異在小數第三位以下）。這正是「同一個指標寫兩份」會發生的事。
>
> ⚠️ **S3 原訂的「前端 import `core`」與 S2 的「前端映像不帶 `core/`」直接衝突**，
> 解法是讓那個 import 變便宜：`core/backtest/analysis/__init__.py` 原本
> eager import analyzer，於是 import 一個**只相依 `math` 與 `typing`** 的
> `risk_metrics` 會經由套件 `__init__` 拉進 pandas／numpy／loguru →
> `stock_price_api` → shioaji 與 sqlite3，實測 **1,164 個模組、431 ms**。
> 改成不 eager import 之後剩 **10 個模組**（作法與 `core/backtest/__init__.py`
> 既有的註解一致；現有呼叫端本來就都走完整路徑，零改動）。
> `frontend/Dockerfile` 因此只 COPY 四個檔案的最小鏈。
>
> 兩條 AST 測試護住這個安排：`app.py` 不得再有計算函式、前端只准 import
> `core` 的 `risk_metrics`；另有一條以**子行程**量測 import 成本，
> 已實測「把 eager import 放回去就會紅」。
> CSS 由 `app.py` 的 137 行行內字串抽成 `frontend/static/theme.css`。

### S4. reporter 可維護性 ✅

- **目的**：F-067。
- **做法**：reporter 改吃 `data_feed.price` 或結束時 `close()`；`Backtester.run()` 以 `try/finally` 關 feed；`set_figure_config(show=…)` 由 `run.py --show/--no-show` 或環境變數決定；benchmark 改 `adjusted=True` 取還原收盤並刪 `STOCK_SPLITS`。
- **產出**：見進度表。
- **驗證方式**：LONG 回歸不變（報表層不在回歸線內，另以 `test_reporting.py` 補一條 benchmark 還原價測試）。
- **相依**：無。

> **✅ 完成紀錄（2026-09-09，commit `b19b17d`）**
>
> ⚠️ **`STOCK_SPLITS` 未依原訂做法刪除**——刪了會把 F-087 修好的東西再打壞。
> 以真實 DB 實測 0050 在 2025-06-18 一拆四：
>
> | 只用 `get_adjusted_close_series()` | 再套 `apply_split_adjustment()` |
> |:---:|:---:|
> | 該日 **−74.8%** 的假跌幅 | **1.8%** |
>
> 原因 `core/api/tw/stock_split.py` 的模組說明本來就寫著：`stock_dividend`
> 只記除權息、不含分割。該表的移除相依
> [還原價缺非除權息公司行動](../../backlog/還原價缺非除權息公司行動.md) S2 的 `corporate_action`
> ETL，屬**那條線的 S3**，不是本步驟做得掉的。benchmark 改用還原價這半邊已完成。
>
> **連線**：reporter 新增 `close()` 並改吃 Backtester 傳入的 `StockPriceAPI`
> （原本自己再開一條，一次回測兩條連線且從不關閉）；`Backtester.run()` 改
> `try/finally`——舊版 `close()` 是最後一行，而回測常在中途炸，那正是連線
> 會累積的路徑。共用連線不歸 reporter 關，沿用 `owns_conn`，不再寫第二份判斷。
>
> **圖表預設不開瀏覽器**：新增 `resolve_show_figures()` 與
> `run.py --show/--no-show`，優先序為旗標 > `ALPHAEDGE_SHOW_FIGURES` > 不開。
> 環境變數只認明確真值——「有設就當成開」會讓習慣寫 `VAR=0` 的人踩到反效果。
> `FuturesBacktestReporter` 的簽章同步加上 `price`／`show` 並轉發，
> 否則 Backtester 統一傳參會 TypeError。
