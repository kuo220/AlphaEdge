# 執行期產物與原始碼的分界

> 本文件定義「程式寫出來的東西該放哪」，以及判斷一個檔案屬於**設定**還是**產物**的準則。
> 實作於 2026-09-02 分八個步驟完成；規劃文件已依
> [`manage-backlog` skill §5](../../.claude/skills/manage-backlog/SKILL.md#5-完成後的處理) 移出 `backlog/`。

---

## 分界只有一條

**`core/` 是被讀的，`data/`／`results/`／`logs/` 是被寫的。**

```
AlphaEdge/
├── core/                  # 函式庫：可被 import，不寫任何東西到自己目錄下
├── run.py  tasks/  frontend/  strategy_lab/  tests/  docs/  backlog/  scripts/
│
├── data/                  # 資料
│   ├── db/                # tw_stock.db、tw_futures.db（市場軸由檔名承載）
│   └── downloads/         # ETL 中繼檔（市場軸由目錄承載）
│       ├── tw_stock/      # price, chip, margin, dividend, financial_statement,
│       │                  # monthly_revenue_report, tick, finmind, meta
│       └── tw_futures/    # price, chip, continuous, universe, margin, tick
│
├── results/               # 回測產出：只放要給人看的東西（CSV ＋ PNG）
│   └── <StrategyName>/
│
└── logs/
    ├── api/               # core/api/ 的查詢日誌
    ├── pipeline/          # 爬取／清洗／入庫
    └── backtest/          # 回測
```

三個根皆可由環境變數覆寫（容器掛載 volume 用）：
`ALPHAEDGE_DATA_DIR`／`ALPHAEDGE_RESULTS_DIR`／`ALPHAEDGE_LOGS_DIR`。

護欄在 [`tests/test_config_paths.py`](../../tests/test_config_paths.py)（20 條）。

## 為什麼要有這條線

2026-09-02 之前，路徑錨點 `BASE_DIR_PATH` 指向 `core/` 自己，38 個路徑常數只能往套件內長。
結果是 **`core/` 這個 `pip install -e .` 安裝的套件裡住了 6.4 GB 程式寫入的檔案**
（database 2.6 GB、logs 2.2 GB、downloads 1.1 GB、results 479 MB）。

代價不是抽象的潔癖，而是攤在四個工具的設定裡——`pyproject.toml` 的 `packages.find`、
ruff 的 `extend-exclude`、coverage 的 `omit` 各維護一份排除清單。

**最能說明問題的是 `.gitignore`**：它沒辦法寫「忽略產物目錄」（產物散在原始碼裡），
只好全 repo 封鎖 `*.csv`／`*.png`／`*.log`／`*.db` 四種副檔名，於是一個正當的 CSV
（回歸 baseline）需要一條負向例外把它撈回來：

```gitignore
!tests/backtest/snapshots/*.csv
```

**那條負向例外能被刪掉，就是這條分界成立的證明。** 分離之後，`.gitignore` 的產物段落
變成三行目錄，四條副檔名封鎖與那條例外全部消失，三份工具排除清單也清空。

### 為什麼是三個根而不是一個

因為**備份策略在三者之間不同**：`data/db/` 弄丟是災難（權益變動表的回補是幾十小時的爬蟲）、
`results/` 幾分鐘可重跑但想留歷史、`logs/` 隨時可刪。收成一個目錄會讓備份規則退化成
「備份 X 但排除 X/logs 與 X/downloads」——又是一條這次正在消滅的排除規則。

### 為什麼日誌分三桶

依**產生者**分，而不是全部平鋪（原本 258 個檔擠在同一層，另有第二棵樹藏在
`backtest/results/logs/`）。三桶而非兩桶的理由由實際數字決定：

| 桶 | 呼叫端 | 實測 | 價值 |
|----|--------|------|------|
| `api/` | `core/api/tw/`（12 支） | **2.2 GB／241 檔** | 每次查詢都寫，純雜訊，可整桶刪 |
| `pipeline/` | `core/pipeline/tw/{updaters,crawlers}`（17 支） | **58 MB／17 檔** | **會回頭讀**（回補的 `N requested / N no data / N unreachable` 統計行） |
| `backtest/` | `core/backtest/`、`core/utils/` | 少 | 單次回測的執行紀錄 |

兩桶不成立，是因為 `pipeline` 蓋不住 `stock_price_api.log` 這些來自 `core/api/` 的日誌，
而它們恰好是檔案數最多的一群。分開之後，「可以整桶刪掉的那一批」才被隔離出來。

---

## 判準：這個檔案是設定還是產物？

搬遷時暴露出 `downloads/tw_stock/meta/` 底下混了兩種性質完全相反的東西。
新增任何會落地的檔案時，先用這張表判斷：

| | 設定 | 產物 |
|---|---|---|
| 誰產生 | **人**維護 | **程式**寫出 |
| 重跑會怎樣 | 不變 | 被覆寫 |
| 缺檔會怎樣 | 行為改變（可能靜默降級） | 重跑就有 |
| 該放哪 | `core/` 內，隨套件發佈 | `data/`／`results/`／`logs/` |
| 進版控嗎 | **要** | **不要** |

實例：

- **設定** — `core/pipeline/tw/cleaners/schema/**/*.json`（13 個欄位對照表）。
  被 cleaner 讀取，**缺檔只會 warning 後靜默降級清洗**。原本混在 `downloads/` 裡，
  產物目錄一納入 `.gitignore` 就會整批掉出版控。
- **產物** — `tick_metadata.json`、`broker_trading_metadata.json`（爬蟲 resume 狀態）。

> **package data 是 `core/` 內唯一正當的非程式碼檔案**：小、唯讀、隨套件發佈、
> 以 `importlib.resources` 或路徑常數讀取。判準是「唯讀 ＋ 隨套件發佈 ＋ 小」，
> 三條都要成立。

---

## `core/config/` 的三個模組

`core/config.py`（392 行）於同一次工作拆成套件，門面維持 `from core.config import X` 不變：

| 模組 | 內容 | 什麼時候會改 |
|------|------|--------------|
| `paths.py` | 原始碼路徑、產物三根與其下所有目錄 | 目錄搬遷時 |
| `schema.py` | 分庫檔名、完整路徑、資料表名稱 | 新增資料表時 |
| `settings.py` | 爬取範圍、預設區間、DolphinDB／Shioaji 憑證 | 調整營運參數時 |

新程式碼建議直接 import 子模組（`from core.config.paths import DATA_DIR_PATH`），語意較明確。

**門面刻意用 star import**：逐一列出會埋一個陷阱——日後在 `paths.py` 新增常數卻忘了
補進 `__init__.py`，`from core.config import NEW_PATH` 會以一個指不到原因的
ImportError 收場。star import 另外完整保留了拆分前的命名空間，行為零改變。

---

## 兩個踩過的坑

1. **搬移路徑常數時不要改常數名。** 改 `base_dir`、不改名稱，改動就收斂在 `config` 一處；
   改名會擴散到 30 個檔案。這條先例來自
   [台期貨平台](../futures/tw-futures-platform.md) Phase0-1，本次沿用。

2. **`Path(__file__).parent` 的層數跟著檔案位置走。**
   `core/config.py` 拆成 `core/config/paths.py` 時，同一行 `.parent` 由指向 `core/`
   變成指向 `core/config/`，`PROJECT_ROOT` 退化成 `core/`，**所有產物路徑全部退回
   `core/data/`——而且不會有任何錯誤**，只會安靜地在錯的地方建目錄。
   現由 `tests/test_config_paths.py` 釘住兩個錨點的絕對位置。

---

## 日誌保留

`LogManager.setup_logger()` 的 `retention` 預設 30 天，但 **loguru 的清理只在該 logger
再次被建立時才觸發**。一支跑完就不再執行的 crawler，它的舊檔會永遠留著——`logs/` 曾累積到
2.2 GB，最舊的檔案比保留期還久了半年。

問題出在「不會被觸發」而不是「保留太久」，故**不要調 retention**，改用與 logger 生命週期
無關的獨立進入點：

```bash
python -m tasks.clean_logs                     # 預覽（不刪）
python -m tasks.clean_logs --apply             # 實際刪除，預設保留 30 天
python -m tasks.clean_logs --apply --bucket api --days 7
```

它**只刪已輪替的檔**（檔名帶時間戳）；當前使用中的 `xxx.log` 一律保留——刪掉正在被 loguru
寫入的檔案，該 handler 會繼續寫進一個已不存在的 inode，日誌就此靜默消失。

### 日誌檔被刪掉之後會自己回來嗎？會，但只有之後的記錄

上面那句「寫進一個已不存在的 inode」是真的會發生，而且 `clean_logs` 的自我約束
**只保護得了它自己那條路徑**——保護不了任何一次手動的 `rm -rf logs`。

2026-09-03 19:12 實際踩過：驗證「pytest 不再產生 `logs/`」時執行了 `rm -rf logs`，
而當時台期貨行情回補已跑了 1 小時 32 分。

- `lsof` 顯示該程序的 fd 仍指向 `logs/pipeline/update_futures_price.log`、
  已寫入 4.3 MB，但那個路徑在檔案系統上已不存在。
- 程序**完全沒有察覺**：照常爬取與入庫（TF 於 19:26 補完 2,844 天），`ERROR` 數 0。
- 若當時不是用背景執行（stdout 另有一份副本），那 9 小時的日誌會完全消失，
  且沒有任何跡象可循。

修法是把防線放進 sink 本身而不是刪除工具：`LogManager.setup_logger()` 的
`logger.add()` 帶 `watch=True`（loguru ≥ 0.7.0），檔案被刪除或被外部程式取代時，
**下一筆記錄會重新建立它**（含缺少的父目錄）。

⚠️ **已經寫進舊 inode 的內容救不回來**，這個參數保證的是「之後不再繼續消失」。
故操作上仍然成立：**長跑的 ETL 進行中不要動 `logs/`**；要驗證這類行為之前，
先 `ps aux | grep -E "backfill|update_db"` 確認沒有東西在跑。

---

## 相關文件

- [命名軸線](naming-axes.md)：`core/` 內部的市場軸與商品軸分層（本次一律未動）
- [台期貨平台](../futures/tw-futures-platform.md) Phase0-1：「改 `base_dir`、不改常數名」的先例
- [PostgreSQL 遷移計畫](../../backlog/PostgreSQL遷移計畫.md)：若日後遷移完成，
  `data/db/` 會整個消失，`data/` 只剩 `downloads/`；本結構承受得住，不需為此預留
