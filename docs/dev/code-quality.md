# 程式碼品質工具鏈與基線

> 本文件描述 `pyproject.toml`／`ruff`／CI／`pre-commit`／覆蓋率的**現行設定與其理由**，
> 以及兩份需要長期追蹤的基線資料（例外處理、測試覆蓋率）。
> 實作於 2026-08-16 完成；規劃文件已依
> [`manage-backlog` skill §5](../../.claude/skills/manage-backlog/SKILL.md#5-完成後的處理) 移出 `backlog/`。

---

## 概觀

`CLAUDE.md` §2 有 10 節 coding style，但在 2026-08-16 之前**沒有任何自動化在執行這些規範**。
現況已補齊四件事：

| 項目 | 檔案 | 作用 |
|------|------|------|
| 套件定義 | `pyproject.toml` `[project]` | `pip install -e .` 後任意目錄可 `import core` |
| Lint／格式 | `pyproject.toml` `[tool.ruff]` | 執行 `CLAUDE.md` §2.5（import 排序）、§2.10（行寬 88、雙引號） |
| CI | `.github/workflows/ci.yml` | 每次 push 跑 `ruff check` ＋ `ruff format --check` ＋ `pytest -m "not slow"` |
| 本機防線 | `.pre-commit-config.yaml` | commit 前先跑一次同一組檢查（需自行 `pre-commit install`） |

`requirements.txt` 為鎖定版本的完整清單，末行 `-e .` 讓同一份檔案也能裝上專案本身；Docker build 用同一份（建置時會濾掉 `-e` 那行）。

### 常用指令

```bash
python -m pip install -r requirements.txt   # 相依 + 專案本身
python -m pip install -e ".[dev]"           # 追加 pytest / pytest-cov / ruff

ruff check .                        # lint
ruff format .                       # 格式化
pytest -m "not slow"                # 略過需要 tw_stock.db 與外部 API 的測試
pytest                              # 全部（需 data/db/tw_stock.db）
./scripts/run_regression.sh         # LONG ＋ SHORT 回歸，必須逐筆相同
```

### optional extras

`dolphindb`（tick）、`streamlit`（frontend）、`python-docx`（lab）**刻意不放進主
`dependencies`**：它們在開發環境並未安裝，而回測與 ETL 主流程照樣運作。
需要時以 `pip install -e ".[tick]"` 等方式個別安裝。

---

## 一、`ruff` 的 ignore 清單為什麼長這樣

**清單裡的每一條都必須有理由**，分三類。改動前先確認屬於哪一類——尤其第一類，
「順手打開」會直接與專案規範打架。

### 1. 與 `CLAUDE.md` 衝突，永久關閉

| 規則 | 衝突點 |
|------|--------|
| `UP006`／`UP035` | §2.4.3 明訂用 `typing.List`／`Dict`，不改 `list[...]` |
| `UP007` | §2.4.3 `Union[X, Y]`，不改 `X \| Y` |
| `UP045` | §2.4.4 `Optional[T]`，不改 `T \| None` |
| `UP042` | §2.7 明訂 `class XxxEnum(str, Enum)`，不改 `StrEnum` |
| `E501` | formatter 已管行寬，但拆不了中文註解與 docstring；留著只會讓 CI 永遠紅燈，並逼人把中文註解硬折行 |

> **這一類是本次施作最大的陷阱。** 原規劃只列了 `UP006`／`UP035` 要關，
> 但 `UP` 家族實際上還有三條會動型別註解與 Enum 寫法，**合計 433 處**。
> 若照原規劃只關兩條就跑 `ruff check --fix`，會一次改掉 433 個違反專案規範的地方。

### 2. 設計選擇，非缺陷

| 規則 | 理由 |
|------|------|
| `B027` | 基底類別刻意留的 no-op 掛點（例如股票的 `settle_daily`：股票沒有每日結算）。標成 `@abstractmethod` 反而會強迫每個子類別寫空實作 |
| `B905` | `zip(..., strict=)` 屬行為決策：補 `strict=True` 可能讓原本靜默的長度不一致改為拋錯，須逐點確認後再開 |

### 3. 待收斂，暫時關閉

`BLE001`、`TRY003`／`TRY300`／`TRY301`／`TRY201`／`TRY004`，以及下方〈待收斂清單〉的七條。
**修掉之後要把對應規則從 `ignore` 移除**，不要讓它長期留著。

> **為什麼是 ignore 而不是在原地加 `# noqa`**：原本想用「規則保持啟用 ＋ 逐點 noqa」的
> ratchet 作法，讓新程式碼不能再犯。實測失敗——加上中文理由後該行超過 88 字元，
> `ruff format` 就把運算式拆成多行，`noqa` 註解跟著跑到別行、失去效力（21 處全部失效）。
> 若日後要改回 ratchet，`noqa` 必須不帶理由文字，理由寫在本文件。

### per-file-ignores

| 對象 | 規則 | 理由 |
|------|------|------|
| `__init__.py` | `F401` | 套件的 re-export 門面，import 就是對外介面 |
| `tests/*`、`strategy_lab/*` | `E402` | 獨立執行的腳本，import 前有 `sys.path` 設定或條件式 mock |
| `stock_tick_utils.py`、`stock_tick_loader.py`、`manual_tick_updater.py` | `F401` | `dolphindb` 是選用相依，該處 import 是「可用性探測」 |

`*.md` 已加入 `extend-exclude`：ruff 0.16 起會連 Markdown 內的 Python 程式碼區塊一起格式化，
而文件裡的範例常刻意對齊註解以利閱讀。`CLAUDE.md` §2.5／§2.10 規範的對象是程式碼，不是文件。

---

## 二、例外處理現況

**量測日期：2026-08-16**（`ruff 0.16.3`，全專案 179 個 Python 檔）

套上 `select = ["E", "F", "I", "UP", "B", "BLE", "TRY"]` 的第一次全量結果為 **1495 條**：

| 規則 | 數量 | 處置 |
|------|-----:|------|
| E501 line-too-long | 597 | ignore |
| UP045 non-pep604-annotation-optional | 391 | ignore（與 §2.4 衝突） |
| F401 unused-import | 134 | 自動修；`__init__.py` 改用 per-file-ignore |
| F541 f-string-missing-placeholders | 112 | 自動修 |
| **BLE001 blind-except** | **85** | **ignore，待收斂** |
| E402 module-import-not-at-top | 26 | per-file-ignore |
| I001 unsorted-imports | 25 | 自動修 |
| UP042 replace-str-enum | 24 | ignore（與 §2.7 衝突） |
| TRY300 / TRY201 / TRY301 / TRY004 | 29 | ignore，待收斂 |
| UP007 non-pep604-annotation-union | 18 | ignore（同 §2.4） |
| B905 zip-without-explicit-strict | 15 | ignore |
| B027 empty-method-without-abstract | 9 | ignore |
| 其餘 | 30 | 見〈待收斂清單〉 |

**盲捕（`except Exception` 或裸 `except`）實測 85 條。** ETL 場景下這會把「網路逾時」（該重試）
與「資料 schema 變了」（該中止）混為一談，而 `core/pipeline/utils/exceptions.py` 已經定義了
自訂例外卻沒有普及。

**已實際造成損失的案例**：2026-08-16 的 `margin` 回補中，`stock_margin_loader.add_to_db()`
的 `except Exception` → `logger.warning` 讓 2 個檔案入庫失敗被吞掉，行程照樣印
`✅ Database Update Completed` 且結束碼為 0，缺了 1,553 列。收斂工作追蹤於
[ETL 入庫約定](../pipeline/etl-ingestion.md) §4.2。

### 待收斂清單（21 條）

**這些不是樣式問題，是真的可能出錯的地方**：

| 規則 | 位置 | 為什麼要緊 |
|------|------|-----------|
| B008 ×5 | `stock_chip_updater.py:61`、`stock_dividend_updater.py:61`、`stock_margin_updater.py:65`、`stock_price_updater.py:63`、`stock_tick_updater.py:99` | 全部是 `end_date: datetime.date = datetime.date.today()`。**預設值在 import 當下就固定**，長駐排程跑過午夜後仍會拿到啟動那天的日期，等於靜默漏掉最新一天 |
| B006 ×4 | `financial_statement_crawler.py:269`、`data_utils.py:101/106/107` | 可變預設參數，跨呼叫共用同一個物件 |
| B904 ×3 | `finmind_updater.py:157`、`time.py:36/45` | `raise` 未帶 `from`，原始例外被吃掉，debug 時看不到根因 |
| E722 ×3 | `stock_tick_cleaner.py:155/163`、`stock_tick_utils.py:209` | 裸 `except`，會連 `KeyboardInterrupt` 一起吞 |
| F841 ×3 | `stock_price_crawler.py:39/40`、`generate_docs.py:65` | **`crawl_price()` 把 `crawl_twse_price()`／`crawl_tpex_price()` 的回傳值指派後完全沒用**，看起來像未完成的函式，需確認是否為缺陷 |
| F811 ×1 | `callback.py:7` | `OrderState` 同時從 `shioaji.constant` 與 `.constant` import，後者覆蓋前者 |
| B007 ×2 | `manual_db_tables.py:129/142` | 未使用的迴圈變數，無害 |

---

## 三、測試覆蓋率基線

**重測（2026-09-02，全專案架構與邏輯健檢 S1）**：`pytest -m "not slow"` **687 passed / 10 deselected**；`core/` 覆蓋率 **60%**（11,348 行，未覆蓋 4,552）；各子套件：managers 95、backtest/models 90、adapters 90、datafeed 83、models 81、pipeline/shared 79、backtester 75、strategies 65、api 60、utils 54、pipeline/tw 46、backtest/report 42、pipeline/utils 36；仍為 0% 的只剩 `core/api/tw/finmind_api.py` 與 `core/utils/path.py`。`BLE001` 盲捕由 85 增為 96（全在 `core/pipeline/`），待收斂清單由 21 條增為 25 條（行號皆已漂移，見該健檢文件〈附錄 B〉與 F-002／F-010~F-012）。

**首次量測（2026-08-16）**　指令：`pytest -m "not slow" --cov=core --cov-report=term`
（207 passed / 9 deselected）

**整體：7112 行中未覆蓋 4269 行 → 40%**

| 模組 | 覆蓋率 | 說明 |
|------|-------:|------|
| `core/models/` | 77~100% | 資料骨架，回歸線會走到 |
| `core/backtest/models/` | 90~96% | `cost_model` 90、`fill_model` 92、`settlement_model` 90、`sizing` 96 |
| `core/managers/` | 88~97% | `stock/position_manager` 97 |
| `core/backtest/factory.py` | 97% | |
| `core/backtest/backtester.py` | 76% | |
| `core/backtest/report/reporter.py` | 38% | 出圖與報表產出未被回歸線覆蓋（呼應 [多市場回測引擎架構](../backtest/multi-market-engine.md) §6.2「回歸雙線不經過 reporter」） |
| `core/api/` | 32~87% | `stock_price_api` 87、`stock_dividend_api` 74、`stock_margin_api` 32、`stock_tick_api` 33 |
| `core/utils/` | 37~100% | `constant` 100、`instrument` 81、`path` 0 |
| `core/strategies/` | 0~89% | `base` 89、`stock/base` 84，但 `momentum_strategy_1` 26、`overnight_lead_event_strategy` 0、`strategy_loader` 0 |
| **`core/pipeline/`** | **0~39%** | **多數 loader／updater 為 0%**：`monthly_revenue_report_*`、`stock_chip_*`、`stock_dividend_*`、`stock_margin_*`、`stock_price_*`、`financial_statement_updater` 全部 0 |

**刻意不設 `fail_under` 門檻**：在覆蓋率明顯偏低時設門檻只會鼓勵寫無效測試。
補測試的優先順序建議為 `core/pipeline/` 的 loader → `strategy_loader` → `reporter`。

---

## 四、打包時踩到的三個坑

新人重建環境或日後調整 `pyproject.toml` 時會再遇到，記於此：

### 4.1 `core.managers` 等目錄沒有 `__init__.py`

它們靠 PEP 420 namespace package 運作。`[tool.setuptools.packages.find]` 必須設
`namespaces = true`，否則 editable 安裝後 `core.managers.*` 會 import 不到——
而且**不會在安裝時報錯，是執行期才炸**。

### 4.2 CI 只能跑 `-m "not slow"`

`data/db/tw_stock.db` 未進版控（`.gitignore` 有 `*.db`），CI 也沒有 Shioaji／FinMind 金鑰。
需要這些的測試一律標 `@pytest.mark.slow` 或 `pytestmark = pytest.mark.slow`。

目前標為 slow 的有 12 檔（2026-09-02）：`tests/backtest/test_long_regression.py`（需 `tw_stock.db`）與 8 支需要 `tw_futures.db` 或外部 API 的 `tests/test_futures_*.py`，另 3 支為 `manual_*`。`test_short_regression.py` 純記憶體、**不是** slow。

**回歸雙線只在本機跑**：CI 的 `-m "not slow"` 不含 LONG 線，`scripts/run_regression.sh` 也沒有任何 workflow 在執行；且該腳本在沒有 `tw_stock.db` 的機器上會因 `skipif` 而回綠（見 [全專案架構與邏輯健檢](health-check-2026-09.md) F-090／F-095）。動引擎前請在有資料庫的機器手動跑。

### 4.2.1 `tests/manual_*.py` 是手動腳本，**不會被 pytest 收集**

`tests/` 底下有九支 `manual_*.py`，它們是**手動執行的驗證腳本**而不是測試：
沒有斷言（或斷言包在 `try/except` 裡）、大量 `print`、結尾有
`if __name__ == "__main__"` 區塊要人自己填參數。

**2026-09-01 之前它們叫 `test_*.py`，因而被 pytest 收走，造成兩種壞結果**：

| 症狀 | 檔案 | 危險度 |
|------|------|:------:|
| 收集期就 `fixture 'stock_id' not found`（函式帶必填參數，pytest 當成 fixture） | `tick_crawler`（3 個）、`tick_updater`（1 個） | 低——**吵但誠實**，看得出來壞了 |
| 整段包在 `try/except` 且失敗時 `return False`，pytest 判定 **passed** | `broker_trading_updater`、`finmind_api` | **高**——**永遠不會紅**，會被誤當成通過的證據 |

第二種在 2026-09-01 的 FinMind S8 重構時真的害到人：原定驗收是
「`test_broker_trading_updater.py` 通過」，實測那一檔連呼叫不存在的方法都能 passed。

改名為 `manual_*` 之後 pytest 不再收集（預設樣式是 `test_*.py`），基線因此變成
**乾淨的 `N passed, 0 errors`**——之後任何一個 error 都是真的出事。腳本本身沒有改，
仍可用 `python -m tests.manual_db_tables` 之類的方式手動執行。

**新增測試時的判準**：**沒有會失敗的斷言就不是測試**。要驗證行為就寫真的斷言，
要人工探勘就取名 `manual_*`，不要放一支永遠綠的檔案佔著位置。

驗證 CI 是否真的會綠，可用「移除資料庫與金鑰的副本」在本機模擬：

```bash
rsync -a --exclude='.venv' --exclude='.git' --exclude='data/db' --exclude='.env' ./ /tmp/cisim/
cd /tmp/cisim && env -u API_KEY -u API_SECRET_KEY python -m pytest tests -q -m "not slow"
```

### 4.3 macOS：隱藏旗標會讓 `.pth` 完全失效

若 `.venv` 內的檔案帶著 macOS 的 `UF_HIDDEN` 旗標，**CPython ≥3.11 的 `site.addpackage()`
會靜默略過隱藏的 `.pth`**——editable 安裝因此完全不生效，且沒有任何錯誤訊息
（連 setuptools 自己的 `distutils-precedence.pth` 也不會被執行）。

症狀是 `pip install -e .` 顯示成功，但在 repo 以外的目錄 `import core` 仍然 `ModuleNotFoundError`。
檢查與修復：

```bash
ls -lO .venv/lib/python3.12/site-packages/*.pth   # 出現 hidden 即中招
chflags nohidden .venv .venv/lib/python3.12/site-packages \
                 .venv/lib/python3.12/site-packages/*.pth
```

**這個旗標會反覆回來。** 實測在同一個 session 內清除後數分鐘又被重新套上，
且新安裝套件產生的 `.pth`（例如 `pytest-cov` 的 `a1_coverage.pth`）一出生就是隱藏的
——推測是從隱藏的父目錄繼承，或有備份／同步工具在背景重新標記。

因此**不要把 editable 安裝當成本機的可靠前提**。在此環境執行需要 `import core`
的獨立腳本時，直接指定 `PYTHONPATH`：

```bash
PYTHONPATH=. python scripts/some_script.py
```

從 repo 根目錄執行 `python -m pytest` 或 `python run.py` 不受影響（cwd 會進 `sys.path`）。

---

## 五、健檢 C 級結論（2026-09-02）

[全專案架構與邏輯健檢.md](health-check-2026-09.md) 的 C 級中屬工具鏈、研究區與雜項者記於此（引擎與 ETL 的 C 級分別在 [多市場引擎 §九](../backtest/multi-market-engine.md) 與 [ETL 入庫約定 §五](../pipeline/etl-ingestion.md)）：

| 編號 | 位置 | 結論 |
|---|---|---|
| F-006 | `strategy_lab/strategies/tsmc_overnight_signal/reports/` | 全專案唯一的循環 import（`generate_docx` ↔ `docx_append`，以延遲 import 繞過）；`scripts/check_layer_deps.py` 現況因此結束碼 1。**2026-09-04 已解**：共用零件抽成 `docx_common.py`，`generate_docx` 只留 `build_report()` 與 CLI，三檔單向相依、函式內延遲 import 一併移回模組層級；`check_layer_deps.py` 現在結束碼 **0**（違規總數 0），**可以接進 CI／pre-commit 當閘門了**（尚未接，屬 [測試護欄與本機CI容器一致性](../../backlog/測試護欄與本機CI容器一致性.md)） |
| F-010 | `core/pipeline/tw/crawlers/stock_price_crawler.py` | `crawl()` 把 `crawl_twse_price()`／`crawl_tpex_price()` 的回傳值指派後未使用（F841 ×2）；確認是否為未完成的合併邏輯 |
| F-011 | `core/utils/callback.py` | `OrderState` 先從 `shioaji.constant` import 再被 `.constant.OrderState` 覆蓋（F811） |
| F-023 | `core/adapters/tw/stock_quote_adapter.py` | `filtered_stock_ids` 用 list 做 `in` 判斷，全市場 2,000 檔 × 每日；改 set |
| F-029 | `core/api/tw/finmind_api.py`、`stock_tick_api.py` | 不接受共用連線注入、各自開連線；前者覆蓋率 0% |
| F-080 | `core/pipeline/tw/` 與 `tasks/` 共 **15 處**（原列 12 處） | `logger.error(..., exc_info=True)`：loguru 把多餘的 kwargs 當 `str.format()` 參數而默默丟掉，traceback 從未印出。**2026-09-04 全數改為 `logger.opt(exception=True).error(...)`**（訊息字串不動；未用 `logger.exception()` 是為了保留原本的 `logger.error` 語意與訊息）。護欄兩道：`tests/test_entrypoint_and_logging.py` 的 AST 掃描（CI 跑得到，且抓得到 `exc_info=e` 等變體）與 `.pre-commit-config.yaml` 的 pygrep |
| F-088 | `strategy_lab/` | 13 個 `output/*.html` 在 `.gitignore` 規則加入前被追蹤（`git rm --cached`）；`tech_new_high` 的 `END_DATE` 寫死、存活者偏差未列入限制、`load_price_panel()` 繞過 API 直接下 SQL |
| F-098 | `core/config/schema.py` | `FUTURES_CONTRACT_TABLE_NAME` 有宣告無建表；**2026-09-04 已刪除常數**，原處留註解說明未建表、股期乘數走 `futures_stock_universe.contract_size`、指數期貨乘數走 `FUTURES_MULTIPLIER` |
| F-101 | `README.md`／`README_zh.md` | Docker 段落曾分岔；2026-09-03 已以中文版為準回填英文版，兩份檔頭互相標註「以中文版為準」 |

工具鏈側可直接動手的三條已放進 `backlog/測試護欄與本機CI容器一致性.md`（`sys.path.insert` 清理 F-009、per-file-ignores 路徑 F-100、環境變數與相依檔 F-096）。

## 相關文件

- [開發環境設定](../setup/dev-setup.md)——建立 venv 與環境變數
- [多市場回測引擎架構](../backtest/multi-market-engine.md)——§七回歸護欄說明 `scripts/run_regression.sh` 的職責
- `CLAUDE.md` §2——coding style 的權威來源，本文件的 ruff 設定即為其可執行版本
