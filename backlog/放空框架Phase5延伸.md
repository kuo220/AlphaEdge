# 放空框架 Phase 5 延伸

## Abstract

- **背景／問題**：[放空回測框架建置.md](放空回測框架建置.md) 的 Phase 0~4 已完成，但 P5-1 的六個延伸項目被明確排除在該次範圍外（狀態 ⏸，備註「另開 backlog」）。其中三項卡在資料源缺口，兩項因會破壞 LONG 回歸保護線或範圍過大而暫緩。
- **目標**：補上放空回測缺少的市場約束——券源可得性、停券強制回補、股利補償——讓放空策略的機會數與績效不再被系統性高估。
- **範圍界線**：**不做**融資做多槓桿與同標的雙向持倉（兩者暫緩，理由見 S4、S5）；不重寫既有成本模型；SBL 個股議定費率僅列為低優先，不在本次必做範圍。
- **驗收標準**：融券餘額 ETL 可日更且有對應 API；`Backtester` 開倉前會檢核券源並把拒單計入事件統計；報表可量化「因無券源拒單」的次數。

---

## 進度追蹤表

| 編號 | 步驟名稱 | 產出檔案 | 驗證方式 | 狀態 | 備註／中斷點 |
|------|----------|----------|----------|:----:|--------------|
| S1 | 融券餘額／信用交易 ETL（crawler→cleaner→loader→updater→API） | `core/pipeline/*/stock_margin_*.py`、`core/api/stock_margin_api.py` | `tasks/update_db.py --target stock_margin` 可日更；抽樣比對證交所原始數據 | ⬜ | **第一順位**；同時解掉券源檢核與券資比風控 |
| S2 | 券源檢核接進回測框架 | `core/utils/cost_model.py`、`core/backtest/backtester.py` | 券源不足時拒單並計入 `event_counts`；報表出現「無券源拒單次數」 | ⬜ | 相依 S1 |
| S3 | 除權息行事曆 ETL ＋ 停券日強制回補與股利補償 | `core/pipeline/*/stock_dividend_*.py`、`core/backtest/backtester.py` | 停券日觸發強制回補；除息日扣股利補償 | ⬜ | 第二順位；相依 S1 的 ETL 慣例 |
| S4 | 融資做多槓桿 | `core/managers/stock/position/position_manager.py` | LONG 回歸重產後逐筆可解釋 | ⏸ | 暫緩：會動 LONG 資金計算、破壞回歸保護線，且目前無策略需求 |
| S5 | 同標的雙向持倉（net position 語意） | 多檔 | 待定 | ⏸ | 暫緩：範圍等同再開一個 Phase，目前無策略需求 |
| S6 | SBL 個股議定費率校正 | `core/utils/cost_model.py` | 熱門空方標的的借券費接近實際 | ⏸ | 低優先：需借券成交資料，取得難度高、對多數標的影響有限 |

---

## 可行性總覽（2026-07 實查結果，摘自框架文件）

| 項目 | 現況 | 主要阻礙 | 對應步驟 |
|------|------|----------|----------|
| `SBL` 逐日市值計費 | **已於 P3-5 完成** | 僅剩「個股議定費率差異」，需借券成交資料 | S6（低優先） |
| 券源可得性（融券餘額檢核） | ❌ 缺資料 | `chip` 表只有三大法人買賣超共 19 欄，無融券餘額／券資比；`price` 表亦無 | S1、S2（第一順位） |
| 停券日資料源（除權息／股東會） | ❌ 缺資料 | DB 無除權息行事曆，目前以 `max_holding_days` 近似 | S3（第二順位） |
| 股利補償現金流 | ❌ 缺資料 | 需除息金額與日期，依賴上一項 | S3（附帶） |
| 融資做多槓桿 | ⚠️ 可做但不建議現在做 | 無資料依賴，但會動 LONG 路徑資金計算，破壞回歸保護線；目前無策略需求 | S4（暫緩） |
| 同標的雙向持倉 | ⚠️ 可做但範圍大 | 需完整 net position 語意，牽動 `check_has_position`、FIFO 篩選與報表分組 | S5（暫緩） |

> **推進順序結論**：先做**融券餘額 ETL**。它同時解掉「券源檢核」與「券資比風控」，且是唯一能讓放空策略的機會數不被高估的項目——目前引擎假設任何標的隨時都借得到券，這會系統性高估放空策略的可交易次數與績效。

---

## S1. 融券餘額／信用交易 ETL ⬜

- **目的**：補上放空可行性判斷所需的唯一資料缺口；沒有這份資料，引擎只能假設「任何標的隨時都借得到券」。
- **做法**：
  - **資料需求**（證交所每日信用交易統計）：融券餘額（張）、融券限額、融資餘額（張，券資比的分母）、當日融券賣出／買進／現券償還張數、是否為暫停融資融券標的（處置股、平盤下不得放空註記）。
  - **落地方式**：沿用既有 `crawlers` / `cleaners` / `loaders` / `updaters` 四層慣例，可直接參考 `stock_chip_*` 那一組：

    | 層 | 新增檔案（建議） |
    |----|------------------|
    | crawler | `core/pipeline/crawlers/stock_margin_crawler.py` |
    | cleaner | `core/pipeline/cleaners/stock_margin_cleaner.py` |
    | loader | `core/pipeline/loaders/stock_margin_loader.py` |
    | updater | `core/pipeline/updaters/stock_margin_updater.py` |
    | API | `core/api/stock_margin_api.py` |

  - 另需在 `tasks/update_db.py` 新增 `--target stock_margin`，並在 `core/config.py` 補表名常數。
- **產出**：上表五個檔案 ＋ `tasks/update_db.py`、`core/config.py`。
- **驗證方式**：`--target stock_margin` 可完成一次日更且中斷後可 resume；抽樣 20 筆與證交所原始數據比對一致。
- **相依**：無。

## S2. 券源檢核接進回測框架 ⬜

- **目的**：讓引擎在券源不足時拒單，並讓「機會數高估的幅度」可被量化。
- **做法**：
  - `ShortConstraint`（`core/utils/cost_model.py`）補「可借券張數上限」欄位。
  - `Backtester` 於開倉前檢核：該標的當日融券餘額不足或屬暫停融券標的 → 拒單並計入 `event_counts`（依框架設計原則 §6「不可靜默失敗」，須 log warning）。
  - 報表的事件統計新增「因無券源拒單次數」。
- **產出**：`core/utils/cost_model.py`、`core/backtest/backtester.py`、`core/backtest/report/reporter.py`。
- **驗證方式**：構造一檔融券餘額為 0 的標的，開倉被拒且 `*_event_report.csv` 出現對應計數；既有 LONG 回歸不受影響。
- **相依**：S1。

## S3. 除權息行事曆與停券日 ⬜

- **目的**：一份資料解兩件事——強制回補日與股利補償現金流，兩者目前都被框架簡化掉。
- **做法**：
  - **資料需求**：個股除權息交易日、除息金額、除權比率、股東會停券起訖日。
  - **ETL**：同樣走四層新增 `stock_dividend_*`。
  - **框架側**：在 `execute_daily_position_check` 內加入兩個分支——① 今日是否觸及停券日 → 強制回補（目前以 `max_holding_days` 粗略近似，見框架文件 §7.3）；② 除息日 → 扣股利補償（放空者需補償出借方的現金股利，長天期放空的績效目前被高估）。
- **產出**：`core/pipeline/*/stock_dividend_*.py`、`core/api/stock_dividend_api.py`、`core/backtest/backtester.py`。
- **驗證方式**：構造跨越停券日的留倉放空案例，部位於停券日前被強制回補；跨除息日的案例出現股利補償扣款。
- **相依**：S1（沿用其 ETL 慣例；兩者無資料相依，可平行進行）。

## S4. 融資做多槓桿 ⏸

- **目的**：支援 LONG 路徑的融資槓桿。
- **做法**：於 `StockPositionManager` 的 LONG 分支加入融資成數與利息計提。
- **產出**：`core/managers/stock/position/position_manager.py`、`core/utils/cost_model.py`。
- **驗證方式**：LONG 回歸 baseline 重產後，差異可完全歸因於槓桿設定。
- **相依**：[LONG成本模型口徑收斂.md](LONG成本模型口徑收斂.md)。
- **暫緩原因與解除條件**：無資料依賴、技術上可做，但會動到 **LONG 路徑的資金計算**，直接破壞放空框架賴以保護的 LONG 逐筆回歸線。建議排在 LONG 成本模型口徑收斂之後——屆時 baseline 本來就要重產，一次處理較合算。目前也無策略需求；待出現需要槓桿的 LONG 策略時解除。

## S5. 同標的雙向持倉 ⏸

- **目的**：支援同一標的多空並存的市場中性策略。
- **做法**：現行框架在 `open_short_position` 明確拒絕「已有 LONG 部位的標的再開 SHORT」（`position_manager.py` 150 行起）。要支援雙向需要：
  - 完整的 net position 語意（同標的多空並存時的曝險、保證金、維持率如何合計）
  - `StockAccount.check_has_position` 的方向參數語意重新定義
  - FIFO 平倉篩選在同標的雙向下的配對規則
  - 報表分組（同一 `stock_id` 兩個方向的統計如何呈現）
- **產出**：待範圍確定後另立文件。
- **驗證方式**：待定。
- **相依**：無技術前置。
- **暫緩原因與解除條件**：範圍等同再開一個 Phase，且目前無策略需求；待出現同標的多空並存的策略需求時，另開獨立 backlog 而非在本文件展開。

## S6. SBL 個股議定費率校正 ⏸

- **目的**：讓熱門空方標的的借券費貼近實際。
- **做法**：`accrue_holding_cost()` 已能逐日以當日收盤價計提借券費，缺的只是「每檔股票的實際議定費率」——現行採統一預設值（框架文件 §3.3），但熱門空方標的實際費率可達 16%，遠高於預設。
- **產出**：`core/utils/cost_model.py` ＋ 費率資料源。
- **驗證方式**：抽樣熱門空方標的，計提費用接近實際借券成本。
- **相依**：借券成交資料源。
- **暫緩原因與解除條件**：資料取得難度高、對多數標的影響有限；待找到可用的借券成交資料源後解除。

---

## 關聯與狀態

- **優先級**：P2（S1、S2 融券餘額 ETL 與券源檢核）／ P3（其餘）
- **相關程式**：`core/pipeline/*`、`core/api/*`、`core/utils/cost_model.py`、`core/backtest/backtester.py`、`tasks/update_db.py`
- **相關 backlog**：
  - [放空回測框架建置.md](放空回測框架建置.md)（P5-1 來源、§7.7 已知簡化）
  - [放空策略_外資大賣強勢股當沖.md](放空策略_外資大賣強勢股當沖.md)（券源檢核直接影響該策略的機會數估計）
  - [LONG成本模型口徑收斂.md](LONG成本模型口徑收斂.md)（S4 融資槓桿建議排在其後）
