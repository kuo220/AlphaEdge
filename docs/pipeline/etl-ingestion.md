# ETL 入庫約定

> 本文件描述 `core/pipeline/` **入庫階段**的現行約定：分批時機、冪等性、失敗語意與結束碼。
> 實作於 2026-08-16 完成；規劃文件已依
> [`manage-backlog` skill §5](../../.claude/skills/manage-backlog/SKILL.md#5-完成後的處理) 移出 `backlog/`。
>
> **各項設計的理由寫在程式碼的 docstring**（`BaseDataLoader.insert_dataframe()` /
> `finish_load()` / `select_csv_files()`、`DataLoadError`、`tasks.update_db.target_guard()`）。
> 本文件只放**跨檔案的全貌**與新增 updater 時的檢查表，不重複那些說明。

---

## 一、四層流程與入庫時機

pipeline 為 crawler → cleaner → loader → updater 四層：crawler 回傳 DataFrame、
cleaner 落地成 `downloads/<source>/{market}_{YYYYMMDD}.csv`、loader 把 CSV 寫進資料庫、
updater 負責串起流程與決定要處理哪些日期。

**入庫時機是這一層最關鍵的設計選擇。** 「整段日期全部爬完才一次 `add_to_db()`」
會讓中斷成本等於全部重來——2026-08-15 的 margin 回補實際發生過：已爬 3,790 個
CSV，程序中斷後資料庫仍是 0 列。

高風險的三個來源（price／chip／margin）因此改為**每 100 天入庫一次**
（`LOAD_BATCH_SIZE`），中斷最多只損失最後一批。

---

## 二、各 updater 現況對照（2026-08-16 建表，2026-09-02 補上期貨線）

新增 updater 時對照本表，確認四個欄位都有著落。

| Updater | 入庫時機 | Resume 依據 | 重載防護 | 失敗可見度 |
|---------|----------|-------------|----------|-----------|
| `StockPriceUpdater` | **每 100 天** | **差集**（見下方說明） | `INSERT OR IGNORE` | `DataLoadError` |
| `StockChipUpdater` | **每 100 天** | **差集**（日曆取自 `price` 表） | `INSERT OR IGNORE` | `DataLoadError` |
| `StockMarginUpdater` | **每 100 天** | **差集**（日曆取自 `price` 表） | `INSERT OR IGNORE` | `DataLoadError` |
| `StockDividendUpdater` | 全部跑完 | **每次都掃整個區間**（一年一次請求，13 年僅 26 次） | `INSERT OR REPLACE` | `DataLoadError` |
| `MonthlyRevenueReportUpdater` | 全部跑完 | DB 最大年月 +1 | 先查既有鍵再過濾 | `DataLoadError` |
| `FinancialStatementUpdater`（前三張報表） | 每種報表一次 | 各表最大年季 +1 | `INSERT OR IGNORE` | `DataLoadError` |
| `FinancialStatementUpdater`（equity_change） | **每 100 檔** | 逐年季查已入庫的 `stock_id` | `INSERT OR IGNORE` | `DataLoadError` |
| `FinMindUpdater`（broker_trading） | 逐組合、每 50 組 commit | metadata ＋ DB | 先查既有鍵再過濾 | `DataLoadError` |
| `StockTickUpdater` | 全部跑完 | 固定起日 ＋ `tick_metadata.json` | **無**（`keepDuplicates=ALL`） | `DataLoadError` |
| `FuturesPriceUpdater` | **每 100 天** | 逐**商品**查該商品在表內的最新 `date` +1 | `INSERT OR IGNORE` | `DataLoadError` |
| `FuturesStockUniverseUpdater` | 一次（單次請求） | 當日快照是否已入庫 | `INSERT OR IGNORE` | `DataLoadError` |
| `FuturesPriceUpdater.update_stock_futures()`（股期） | **每 100 天** | 逐商品最新 `date` +1；商品清單取自標的池前 N 檔 | `INSERT OR IGNORE` | `DataLoadError` |
| `FuturesMarginUpdater` | 一次（單次請求） | 主鍵 `(effective_date, product)` 相同即略過 | `INSERT OR IGNORE` | `DataLoadError` |
| `FuturesContinuousUpdater` | 整段重建（衍生表，不連網路） | 無 resume（逆向調整量會隨後續換月改變，一律重建） | 整表重建 | `DataLoadError`（有行情卻排不出換月表時） |
| `FuturesChipUpdater` | 每個資料集跑完 | 三張表各自最新 `date` +1 | `INSERT OR IGNORE` | `DataLoadError`（該有資料卻沒拿到時） |
| `FuturesTickUpdater` | 全部跑完 | 以日線行情表決定契約、預設只爬近月 | **無**（DolphinDB `keepDuplicates=ALL`，寫入路徑尚未實測） | `DataLoadError` |

**未分批的四個並非疏漏**：dividend／mrr／fs 的量級是十餘年 × 數十個年月或年季，
單次執行以分鐘計，中斷重跑的成本可接受。tick 走 DolphinDB，語意與 SQLite 組不同。

### Resume 為什麼是「差集」而不是 `MAX(date) + 1`

2026-09-03 起（健檢 F-050），台股三支日更 updater 的候選日期改為：

    候選 ＝ 日曆 − 表內已有的日期 − 已確認沒有資料的日期 ＋ 上次沒跑完的日期

`MAX(date) + 1` 的問題是**中間缺的日子永遠不會再被嘗試**：某天因為連線失敗
沒抓到，隔天照樣從新的 `MAX(date)+1` 起跑，那個洞就留在資料庫裡；
而回測遇到缺日會當成休市靜默跳過（F-028）。

最後一項尤其關鍵：price／chip／margin 每天都打**上市與上櫃兩次**請求。
上市成功、上櫃失敗時，上市那批已經進了資料表——差集會把這天當成
「已經有了」而排除，**上櫃那半永遠補不回來**。故失敗的日期另外記在
`DateProgressStore` 的 `incomplete` 集合，用它把「表內已有」的排除翻回去。

**只有站方明確回覆「查無資料」才會寫進 `no_data`**（見 `CrawlResult`）；
連線失敗、被擋、版面解析不出來都不會，那些日子下次還會再試。
且**當天（含未來）一律不寫入** `no_data`——`NO_DATA` 同時代表「休市」與
「盤後尚未公布」，盤中跑一次就把今天寫進永久名單的話，收盤後那天的資料
再也不會被抓。

實作見 `core/pipeline/shared/date_planner.py` 的模組說明。

**2026-09-03 的實跑驗證**（`--target price --from 2026-06-18`，56 個平日）：

```
本次待更新日期：56 天（2026-06-18 ~ 2026-09-03）
[price] 本批統計：56 requested / 54 ok / 0 no data / 2 unreachable
        ；unreachable 的日期下次執行會自動重試        ← WARNING 等級
[price] 入庫完成：新寫入 108 檔、已存在跳過 0 檔、失敗 0 檔
```

- 事前刻意刪掉的 2026-06-18（2,377 列）**原數回補**，證實缺口偵測有效。
- 2026-06-19 與 2026-07-10 兩天 TWSE 回了解析不出表格的內容。
  **舊版會記成「is a Holiday!」並永遠跳過**；新版判為 `FAILED`、寫進
  `DateProgressStore.incomplete`，下次執行會重試（`no_data` 維持空集合）。
- 新入庫的資料 **0 價列數為 0、NULL 價列數 1,722**，證實 cleaner 的
  「無成交價保持 NULL」在真實資料上生效。

**`equity_change` 是 fs 裡的例外**：MOPS 的權益變動表端點（`ajax_t164sb06`）是
**逐檔查詢**，一個年季就要打兩千多次請求，整段回補以十萬次計——量級跟 price／chip／margin
同一等級，所以入庫時機與 resume 依據都得比照它們，而不是比照同一支 updater 裡的另外三張報表。
Resume 尤其不能沿用「表最大年季 +1」：一個年季爬到一半中斷時，該年季已經有資料，
會被判定為已完成而整季跳過，沒爬到的公司永遠補不回來。

**期貨的 updater 寫的是 `tw_futures.db` 不是 `tw_stock.db`**（主鍵語意不同，見
`futures_price_loader` 的說明）。`FuturesPriceUpdater` 的 resume **以商品為單位而非
全表最新日**：各商品上市日不同、且會陸續加進爬取範圍，用全表最新日會讓新加的商品
被既有商品的進度擋住而整段歷史都補不到。`FuturesStockUniverseUpdater` 則沒有回補
區間——來源是一張當下的完整清單，一次請求就結束，故「resume」退化成「今天抓過沒有」。

**`StockTickUpdater` 是目前唯一沒有重載防護的**：DolphinDB 建表時
`keepDuplicates=ALL` 是 tick 語意的刻意選擇（同一時間戳可以有多筆成交），
代價是同一批 CSV 重複 load 會產生重複 tick，需由入庫流程自行把關。

---

## 三、三個必須守住的性質

### 3.1 冪等：重跑不得產生重複列，也不得被誤判為失敗

loader **每次都掃整個 `downloads/` 目錄**，已入庫的檔案必然會再被送一次。
三種結果要分清楚，否則「重跑」會被當成「出錯」：

| 結果 | 判定 | 處置 |
|------|------|------|
| 整檔 0 列寫入、全部跳過 | 重跑，正常 | 計入「已存在跳過」，不出聲 |
| 部分寫入、部分跳過 | 同鍵不同值，資料可能有衝突 | `logger.warning` 列出檔名 |
| 拋出例外 | 欄位不符、檔案損毀 | 計入失敗，最終讓行程非零結束 |

分批入庫讓「重載已入庫檔案」從偶發變成**每批都會發生**，所以分批與冪等必須成對——
只做分批不做冪等，每批都會撞鍵。

### 3.2 失敗必須浮出來

單檔失敗**不中止整批**（其餘檔案仍該入庫），但整批跑完後若有任何失敗，
`finish_load()` 會拋出 `DataLoadError`，最終讓 `tasks/update_db.py` 以**結束碼 1** 結束
且不印 `✅`。

同時，單一 target 失敗**不中斷其餘 target**（`target_guard()`）——一次
`--target no_tick` 會跑十來個 updater、耗時數小時，若其中一個失敗就中止整批，
等於拿可用性換可見度。

### 3.3 交易日判定不可用「非週末」近似

台股有**補行交易日**（補班的週六照常開市），2013 起就有 11 天。
以 `date.weekday()` 判斷會整天漏掉這些日子。
正確做法是以 `price` 表實際有資料的日期為準（見 `StockMarginUpdater.get_candidate_dates()`）。

### 3.4 欄位語言跟著資料來源走

**定案（2026-09-01）：資料表的欄位語言由來源決定，不由市場決定。**

| 來源 | 欄位語言 | 現有例子 |
|------|----------|----------|
| 交易所網頁／檔案（TWSE、TPEX、TAIFEX、MOPS） | **保留來源的中文欄名** | `price` 的 `開盤價`、`chip` 的 `外資買進股數`、`futures_price_daily` 的 `結算價` |
| API（FinMind、未來的美股 provider） | **用來源的英文欄名** | `taiwan_stock_info` 的 `stock_id`／`stock_name`、規劃中的 `us_price_daily` 的 `ticker`／`trade_date` |

兩者皆**以英文命名主鍵欄**（`date`、`stock_id`、`product`、`session`），這是既有慣例。

**為什麼不統一成英文**：15 張表裡 10 張是中文欄（`balance_sheet` 一張就 75 欄），
程式側有 277 處中文欄位字面值橫跨 33 個檔。改成英文要同時動 schema、2.3 GB 資料與
所有下游，而 [PostgreSQL 遷移](../../backlog/PostgreSQL遷移計畫.md) 本來就會重寫這一層——
真要收斂就在那個批次做，不值得為它單獨開一次遷移。

**為什麼不讓美股用中文**：`開盤價` 這種欄名對 AAPL 沒有來源依據（美股 provider 回的
本來就是 `open`／`close`），硬翻是憑空造一套對照表；而且專案裡已經有五張全英文的表，
美股用英文不是新增第三套規則，是延用既有的那一套。

---

## 四、五次事故與其教訓

這一節記錄**實際發生過**的問題。它們的價值不在歷史，而在於後續實作者若不知道會重蹈覆轍。

### 4.1 回補中斷 → 資料歸零

margin 回補已爬 3,790 個 CSV 後中斷，DB 仍為 0 列——因為入庫在最後一步。
**教訓**：長時間回補必須分批入庫。已於 `LOAD_BATCH_SIZE` 處理。

### 4.2 入庫失敗被降級成 warning，行程仍回報成功

6,632 個 CSV 中有 2 個入庫失敗，只留下 warning，行程照樣印
`✅ Database Update Completed` 且結束碼 0。缺的 **1,553 列**是事後逐日比對列數才發現的。
**教訓**：`except` 之後不吭聲，比不 catch 更危險。已由 `DataLoadError` ＋ 結束碼處理。

延伸問題：`to_sql(append)` 是整批送出，**一列撞鍵就整檔失敗**。上述 2 個檔案中，
`tpex_20170907.csv` 的 625 列裡只有 1 列撞鍵，卻導致 625 列全部沒進資料庫。
改用 `INSERT OR IGNORE` 之後，撞鍵那列跳過、其餘 624 列照常入庫。

### 4.3 「修好可見度」反而讓日常更新每天失敗

把入庫失敗改成硬失敗之後，日常更新**每次都會以結束碼 1 結束**——loader 每次掃
全目錄，已入庫的 6,632 個檔案全部撞鍵，被當成 6,632 次失敗。
**教訓**：提高失敗可見度之前，得先讓「正常的重複」不算失敗。兩者必須同時做。

### 4.4 沒有市場欄位的主鍵擋不住跨市場代號衝突

`price` 表把上市與上櫃合併存放卻沒有市場欄位。2017-01-17 之前上櫃 ETF 使用 4 碼代號，
與上市股票的代號空間相撞：`6201` 同時是 亞弘電（上市）與 元大富櫃50（上櫃 ETF），
共 992 天；`6202` 89 天。因為 `price` 的主鍵含證券名稱，兩者能並存而不撞鍵、
也沒有任何錯誤訊息。

`margin` 的主鍵是 `(date, stock_id)`，同一情況會直接撞鍵——這正是 4.2 那 2 個檔案失敗的原因。

**教訓**：主鍵若無法唯一識別商品，衝突不是「會不會發生」而是「什麼時候發現」。
資料已修正（`scripts/fix_price_etf_stock_id.py`），並在
`StockQuoteAdapter.warn_duplicate_symbols()` 加了防護，讓同一 bar 內的重複代號不再靜默。

### 4.5 「連續 N 筆都沒資料」不能當成「整批都沒資料」

`equity_change` 是逐檔查詢，一個年季要打兩千多次請求，因此加了一道早退：
連續 30 檔查無資料就判定該年季尚未申報、跳過整季。

2026-08-22 的 2020Q1 回補實際踩到：跑到代號 6874 附近時撞上一段「2020 年後才上市」
的連續新股，被判定成整季未申報而中止，**代號 6874~9962 共 323 檔從未被嘗試**
（抽驗 9933 中鼎、9945 潤泰新等 5 檔，全部確實有資料）。行程以結束碼 0 正常結束，
log 也沒有任何錯誤——只有一行 `first 30 stocks have no data` 語氣像正常訊息。

根因是**拿順序當統計樣本**：股票代號是排序過的，某個號段連續都是新股完全正常，
它不是「整季未申報」的證據。這個 bug 連 resume 都會壞——重跑時 pending 清單開頭
就是一串無資料的公司，會在同一個地方再次誤判中止。

**教訓**：要判斷「整批是否為空」，就去找**能代表整批的樣本**，不要用「連續遇到幾筆」
這種與順序耦合的近似。現行做法改為試探三檔 2013 年前就上市的權值股
（`EQUITY_CHANGE_PROBE_STOCK_IDS`），全部查無資料才判定未申報；
暫時性失敗一律視為已申報繼續跑，寧可多打請求也不略過已申報的年季。

延伸教訓：**每批結束要留一行統計**。這次是事後撈 log 才發現少了 323 檔；
補上 `N requested, N no data, N unreachable` 之後，同樣的異常在當下就看得出來。

---

## 五、健檢 C 級結論（2026-09-02）

[全專案架構與邏輯健檢.md](../dev/health-check-2026-09.md) S7~S10 逐檔核對四層後，A／B 級已於 2026-09-03 全數完成（規劃文件已依 `manage-backlog` skill §5 移出 `backlog/`，成果見本文件 §二與 `core/pipeline/shared/` 的模組說明）；下列 C 級是**結構性的取捨**，先記錄、等該區塊真的要動時再處理：

| 編號 | 結論 |
|---|---|
| F-013 | 盲捕 `except Exception` 由 85 增為 96 條，全在 `core/pipeline/`（crawlers 26、updaters 25、loaders 其餘）。收斂順序：先做 §3.2 的失敗語意（讓例外有型別），再逐檔把盲捕換成具名例外 |
| F-033 | `base_crawler`／`base_cleaner` 只定義 `setup()`／`crawl()`（`*args, **kwargs`），14 個 crawler 的 `crawl()` 簽章各不相同；抽象基底沒有約束力，新增 crawler 時無法靠型別發現漏實作 |
| F-034 | 節流常數散在三處且語意各異（`RequestUtils` 的 HTTP 重試、財報／月營收各自的 sleep、權益變動表專用常數）；建議集中成一份 `ThrottlePolicy` 由 crawler 注入 |
| F-035／F-036 | FinMind 與期貨籌碼 crawler 的「被擋」與「真的沒資料」都回 `None`，把「該不該重試」推給 updater；與 A 級 F-030 同根，修 F-030 時一併定義回傳型別 |
| F-039 | 財報 cleaner 的三份欄位對照表（`*_all_columns.json`／`*_column_map.json`／`*_cleaned_columns.json`）缺檔只 warning 後降級清洗；依 [執行期產物](../dev/runtime-artifacts.md) 的判準它們是**設定**，缺檔應直接失敗 |
| F-040 | `fix_broken_char()` 把任何 `�` 一律換成「碁」——只對「碁」字家族正確；應改為以股票代號查 `taiwan_stock_info` 的正確名稱 |
| F-041 | `futures_margin_cleaner` 解析不到生效日時退回「公告日 +1」，與同檔第 1 點「解析不到一律整批放棄」矛盾；擇一 |
| F-042 | `futures_stock_universe_cleaner` import crawler 與引擎的 `FuturesCalendar`，cleaner 應只依賴 `shared/` |
| F-048 | `price`／`chip` 主鍵含 `證券名稱`、`margin`／`dividend` 不含，同一個 `(date, stock_id)` 在四張表的唯一性語意不同（§4.4 的根因）；歸 PostgreSQL 遷移的 schema 批次 |
| F-049 | `futures_margin_loader.insert_rows()` 以「第一欄是 `effective_date`」的位置假設轉字串；改以欄名 |
| F-055 | 券商分點 metadata 只存 `(earliest, latest)`，`get_existing_dates()` 把區間內每一天都當已有；與 [券商分點 NO_DATA 的 metadata 語意](broker-trading-no-data.md) 同一題，該文件已選型 |

## 相關文件

- [指令教學](../commands/command-usage.md)——`update_db` 的完整 target 對照與範例
- [權益變動表](equity-change.md)——`equity_change` 的資料形狀、涵蓋範圍、已知限制與爬取節流
- [券商分點 NO_DATA 的 metadata 語意](broker-trading-no-data.md)——選型紀錄，尚未實作
- [程式碼品質工具鏈與基線](../dev/code-quality.md)——§二〈例外處理現況〉記錄了全專案 85 條盲捕，4.2 是其中的第一個收斂案例
- [資料覆蓋範圍](../exchanges/data_coverage.md)——各資料來源的時間涵蓋與已知限制
