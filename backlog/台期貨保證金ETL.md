# 台期貨保證金 ETL

## Abstract

- **背景／問題**：`FuturesPositionManager`（2026-09-01 Phase1-4 完成）目前用
  `FuturesMarginConfig` 的「契約價值 × 固定比率（10%）」近似保證金，那是刻意的佔位，
  不是真值。實際的 TAIFEX 原始保證金是**每口固定金額**，且**每日計算、達門檻就調整**——
  TX 在 2015~2026 調整 62 次，相鄰間隔最短 2 天、最長 372 天、中位數 34 天，
  沒有任何固定週期。更關鍵的是 TAIFEX 明載**調整後溯及既往**：
  「所有未沖銷部位亦將以調整後之保證金標準計算」，所以用單一比率跨年回測，
  可開口數與資金效率會系統性偏掉。
- **目標**：把保證金做成**帶生效日的歷史序列**入庫，並讓 `FuturesMarginConfig`
  改為查表；指數類（每口金額）與股票類（適用比例）**分兩張表**。
- **範圍界線**（**不做**）：
  - **不做 2015~2019 的 OCR**（S6 ⏸，理由與解除條件見該步驟）。
  - 不做槓桿控管與追繳／斷頭模擬——那是 [台期貨ETL與回測架構規劃](台期貨ETL與回測架構規劃.md)
    Phase2-2 的另一半，相依本文件。
  - 不做選擇權保證金（SPAN 參數、A／B／C 值）：目前無選擇權回測需求。
  - 不改 `futures_price_daily` 或 `futures_stock_universe` 的既有 schema。
- **驗收標準**：`--target futures_margin` 跑完後兩張表皆有資料且重跑冪等；
  任一交易日查得到當時生效的保證金；2020/03 起的每一次 TX 調整都能在表中找到對應列，
  且**相鄰兩列的「調整前」與前一列的「調整後」逐筆吻合**（鏈式驗證）。

---

## 進度追蹤表

| 編號 | 步驟名稱 | 產出檔案 | 驗證方式 | 狀態 | 備註／中斷點 |
|------|----------|----------|----------|:----:|--------------|
| S1 | 常數與兩張表的 schema 定案 | `core/config.py` | 兩個表名常數與中繼目錄可解析 | ✅ | **2026-09-01 完成**。比例欄定案為**小數**（見該步驟） |
| S2 | 現行保證金快照 ETL（指數類，四層） | `core/pipeline/tw/*/futures_margin_*.py`、`tasks/update_db.py` | 19 條測試 ＋ `--target futures_margin` 端對端驗過 | ✅ | **2026-09-01 完成**：7 個商品入庫、重跑 0 新增 |
| S3 | 現行保證金快照 ETL（股票類，比例） | 同上 | 級距與比例正確、選擇權列被濾掉 | ⬜ | 相依 S2（共用 crawler／updater 骨架） |
| S4 | 歷史回補：2020/03 起的公告 CSV | `core/pipeline/tw/*/futures_margin_*.py` | 鏈式驗證通過（見驗收標準） | ⬜ | 相依 S2；44 筆 TX 公告有 CSV 附件 |
| S5 | `FuturesMarginAPI` ＋ 接進 `FuturesMarginConfig` | `core/api/futures_margin_api.py`、`core/managers/futures/position_manager.py` | 既有 23 條部位測試全綠；查表值取代固定比率 | ⬜ | 相依 S4 |
| S6 | 2015~2019 補完（OCR） | — | OCR 值與下一次公告的「調整前」欄吻合 | ⏸ | **暫緩**：來源為掃描影像，需系統套件 ＋ 有靜默錯誤風險，解除條件見該步驟 |

> **URL 已於 2026-09-01 全數寫入 `core/pipeline/utils/url_manager.py` 並實測打通**
> （`TAIFEX_INDEX_MARGIN_URL`／`TAIFEX_STOCK_MARGIN_URL`／`TAIFEX_HISTORY_NEWS_URL`／
> `TAIFEX_NEWS_DETAIL_URL`），解析上的坑寫在該檔註解裡，動工前先看那一段。

---

## 一、為什麼分兩張表

指數類與股票類的來源格式**語意不同，不是欄位多寡的差別**：

| | 指數類（TX、MTX、TE…） | 股票類（CDF、NAF…） |
|---|---|---|
| 來源 | `TAIFEX_INDEX_MARGIN_URL` | `TAIFEX_STOCK_MARGIN_URL` |
| 給的值 | **每口固定金額**（元） | **適用比例**（%）＋ 級距 |
| 每口保證金 | 直接就是該值 | 標的股價 × 契約單位 × 比例（**要算**） |
| 商品數 | 約 30 | 約 300 |

硬塞進同一張表的話，指數類的比例欄與股票類的金額欄會**永遠是 NULL**，
而下游取值時得先判斷「這是哪一類」才知道該讀哪一組欄位——那個判斷會散落到每個呼叫端。
分兩張表則各自的欄位全部有意義，API 也自然分成兩個方法。

**欄位語言依 [ETL 入庫約定 §3.4](../docs/pipeline/etl-ingestion.md)**：兩張表都是從交易所
網頁爬來的，故**保留來源的中文欄名**（`原始保證金`、`原始保證金適用比例`），
主鍵欄用英文（`effective_date`、`product`）。

---

## S1. 常數與兩張表的 schema 定案 ✅

- **目的**：先把表名、欄位與中繼目錄定下來，S2 之後才不會邊做邊改 schema。
- **做法**：
  1. `core/config.py`：`FUTURES_MARGIN_HISTORY_TABLE_NAME`（**已存在**）沿用；
     新增 `STOCK_FUTURES_MARGIN_RATE_HISTORY_TABLE_NAME: str = "stock_futures_margin_rate_history"`
     與 `FUTURES_MARGIN_DOWNLOADS_PATH`（掛在 `TW_FUTURES_DOWNLOADS_PATH` 之下，
     比照 `FUTURES_UNIVERSE_DOWNLOADS_PATH`）。
  2. **`futures_margin_history`**（指數類等固定金額商品）

     | 欄位 | 型別 | 說明 |
     |------|------|------|
     | `effective_date` | TEXT NOT NULL | 生效日（PK） |
     | `product` | TEXT NOT NULL | 契約代碼（PK；Ex: TX） |
     | `product_name` | TEXT | 來源的中文簡稱，供人工核對 |
     | `結算保證金` | INT | |
     | `維持保證金` | INT | |
     | `原始保證金` | INT | **回測用這一欄**（委託人繳交） |
     | `source` | TEXT NOT NULL | `snapshot`（現行一覽表）／`announcement`（調整公告） |

     PK `(effective_date, product)`。

  3. **`stock_futures_margin_rate_history`**（股票類）

     | 欄位 | 型別 | 說明 |
     |------|------|------|
     | `effective_date` | TEXT NOT NULL | 生效日（PK） |
     | `product_id` | TEXT NOT NULL | 股期代碼（PK；Ex: CDF），對應 `futures_stock_universe.product_id` |
     | `underlying_stock_id` | TEXT | 標的證券代號 |
     | `product_name` | TEXT | 中文簡稱 |
     | `保證金所屬級距` | TEXT | 級距1／級距2／級距3 |
     | `結算保證金適用比例` | REAL | |
     | `維持保證金適用比例` | REAL | |
     | `原始保證金適用比例` | REAL | **回測用這一欄** |
     | `source` | TEXT NOT NULL | 同上 |

     PK `(effective_date, product_id)`。

- **待定案的一件事**：比例欄存**小數**（`0.1350`）還是**百分比數值**（`13.50`）。
  傾向**小數**——下游直接乘不需要再除以 100，而「忘記除 100」是會讓保證金差 100 倍
  卻不會報錯的那種錯。定案後必須寫進 loader 的建表註解。
- **產出**：`core/config.py`。
- **驗證方式**：兩個表名常數與 `FUTURES_MARGIN_DOWNLOADS_PATH` 可正確解析。
- **相依**：無。

> **✅ 完成紀錄（2026-09-01）**
> - 新增 `STOCK_FUTURES_MARGIN_RATE_HISTORY_TABLE_NAME` 與 `FUTURES_MARGIN_DOWNLOADS_PATH`
>   （`core/pipeline/downloads/tw_futures/margin`）；`FUTURES_MARGIN_HISTORY_TABLE_NAME` 沿用。
> - **比例欄定案為小數**（`0.1350`）：下游直接乘不需要再除以 100，
>   而「忘記除 100」會讓保證金差 100 倍卻不會報錯。S3 實作時寫進建表註解。
> - 兩個表名常數上方補了分兩張表的理由，避免日後有人想合併。

---

## S2. 現行保證金快照 ETL（指數類）✅

- **目的**：把「現在這一組」保證金落地，並建立往後累積歷史的機制。
- **做法**：四層比照 `futures_stock_universe`（同樣是「來源只給現況」的快照序列）：
  1. **crawler**：GET `TAIFEX_INDEX_MARGIN_URL`，**回的是 big5 CSV 不是 HTML**，
     用 `FileEncoding.BIG5` 解碼。
  2. **cleaner**：第一行 `更新日期:YYYY/MM/DD` 取出當 `effective_date`，
     資料表頭在第二行。**不要用 `pd.read_html`**，這是 CSV。
  3. **loader**：`INSERT OR IGNORE` 寫入 `futures_margin_history`，`source='snapshot'`。
  4. **updater**：`--target futures_margin`。
- **`effective_date` 的語意要寫清楚**：來源的「更新日期」是**這組保證金開始適用的日子**，
  不是抓取日。同一組保證金連抓 30 天只會產生 1 列（主鍵相同被 IGNORE），
  這正是我們要的——表是**變動序列**不是每日快照。
- **一個免費的正確性檢查**：金額與契約乘數等比例（TX(200) 701,000 →
  MTX(50) 175,250 → TMF(10) 35,050，實測分毫不差）。cleaner 可以用這個關係
  做 sanity check，比例對不上就是解析錯位。
- **產出**：`core/pipeline/tw/{crawlers,cleaners,loaders,updaters}/futures_margin_*.py`、
  `tasks/update_db.py`。
- **驗證方式**：跑完可在 `futures_margin_history` 查到當期資料；同日重跑列數不變。
- **相依**：S1。

> **✅ 完成紀錄（2026-09-01）**
> - 四層 ＋ `--target futures_margin` 已上線。**端對端實跑**：首次入庫 7 個商品
>   （TX／MTX／TMF／TE／ZEF／TF／ZFF，生效日 2026-08-12），
>   **第二次執行新增 0 列**——冪等靠主鍵 ＋ `INSERT OR IGNORE`，不需要另外判斷有沒有變。
> - **crawler 回傳的是解碼後的字串而不是 `Response`**：來源是 big5 CSV，
>   `requests` 猜的編碼不可信，把解碼點收斂在一處，下游不必再操心。
> - **乘數比例檢查只在同一標的指數家族內成立**（實作時先寫錯、實測抓到）：
>   加權每點 3,505、電子 244.50、金融 158.00，**三者本來就不同**。
>   拿 TX 去比 TE 會誤判成解析錯誤，故 `PRODUCT_INDEX_FAMILY` 分家族比對。
>   這是本層唯一能自動偵測「數字都對但欄位錯位」的手段。
> - **只收乘數已登錄的商品**，本次濾掉 22 項並列在 log 供人工複查：選擇權的風險保證金
>   A／B／C 值（語意不是每口金額）、`客製化小型臺指期貨`（MXFFX 乘數未登錄）、
>   以及櫃買／半導體30／美國道瓊等尚未登錄乘數的商品。
>   要收錄它們**必須先在 `FUTURES_MULTIPLIER` 登錄乘數**，那是 Phase4-1 的範圍。
> - **生效日解析不到就整批放棄，不退回今天**——退回今天會產生一列日期錯誤
>   但看起來完全正常的資料。測試有釘。
> - **驗證**：`tests/test_futures_margin.py` 19 條（生效日、欄位錯位、變動序列語意、
>   `effective_date <= 該日` 的查詢語意先行釘住供 S5 用）＋ 端對端實跑。

---

## S3. 現行保證金快照 ETL（股票類）⬜

- **目的**：股期的比例與級距落地。
- **做法**：沿用 S2 的 crawler／updater 骨架，cleaner 與 loader 另寫。
  **三個實測撞到的坑**（`url_manager.py` 註解亦有記錄）：
  1. 檔案標題是「股票期貨**及選擇權**契約保證金一覽表」，**選擇權列混在同一檔**
     （代碼結尾為 `O`，如 `CAO`）。實測 322 個代碼中有 26 個對不回
     `futures_stock_universe`，全部是選擇權，必須濾掉。
  2. **尾段的 ETF 選擇權改用 A值／B值的固定金額**，與前段的比例欄位語意完全不同，
     用同一組欄位規則硬解會錯位。
  3. **公司名稱含逗號**（`"...Co., Ltd."`），必須用 `csv` 模組解析，
     **不可 `split(",")`**——實測用 split 會把 `Ltd.` 讀成級距值。
- **產出**：同 S2。
- **驗證方式**：入庫代碼能對回 `futures_stock_universe.product_id`（實測 296/322）；
  級距只有三種值；比例欄無 NULL。
- **相依**：S2。

---

## S4. 歷史回補：2020/03 起的公告 CSV ⬜

- **目的**：把 2020/03 之後的每一次調整補進表，讓任一交易日都查得到當時生效的保證金。
- **做法**：
  1. POST `TAIFEX_HISTORY_NEWS_URL` 取公告清單（`isQuery` **必須是 `"1"`**、
     `newsType` 值是中文字 `公告`、關鍵字 `保證金金額`），回應可直接 `pd.read_html`
     解成「日期, 標題」兩欄。
  2. 逐筆開 `TAIFEX_NEWS_DETAIL_URL` 取附件連結，抓其中的 **CSV**（檔名每則不同，
     `保證金調整情形列表.csv`／`0312保證金調整.csv`／`保證金調整20260310.csv`…，
     **組不出通則，一定要從頁面上抓**）。
  3. CSV 欄位：`契約中文簡稱, 契約代碼, 契約ABC值, 調整後原始/維持/結算保證金,
     調整前原始/維持/結算保證金`。**「調整前」欄是鏈式驗證的關鍵，不要丟掉**。
  4. **生效日不是公告日**：TAIFEX 規則為「自公告日之**次一**一般交易時段結束後起實施」，
     且標題本身帶明確生效日（民國年，Ex:「並自115年4月1日…起實施」）。
     以標題解出的日期為準，解不出才退回公告日 +1。
- **鏈式驗證（本步驟的核心驗收）**：把同一商品的所有調整依生效日排序後，
  **第 N 筆的「調整前」必須等於第 N−1 筆的「調整後」**。對不上就是漏抓了中間某次調整
  （例如春節的調高／回調成對出現，漏掉一筆會讓後面整段錯位）。
- **已知邊界**（2026-09-01 逐筆盤點 TX 的 62 筆公告）：
  - 2020/03 起 **44 筆有 CSV**
  - 2015~2019 的 **16 筆只有掃描 PDF**（S6）
  - 2020/01/17、2020/01/30 **2 筆無附件**，需人工看內文或視為缺口
- **產出**：同 S2 ＋ 回補用的執行方式（比照權益變動表，直接呼叫 updater 指定區間）。
- **驗證方式**：鏈式驗證全數通過；2020/03/12 那筆的「調整前」即為 2019 年底的實際值，
  可當成 pre-2020 的唯一錨點記錄下來。
- **相依**：S2。

---

## S5. `FuturesMarginAPI` ＋ 接進 `FuturesMarginConfig` ⬜

- **目的**：讓 `FuturesPositionManager` 改用真值，取代固定比率。
- **做法**：
  1. `core/api/futures_margin_api.py`：`get_initial_margin(product, date)`
     取「該日**生效中**的那一列」——即 `effective_date <= date` 的最大者，
     不是等於該日（保證金不是每天都變）。股期另有
     `get_initial_margin_rate(product_id, date)`。
  2. `FuturesMarginConfig` 改為可接受 API：查得到就用查表值，
     **查不到時的行為必須明確**——傾向 `raise` 而非退回比率，
     理由同 `FUTURES_MULTIPLIER` 的 `[]`：靜默用一個近似值比中斷難查得多。
     2015~2019 沒有資料，回測那段期間會當場中止並指向 S6，這是**刻意的**。
  3. 股期的每口保證金 = 標的股價 × `futures_stock_universe.contract_size` × 比例。
- **產出**：`core/api/futures_margin_api.py`、`core/managers/futures/position_manager.py`。
- **驗證方式**：既有 `tests/test_futures_position_manager.py` 23 條全綠
  （固定比率的測試改為注入假 API）；抽樣比對 TAIFEX 原站。
- **相依**：S4。

---

## S6. 2015~2019 補完（OCR）⏸

- **暫緩原因**：該區間的公告附件**全部是掃描影像**——2026-09-01 逐年抽驗
  （2015/02/12、2016/02/02、2017/01/23、2018/02/09、2019/01/29），
  五份都是 `XObject=/Image`、`DCTDecode`／`CCITTFaxDecode`、**無 `/Font`、可抽文字 0 字**。
  取值只能靠 OCR，代價是：
  1. 需要 **tesseract 系統套件 ＋ 中文訓練資料**（不是 `pip install` 就能解決）；
  2. **OCR 把 `477000` 讀成 `47700` 不會報錯**，正是本專案一再踩到的靜默錯誤型態
     （見 [ETL 入庫約定 §4](../docs/pipeline/etl-ingestion.md)）。
- **解除條件**：S4 落地後，實際需要 2015~2019 的精確保證金時才啟動
  （例如要做槓桿控管或追繳模擬，且回測區間必須涵蓋那五年）。
- **啟動時的強制防線**：OCR 出來的數值**必須與下一次公告 CSV 的「調整前」欄鏈式吻合**
  才可入庫，對不上一律標為 `unverified` 不進正式表。沒有這道防線就不要做。
- **替代方案**：把回測的保證金起點對齊到 **2020/03**，2015~2019 以
  「已知 16 個變動日期 ＋ 2019 年底錨點」標記為不確定區間。
- **相依**：S4。

---

## 關聯與狀態

- **優先級**：P3（保證金影響資金效率與可開口數，**不影響 PnL 本身**，
  故不擋 [台期貨ETL與回測架構規劃](台期貨ETL與回測架構規劃.md) 的 Phase1-5／1-6 主線）
- **相關程式**：`core/managers/futures/position_manager.py`（`FuturesMarginConfig`）、
  `core/pipeline/utils/url_manager.py`（四個端點與解析坑）、`core/config.py`
- **相關 backlog**：[台期貨ETL與回測架構規劃](台期貨ETL與回測架構規劃.md) Phase2-2
  的另一半（槓桿／部位控管）相依本文件；本文件不含那部分
- **相關文件**：[ETL 入庫約定](../docs/pipeline/etl-ingestion.md)（§3.4 欄位語言、§4 事故樣式）
