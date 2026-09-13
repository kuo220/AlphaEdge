# 健檢第四輪收斂（2026-09 完成紀錄）

## Abstract

- **背景／問題**：2026-09-13 對全 repo 做第四輪掃描（前三輪見 全專案架構與邏輯健檢（2026-09-02）、2026-09-04 的「健檢殘留項目收斂」與 健檢第三輪收斂，後兩者皆已結案移出）。本輪抓到 7 條。**唯一有資料正確性與工時風險的是 S1**：F-056 的修法（只有「表不存在」回 `None`，其餘 `sqlite3` 錯誤上拋）只套在 `core/pipeline/utils/sqlite_utils.py`，**期貨線的 1 個 loader ＋ 4 支 API 共 8 處仍在吞掉整個 `sqlite3.OperationalError`**，資料庫被鎖住時 updater 會從預設起日整段重爬、回測會靜默少開倉。其次是 S2：三支護欄腳本只有一支進了 CI 與 pre-commit，**`check_doc_paths.py` 在本輪掃描時於 HEAD 上就是紅的（5 處）而沒有任何人發現**。
- **目標**：同一類「吞掉 sqlite 錯誤」的寫法在全專案只有一種行為；三支護欄腳本都有閘門，紅了就擋得住；死程式碼與重複實作清掉；型別標註與執行期產物治理回到 `CLAUDE.md` 的規範。
- **範圍界線**：**不動 `core/pipeline/utils/data_utils.py`、`core/pipeline/tw/utils/mops_payload.py`、`core/pipeline/tw/crawlers/financial_statement_crawler.py` 與 [命名軸線](naming-axes.md)**——2026-09-13 另一條線正在收斂 `Payload`，這四檔有未提交變更。**不改 ETL 的分批與失敗語意**（屬 [爬蟲缺口回補與非交易日批次清理](../../backlog/爬蟲缺口回補與非交易日批次清理.md)）。**不動 `core/pipeline/utils/constant.py` 的欄位 Enum**（屬 [PostgreSQL遷移計畫](../../backlog/PostgreSQL遷移計畫.md) Phase2-3 的 F-007）。**不追求覆蓋率數字**，S5 只補失敗語意的測試。
- **驗收標準**：`pytest -m "not slow"` 全綠且條數不減；`./scripts/run_regression.sh` 雙線通過（本份工作預期**零數值變動**）；`python scripts/check_layer_deps.py`、`check_doc_paths.py`、`check_api_orphan_methods.py` 三支皆結束碼 0，且後兩支已進 CI；全專案 `grep -rn "except sqlite3.OperationalError" core/` 為 0。

> **驗收結果（2026-09-13，7 條全數結案）**
>
> | 驗收條件 | 動工前 | 完成後 |
> |----------|--------|--------|
> | `pytest -m "not slow"` | 993 passed | **1008 passed** |
> | `./scripts/run_regression.sh` | 雙線通過 | 雙線通過，**零數值變動如預期** |
> | `ruff check .` / `format --check` | 全綠 | 全綠（且 `ANN201`／`ANN204` 已納入閘門） |
> | `check_layer_deps.py` | 0 | 0 |
> | `check_doc_paths.py` | 0 | 0（**已進 CI 與 pre-commit**） |
> | `check_api_orphan_methods.py` | 0 | 0（**已進 CI**） |
> | `grep -rn "except sqlite3.OperationalError" core/` | 8 處 | 0 處 |
>
> **本輪三個值得記住的教訓**：
>
> 1. **要測「一個目錄進不了版控」，不能測目錄路徑本身**。S6 的 `.ruff_cache` 那半條
>    是誤判——ruff 會在快取目錄內寫一份 `.gitignore`（內容 `*`）自我排除，
>    `git check-ignore .ruff_cache` 卻回報未命中。該測底下的檔案或直接 `git add -n`。
> 2. **批次補型別標註時，抽象方法必須單獨挑出來人工判**。它們的 body 是 `pass`，
>    任何「看這個函式有沒有 return 值」的自動化都會得到 `None`，而契約在子類身上。
>    S4 有 4 個因此被標錯。
> 3. **規劃時要先查既有測試**。S5 情境 2 早就有人寫過了，是四個月內第二次發生
>    「標為待做、其實做過」（第三輪的 F-010／F-023 同型）。

## 進度追蹤表

| 編號 | 步驟名稱 | 產出檔案 | 驗證方式 | 狀態 | 備註／中斷點 |
|------|----------|----------|----------|:----:|--------------|
| S1 | 期貨線 8 處吞 `sqlite3.OperationalError` 收斂 | `core/api/base.py`、`core/pipeline/tw/loaders/futures_chip_loader.py`、`core/api/tw/` 三支 API、`tests/test_sqlite_error_semantics.py` | 表不存在仍回 `None`／`0`；其餘 sqlite 錯誤上拋；以「鎖住的 DB」實測會拋而非靜默 | ✅ | **2026-09-13 完成**：8 處全清，新增 12 條測試，**其中 9 條實測在修正前會失敗**。回歸雙線零數值變動 |
| S2 | 兩支護欄腳本進 CI 與 pre-commit | `.github/workflows/ci.yml`、`.pre-commit-config.yaml` | 三支腳本在 CI 皆執行且結束碼 0；刻意寫一個搬過家的路徑要當場紅 | ✅ | **2026-09-13 完成**：那 5 處漂移已由同日另一條線的文件整理清掉，本步驟只剩補閘門 |
| S3 | 刪除死程式碼 `core/utils/path.py` | `core/utils/path.py`（刪） | 全專案零引用；`pytest -m "not slow"` 全綠 | ✅ | **2026-09-13 完成**：與 `core/config/paths.py` 的同名函式逐行相同。`code-quality.md` 未改——該檔的覆蓋率基線段落已被同日的文件整理移除。**本步驟同時把 [測試護欄](../../backlog/測試護欄與本機CI容器一致性.md) S6 的該子項做掉** |
| S4 | 補齊缺漏的回傳型別標註並開啟 ANN 閘門 | `core/**`、`tasks/`、`frontend/`、`tests/`、`pyproject.toml`、`docs/dev/code-quality.md` | `ruff check .` 全綠且 `ANN201`／`ANN204` 已在 `select` 內 | ✅ | **2026-09-13 完成**：實際補 **181 處**（不只 150，`tests/` 另有 41 處）。⚠️ 過程中抓到 **4 個抽象方法被自動化補錯**，見該步驟 |
| S5 | ETL 層失敗語意的測試補強 | `tests/test_sqlite_error_semantics.py`、`tests/test_loader_failure_reporting.py` | 四個情境各有測試覆蓋 | ✅ | **2026-09-13 完成**：情境 1 隨 S1（12 條）、情境 3 新增 1 條、情境 4 補期貨線 2 條；⚠️ 情境 2 實查發現**早就有測試**，情境 4 的 tick 半邊**不適用** |
| S6 | 執行期產物治理：測試暫存 DB | `tests/test_finmind_loader_broker_trading.py` | 連跑兩次 `pytest`，`tests/temp/` 不再產生 | ✅ | **2026-09-13 完成**：改用 `tmp_path`，該目錄不再出現。⚠️ **`.ruff_cache` 那半條實查後判定不必做**，理由見該步驟 |
| S7 | 過寬的 `except Exception` 收斂 | `core/pipeline/tw/cleaners/corporate_action_cleaner.py` | 只捕 `ValueError`／`TypeError`，其餘上拋 | ✅ | **2026-09-13 完成**：實際只有 **1 處**（原記「兩處」有誤，`:271` 本來就只捕 `ValueError`） |

## 步驟詳述

### S1. 期貨線 8 處吞 `sqlite3.OperationalError` 收斂 ✅

- **目的**：F-056 已經定案過這個問題的正確寫法——**只有「表不存在」與「表是空的」該回 `None`，其餘 sqlite 錯誤一律上拋**——但當時只修了 `core/pipeline/utils/sqlite_utils.py`。期貨線有 8 處是舊寫法：

  ```python
  # core/pipeline/tw/loaders/futures_chip_loader.py:158
  def get_latest_date(self, table: str) -> Optional[str]:
      """表內最新的資料日期；供 updater 續跑（表不存在時為 None）"""

      self.connect()
      try:
          row = self.conn.execute(f"SELECT MAX(date) FROM {table}").fetchone()
      except sqlite3.OperationalError:      # ← 表不存在、被鎖住、schema 壞掉，長得一模一樣
          return None
      return row[0] if row else None
  ```

  docstring 寫的是「表不存在時為 None」，但 `OperationalError` 同時涵蓋 `database is locked`、`disk I/O error`、`malformed` 與欄名打錯。

- **三條已驗證的後果**（2026-09-13 逐處追呼叫端）：

  1. **整段重爬**：`core/pipeline/tw/updaters/futures_chip_updater.py` 的 `resolve_start_date()` 拿到 `None` 就 `return start_date or self.DEFAULT_START_DATE`。背景有另一支 ETL 正在寫 `tw_futures.db` 時，續跑會從預設起日重來，而 log 只會顯示一個正常的起始日期。
  2. **入庫統計變負數**：同一支 loader 的 `count_rows()` 出錯時回 `0`，而 `inserted = self.count_rows(table) - before`——後一次查詢失敗就會印出「新增 -1234 列」。
  3. **回測靜默少開倉**：`core/api/tw/futures_chip_api.py`、`futures_margin_api.py`、`futures_stock_universe_api.py` 共 6 處同樣寫法，回測期間資料庫被鎖住會讓策略拿到 `None`，**沒有任何錯誤、只是少開幾筆倉**。這正是 [模組使用關係](../backtest/module-map.md) §六反覆強調要避免的失敗模式。

- **做法**：比照 `SQLiteUtils.check_table_exist()` 先明確判斷表是否存在，其餘 `sqlite3.OperationalError` 不捕：

  ```python
  if not SQLiteUtils.check_table_exist(conn=self.conn, table_name=table):
      logger.debug(f"Table '{table}' does not exist yet. Normal for first-time updates.")
      return None
  row = self.conn.execute(f"SELECT MAX(date) FROM {table}").fetchone()
  ```

  `core/api/` 這一側要注意**不要**反向 import `core/pipeline/`（那是 F-007 已登記的相依），把 `check_table_exist` 搬到 `core/api/base.py` 或抽到 `core/config/` 以下的共用層，這一步與 F-007 的最小切法一致。

- **產出**：`core/pipeline/tw/loaders/futures_chip_loader.py`、`core/api/tw/` 三支 API、`core/api/base.py`、`tests/`。
- **驗證方式**：對一個**被另一個連線鎖住**的資料庫呼叫這 8 個方法，修正前全部靜默回 `None`／`0`，修正後全部拋出；表不存在的情境行為不變。既有的 `tests/test_futures_margin.py` 與期貨籌碼相關測試必須不變。
- **相依**：無。與 F-007 建議同批施作（`check_table_exist` 的落點是同一個決定）。

> **✅ 完成紀錄（2026-09-13）**
>
> **8 處全清**，`grep -rn "except sqlite3.OperationalError" core/` 只剩 `core/api/base.py`
> 那段說明為什麼不該這樣寫的註解。
>
> **`check_table_exist` 的落點選了 `core/api/base.py`**（新增一支 static method），
> 讀取層因此不必反向 import ETL 套件。`core/pipeline/utils/sqlite_utils.py` 那份保持不動，
> **兩份各自存在是刻意的**——F-007 要移除的正是 `core/api` → `core/pipeline` 這條相依，
> 為了一個五行的 `sqlite_master` 查詢再建一條相依會把那條路堵死。
> 兩份的行為以測試釘住（`test_check_table_exist_tells_missing_from_present`）。
>
> **新增 `tests/test_sqlite_error_semantics.py`，12 條**。鎖住的資料庫用真鎖模擬而非
> mock：另一條連線 `BEGIN EXCLUSIVE` 後，讀取端以 `timeout=0` 連線，
> 於是連 `sqlite_master` 都讀不到——這正是「背景 ETL 正在寫同一個檔」時的實況。
>
> **實測：修正前 12 條中有 9 條失敗**（把五個原始檔 stash 起來跑）。
> 另外 3 條是「表還沒建仍要回 `None`／`0`」，修正前後都必須通過——
> 它們擋的是「把正常路徑一起改成拋例外」這種過度修正。
>
> **驗收數字**：`pytest -m "not slow"` 由 993 增為 **1005 passed**；
> `./scripts/run_regression.sh` 雙線實際執行、**零數值變動**；
> `ruff check .` 全綠；三支護欄腳本皆 exit 0。

### S2. 兩支護欄腳本進 CI 與 pre-commit ✅

- **目的**：`scripts/` 底下有三支護欄腳本，但只有 `check_layer_deps.py` 同時進了 [CI](../../.github/workflows/ci.yml) 與 pre-commit。另兩支只能靠人想起來手動跑，於是：

  **2026-09-13 實測 `python scripts/check_doc_paths.py` 在 HEAD 上結束碼 1，5 處漂移**：

  | 文件 | 寫的是（搬家前的路徑） | 實際在 |
  |------|------------------------|--------|
  | `docs/dev/health-check-2026-09.md` | `config.py` 在 `core/` 根下 | `core/config/`（已拆為套件） |
  | `docs/dev/health-check-2026-09.md` | `stock_tick_loader.py` 在 `core/pipeline/loaders/` | `core/pipeline/tw/loaders/` |
  | `docs/dev/health-check-round3-2026-09.md` | 同上兩條 ＋ `url_manager.py` 的舊路徑 | `core/pipeline/tw/utils/` |

  （本表刻意不寫出完整舊路徑，否則這份文件自己就會被同一支腳本判為漂移。）

  成因是這支腳本的 `_HISTORICAL_DOCS`（歷史紀錄檔豁免清單）在第三輪結案時被清空，而兩份健檢紀錄的內文路徑沒有一起處理。**沒有閘門，所以紅了三天沒人知道。**

- **做法**：
  1. 先決定那 5 處的處置：兩份都是**完成紀錄**，改內文路徑會讓紀錄失真，所以傾向把它們放回 `_HISTORICAL_DOCS`（第三輪已為 `health-check-2026-09.md` 做過同樣判斷，理由見該檔檔頭）。若決定改寫，就要連同「當時的路徑就是那樣」這件事一起在檔頭說明。
  2. `check_doc_paths.py` 與 `check_api_orphan_methods.py` 各加一個 CI step，位置接在分層相依檢查之後。兩支都是純靜態掃描、不需要資料庫。
  3. pre-commit 只加 `check_doc_paths.py`（`check_api_orphan_methods.py` 要 import `core/api`，比較慢，留給 CI）。
- **產出**：`.github/workflows/ci.yml`、`.pre-commit-config.yaml`、`scripts/check_doc_paths.py`。
- **驗證方式**：三支腳本在 CI 皆執行且結束碼 0；刻意在文件裡寫一個搬過家的路徑，CI 要當場紅。
- **相依**：無。**但與 [測試護欄與本機CI容器一致性](../../backlog/測試護欄與本機CI容器一致性.md) S6 是同一個檔案群**（那一步要改 `pyproject.toml` 的 per-file-ignores），建議同批施作。

> **✅ 完成紀錄（2026-09-13）**
>
> **那 5 處漂移不必處理了**：同日另一條線的文件整理（`c6bab3e`，「`docs/` 只留現行
> 說明文件」）把兩份健檢紀錄的內文路徑一併收掉，動工前複查時三支腳本已全綠。
> 原訂的「放回 `_HISTORICAL_DOCS` 還是改寫」這個決定因此消失。
>
> **閘門**：CI 在分層相依檢查之後加兩個 step（`check_doc_paths.py`、
> `check_api_orphan_methods.py`）；pre-commit 只加前者——後者要 import `core/api`，
> 比它慢一個量級，留給 CI。
>
> **實測閘門會咬**：在 `docs/dev/code-quality.md` 末尾故意寫一個搬過家的路徑，
> `check_doc_paths.py` 當場 exit 1；還原後回到 0。
>
> ⚠️ **pre-commit hook 本身未實跑**：本機沒裝 `pre-commit` CLI。已驗證的是
> 兩份 YAML 語法正確（`yaml.safe_load`）＋ hook 要跑的那道指令本身會正確紅燈。
> 裝了 `pre-commit` 的機器請跑一次 `pre-commit run check-doc-paths --all-files` 確認。

### S3. 刪除死程式碼 `core/utils/path.py` ✅

- **目的**：`core/utils/path.py`（21 行、覆蓋率 **0%**）有兩個函式，**全專案零引用**：

  - `get_static_resolved_path()`：與 `core/config/paths.py` 的同名函式**實作完全相同**，而全部 35 個路徑常數用的是 `config/paths.py` 那一份。
  - `get_env_resolved_path()`：零呼叫，且簽章 `default: str = None` 的型別標註是錯的（應為 `Optional[str]`，違反 `CLAUDE.md` §2.4）。`config/paths.py` 另有一支 `get_env_path()`，簽章不同、用途才是現行的容器掛載覆寫。

  [程式碼品質基線](code-quality.md) 先前把這一檔記成「覆蓋率 0%」，是把**死程式碼**當成了**測試缺口**——補測試是錯的處置，該做的是刪掉。

- **做法**：`git rm core/utils/path.py`，確認 `core/utils/__init__.py` 沒有 re-export（實查：沒有）。
- **產出**：`core/utils/path.py`（刪）。
- **驗證方式**：`grep -rn "utils.path\|get_env_resolved_path" core tasks tests frontend scripts` 為 0；`pytest -m "not slow"` 全綠。
- **相依**：無。

> **✅ 完成紀錄（2026-09-13）**
>
> 刪除前逐行比對確認兩份 `get_static_resolved_path()` **實作完全相同**（含 docstring），
> 而 35 個路徑常數與 `core/config/schema.py` 用的都是 `config/paths.py` 那一份。
>
> **兩處與原規劃不同**：
>
> - `docs/dev/code-quality.md` **沒有改**——原訂要把「覆蓋率 0%」那一條改為已刪除，
>   但該檔的覆蓋率基線段落已在同日的文件整理（`c6bab3e`）中移除，沒有東西要改。
> - 這一刪同時完成了 [測試護欄與本機CI容器一致性](../../backlog/測試護欄與本機CI容器一致性.md) S6
>   的「刪 `core/utils/path.py` 併入 `config/paths.py`」子項。**併入那半不需要做**：
>   `config/paths.py` 早就有自己的同名函式，被刪的那一份沒有任何獨有邏輯。

### S4. 補齊缺漏的回傳型別標註並開啟 ANN 閘門 ✅

- **目的**：`CLAUDE.md` §2.4 要求「所有函式參數與回傳值都要標註型別，包含回傳 `None` 的 `-> None`」，實查 `core/`／`tasks/`／`frontend/`／`scripts/` 共 **150 處**沒有回傳標註，其中絕大多數是 `__init__`（`core/strategies/base.py:14`、`core/backtest/backtester.py:75`、`core/api/base.py:14`、四個 `pipeline/shared/*base*.py` 等）。**ruff 目前沒有啟用 `ANN` 規則，所以這條規範完全沒有機器護欄**，新程式碼可以繼續漏。
- **做法**：分批補 `-> None`（`__init__` 與 `setup()` 佔多數，機械性改動）；補完後在 `pyproject.toml` 的 `select` 加入 `ANN204`（`__init__` 缺回傳）與 `ANN201`（公開函式缺回傳），把規範變成閘門。若某些位置刻意不標，用 per-file-ignores 並在 `code-quality.md` 寫理由。
- **產出**：`core/**`、`tasks/**`、`frontend/**`、`tests/**`、`pyproject.toml`、`docs/dev/code-quality.md`。
- **驗證方式**：`ruff check .` 全綠；`pytest -m "not slow"` 條數不變（純標註不改行為）。
- **相依**：無。建議排在 S1 之後，避免與 S1 改到的檔案衝突。

> **✅ 完成紀錄（2026-09-13）**
>
> **實際補 181 處**，不是原估的 150——原掃描只看 `core/`／`tasks/`／`frontend/`／
> `scripts/`／`run.py`，`tests/` 另有 41 處。補法是以 AST 找出「函式本身沒有帶值的
> `return`、也沒有 `yield`」者（不含內層函式），再用 tokenize 定位簽章結尾的冒號插入
> `-> None`，最後交給 `ruff format` 重排。
>
> ⚠️ **自動化把 4 個抽象方法標錯了，逐一對照子類簽章才抓到**。這是本步驟最值得記住的坑：
> 抽象方法的 body 是 `pass`，用「函式自己有沒有 return 值」判斷必然得到 `None`，
> **但它的契約由子類決定**：
>
> | 位置 | 自動化標成 | 子類實際回傳 | 改為 |
> |------|-----------|--------------|------|
> | `core/backtest/analysis/base.py` `compute_equity_curve()` | `None` | `List[float]` | `List[float]` |
> | 同上 `compute_mdd()` | `None` | `float` | `float` |
> | `core/pipeline/shared/base_crawler.py` `crawl()` | `None` | `None`／`Optional[DataFrame]`／`Optional[str]`／`Dict`／`CrawlResult` 五種 | `Any` ＋ 註明理由 |
> | `core/pipeline/shared/base_loader.py` `add_to_db()` | `None` | 6 支回 `None`、4 支回 `int` | `Any` ＋ 註明理由 |
>
> 另外逐一確認 35 個被標成 `-> None` 的抽象方法中其餘 31 個是對的
> （`setup`／`connect`／`plot_*`／`settle_daily`／`update` 等，子類清一色 `-> None`），
> 以及 4 個 B027 的 no-op 掛點（`apply_price_limit_basis` 等）子類也都回 `None`。
>
> **閘門**：`pyproject.toml` 的 `select` 加入 `ANN201`／`ANN204`。
> `tests/*` 與 `scripts/manual/*` 對 `ANN201` 具名豁免——那 24 處是測試 helper 與
> 手動腳本，回傳型別多半是「被 monkeypatch 過的 loader」或 `(物件, 路徑)`，
> 標註要嘛得把類別從函式內部的 import 搬到檔頭（會讓 monkeypatch 失效）、
> 要嘛只能寫 `Any`。**`ANN204` 對全專案生效**，`__init__` 一律要 `-> None`。
> 理由寫進 [程式碼品質基線](code-quality.md) 的 per-file-ignores 表。
>
> **實測閘門會咬**：對 `core/probe.py` 餵一個沒標註的 `__init__` 與 `def f(): return 1`，
> 兩條規則都報；同一份內容改成 `tests/probe.py` 只報 `ANN204`，與設計一致。
>
> **驗收**：`pytest -m "not slow"` **1005 passed**（與動工前相同）、`ruff check .` 全綠、
> `ruff format --check .` 309 檔無變動、回歸雙線零數值變動、三支護欄腳本皆 exit 0。

### S5. ETL 層失敗語意的測試補強 ✅

- **目的**：2026-09-13 實測 `core/` 整體覆蓋率 **66%**（12,682 行，未覆蓋 4,315），但 ETL 層明顯偏低，最低的十幾檔全在 `core/pipeline/tw/`：

  | 檔案 | 覆蓋率 |
  |------|-------:|
  | `core/pipeline/tw/updaters/stock_tick_updater.py` | 12% |
  | `core/pipeline/tw/loaders/financial_statement_loader.py` | 18% |
  | `core/pipeline/tw/cleaners/stock_tick_cleaner.py` | 19% |
  | `core/pipeline/tw/cleaners/stock_chip_cleaner.py` | 20% |
  | `core/pipeline/tw/loaders/monthly_revenue_report_loader.py` | 20% |

  **不要為了數字補測試**（CI 的覆蓋率步驟刻意不設門檻，理由寫在 `ci.yml`）。真正的缺口是**失敗語意**：前三輪健檢的 A／B 級幾乎都是「錯誤被吞成正常」（F-030、F-050、F-052、F-056），而這一層正是那些 bug 的所在地。

- **做法**：只補四個情境，每個情境一條會失敗的測試：
  1. ~~資料庫被鎖住時，loader 與 updater 必須拋而不是回預設起日（與 S1 同一組）。~~ **2026-09-13 已隨 S1 完成**，見 `tests/test_sqlite_error_semantics.py` 的 12 條。
  2. 清洗後為空（`cleaned empty`）必須與「來源沒資料」分開統計。
  3. 表不存在時的首次更新路徑必須正常走完。
  4. 單批入庫失敗時 `finish_load()` 的統計數字正確（已有 `tests/test_loader_failure_reporting.py`，補 tick 與期貨兩條路徑）。
- **產出**：`tests/`。
- **驗證方式**：每條測試都要**先在修正前實測會失敗**（前三輪的慣例）。
- **相依**：情境 1 相依 S1。

> **✅ 完成紀錄（2026-09-13）**
>
> 四個情境的實際結果**與規劃有兩處不同**：
>
> | 情境 | 結果 |
> |------|------|
> | 1. 鎖住的 DB 必須拋 | 隨 S1 完成，`tests/test_sqlite_error_semantics.py` 12 條，修正前 9 條會失敗 |
> | 2. `cleaned empty` 與「沒有資料」分開統計 | ⚠️ **早就有測試**：`tests/test_equity_change_interruption.py` 的 `test_cleaned_empty_is_counted_separately`（2026-09-04 隨權益變動表 S6 寫的），規劃時沒查到。不必重寫 |
> | 3. 表不存在時的首次更新路徑走得完 | 新增 1 條：`resolve_start_date()` 在表還沒建時退回 `DEFAULT_START_DATE`。**這條擋的是修 S1 時的過度修正**——把「表不存在」也改成拋例外，剛 clone 的機器第一次更新就會失敗 |
> | 4. 單批入庫失敗時 `finish_load()` 的統計 | 補期貨線 2 條（日行情、標的池）。⚠️ **tick 半邊不適用**：`stock_tick_loader.add_to_db()` 根本沒呼叫 `finish_load()`，它的失敗語意是另一條路徑（F-052），歸「ETL 失敗語意與缺口回補」 |
>
> **順手發現一個未收斂的不一致**：期貨線的 `failed_files` 存**完整路徑**，
> 台股線（price／margin）只存**檔名**。兩邊的失敗清單格式不同，讀 log 的人
> 看到的東西也不同。本輪不改（會動到兩條線的 loader），但測試已用
> 「檔名出現在清單裡」的斷言寫成兩種格式都通得過，並在該處註明。

### S6. 執行期產物治理：測試暫存 DB ✅

- **目的**：兩個洞：

  1. **`tests/temp/` 無上限累積**。`tests/test_finmind_loader_broker_trading.py:45-48` 每跑一次就在 `tests/temp/` 建一個帶時間戳的 SQLite 檔且**從不刪除**：

     ```python
     temp_dir: Path = project_root / "tests" / "temp"
     temp_dir.mkdir(parents=True, exist_ok=True)
     temp_db_path: str = str(temp_dir / f"test_finmind_loader_opt_{timestamp}.db")
     ```

     2026-09-13 清理時已累積 **560 個檔案、275 MB**（最舊的是 2026-08-02，最大的單檔 12 MB）。目錄有 `.gitignore` 所以不會進版控，但會一直吃磁碟，而且 `pytest` 跑得越多長得越快。
  2. **`.ruff_cache` 沒進 `.gitignore`**（`.pytest_cache`、`.coverage`、`tests/temp/`、`alphaedge.egg-info` 都有）。目前沒出事只是因為沒有人 `git add -A`。

- **做法**：測試改用 pytest 內建的 `tmp_path` fixture（跑完自動清、且每個測試互相隔離）。
- **產出**：`tests/test_finmind_loader_broker_trading.py`。
- **驗證方式**：連跑兩次 `pytest -m "not slow"`，`tests/temp/` 不再產生。
- **相依**：無。這是本輪最小、最適合先做的一步。

> **✅ 完成紀錄（2026-09-13）**
>
> 測試改吃 `tmp_path`，順手移除檔尾的 `if __name__ == "__main__"` 直跑區塊
> （改用 fixture 後它無法再直接呼叫）與因此用不到的 `datetime` import。
> 實測：清空 `tests/temp/` 後連跑兩次 `pytest -m "not slow"`，**該目錄不再出現**，
> 993 passed 不變。
>
> ⚠️ **`.ruff_cache` 那半條實查後判定不必做，原判斷是錯的**。
> 我當時用 `git check-ignore .ruff_cache` 測**目錄本身**而回報未命中，
> 但 ruff 會在 `.ruff_cache/.gitignore` 寫入 `*` **自我排除整個目錄內容**
> （`.pytest_cache` 同樣機制），實測 `git add -An .ruff_cache` 無任何輸出，
> 加不進版控。`.gitignore` 第 57 行本來就寫明了這件事。
> **教訓：要測一個目錄是否真的進不了版控，該測它底下的檔案或直接試 `git add -n`，
> 不是測目錄路徑。**
>
> `docs/dev/runtime-artifacts.md` 也不必改——`tests/temp/` 已經不再產生，
> 沒有需要寫進產物約定的東西。

### S7. 過寬的 `except Exception` 收斂 ✅

- **目的**：`core/pipeline/tw/cleaners/corporate_action_cleaner.py:259` 的日期解析用 `except Exception: return None` 收掉所有例外。同一支檔案 `:271` 的 `_extract_detail_number()` 只捕 `ValueError`，寫法正確，可見前者是疏漏而非設計。
- **做法**：縮到 `except (ValueError, TypeError)`。
- **範圍界線**：**本步驟只處理這兩處**。全 `core/` 共 93 處 `except Exception`、3 處裸 `except:`（E722，全在 tick 舊叢集且隨後 `raise`），逐處判讀屬 F-002／F-012 的 ruff 收斂批次，不在本輪。
- **產出**：`core/pipeline/tw/cleaners/corporate_action_cleaner.py`。
- **驗證方式**：`pytest -m "not slow"` 全綠；公司行動相關測試不變。
- **相依**：無。

> **✅ 完成紀錄（2026-09-13）**
>
> **實際只有 1 處，原記「兩處」有誤**：`:271` 的 `_extract_detail_number()` 本來就只捕
> `ValueError`，是正確寫法，它被我的掃描器列出來只因為它「回 None 且不 log」。
>
> 收斂為 `except (ValueError, TypeError)` 並附註理由。逐一確認 `try` 區塊裡真正會拋的
> 東西：`text.split("/")` 拆不出三段（ValueError）、`int(month)`／`int(day)` 非數字
> （ValueError）、`datetime.date()` 日期超出範圍（ValueError）、以及
> `TimeUtils.convert_roc_to_ad_year()` 對無效年份**明確改拋 ValueError**（該函式內部
> 已把 `ValueError`／`TypeError` 轉成帶訊息的 ValueError）。兩個型別即足夠覆蓋。

## 本輪確認健康（下次健檢可跳過）

以下項目本輪實查過、沒有問題，記在這裡以免下一輪重做一遍：

| 項目 | 實查結果 |
|------|----------|
| `ruff check .` / `ruff format --check .` | 全綠，309 檔已格式化 |
| `pytest -m "not slow"` | **993 passed**、19 deselected（上一輪結案時為 975） |
| `TODO`／`FIXME`／`XXX`／`HACK` | 全專案 **0 處** |
| 測試裡的 `except: pass` | **0 處**（`tests/` 的 `return False` 亦已在前一輪降到 2） |
| 「無斷言的測試」9 處 | **全部是誤判**：3 條回歸線的斷言在 `assert_matches_snapshot()` helper 裡，其餘 6 條是「呼叫後不得拋例外」型的測試，那本身就是斷言 |
| `print()` 擴散 | `core/` 共 14 處，全在 Shioaji／tick 舊叢集，與 `CLAUDE.md` §2.9 記錄的既有例外一致，未擴散 |
| `datetime.now()` 未帶 tz | 4 處，全在 `tasks/clean_logs.py` 與 `scripts/manual/`，皆為本機日誌時間用途，非交易時序 |
| `core/utils/instrument.py` 等共用層 | 無市場語意洩漏；`check_layer_deps.py` 的 A~E 節皆 0 |
| `strategy_lab/` 循環 import | 已解除（第三輪），本輪複查仍 0 |
| 直接 `sqlite3.connect` 65 處 | 全在 `core/pipeline/` 與 `core/api/`，屬 [PostgreSQL遷移計畫](../../backlog/PostgreSQL遷移計畫.md) Phase1-1／Phase2-1 的既有登記，不是新問題 |
