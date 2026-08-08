# LONG 成本模型口徑收斂

## Abstract

- **背景／問題**：放空框架 Phase 2 原規格是「多空兩條路徑都走 `StockCostModel`」，實作時只有 SHORT 分支照做，LONG 分支仍呼叫舊的 `StockUtils`，形成同一個 `StockPositionManager` 內兩套費用口徑並存（來源見 [放空回測框架規格](../docs/backtest/short-selling-framework.md) Phase2-1 的「偏離原規格」）。
- **目標**：LONG 與 SHORT 共用 `StockCostModel` 記帳，`StockUtils` 退回純計算工具函式，不再承擔記帳口徑。
- **範圍界線**：**只做口徑收斂**，不新增滑價係數（屬 [回測滑價與執行係數.md](回測滑價與執行係數.md)）、不改成本模型的公式定義、不動 SHORT 路徑既有行為、不擴充多市場費率抽象（屬 [多市場回測引擎架構](../docs/backtest/multi-market-engine.md)）。
- **與多市場抽象的關係**：本文件是在 `StockCostModel` **內部**統一 LONG／SHORT 口徑，[多市場回測引擎架構](../docs/backtest/multi-market-engine.md) Phase2-4 是在其**外部**加上 `BaseCostModel` 介面，兩者互不衝突、可任意先後；但若多市場抽象先做，本文件的檔案路徑須依其 Phase4-1／Phase4-2 更新。
- **驗收標準**：`position_manager.py` 內不再直接呼叫 `StockUtils.calculate_transaction_*` / `calculate_net_profit` / `calculate_roi`，部分平倉的等比例攤提多空共用同一段程式碼，且既有 61 項單元／整合測試與 `test_long_regression_snapshot` 全數通過。

---

## 進度追蹤表

| 編號 | 步驟名稱 | 產出檔案 | 驗證方式 | 狀態 | 備註／中斷點 |
|------|----------|----------|----------|:----:|--------------|
| S1 | 量化新舊兩套公式的差異分布 | `tests/backtest/compare_cost_formula.py` | 掃描含部分平倉的組合，輸出四項差值分布報告 | ⬜ | 必須先於 S2 完成，不可直接改了再看回歸紅不紅 |
| S2 | 決定收斂口徑（做法 A／B 二選一） | 本文件（決策紀錄） | 決策與理由寫入本文件，並註明切換日期 | ⬜ | 相依 S1 的差異報告 |
| S3 | 改造 `position_manager.py` 的 LONG 分支 | `core/managers/stock/position_manager.py` | `test_long_regression_snapshot` ＋ 既有測試 | ⬜ | 相依 S2；路徑依 [多市場回測引擎架構](../docs/backtest/multi-market-engine.md) Phase4-2 扁平化後為準 |
| S4 | 收斂 `StockUtils` 對外入口與 docstring | `core/backtest/models/cost_model.py`、`core/backtest/models/instrument_spec.py` | 人工檢視：無語意重疊的雙入口 | ⬜ | 相依 S3；路徑依 [多市場回測引擎架構](../docs/backtest/multi-market-engine.md) Phase4-1 搬移後為準 |

---

## 背景：目前程式碼的實際樣貌

`core/managers/stock/position_manager.py`：

| 路徑 | 開倉 | 平倉 | 損益／ROI |
|------|------|------|-----------|
| LONG | `StockUtils.calculate_transaction_commission`（82 行） | `StockUtils.calculate_transaction_commission` / `calculate_transaction_tax`（279–286 行） | `StockUtils.calculate_net_profit` / `calculate_roi`（311–320 行） |
| SHORT | `self.cost_model.commission` / `tax` / `borrow_fee` / `margin_required`（157–171 行） | `self.cost_model.commission` / `short_interest`（408–414 行） | `self.cost_model.realized_pnl` / `roi` / `roi_on_capital`（425–443 行） |

### 為什麼當時沒改

兩套公式在**部分平倉**時的開倉手續費口徑不同：

- 舊 `StockUtils` 路徑：以「本次平倉張數」按比例攤提 `position.commission`（289–291 行的 `proportional_buy_commission`），再從 position 上扣掉（325–326 行）。
- 新 `StockCostModel`：以等比例攤提所有開倉成本項。

兩者在整數取整（`int()` 截斷 vs 成本模型的取整規則，見框架文件 §6.0）的邊界上會產生逐元差異，直接切換會讓 `test_long_regression_snapshot` 的 915 筆 baseline 對不上。當時的判斷是**優先保住回歸保護線**，先讓放空落地。

### 現在的風險

1. **兩套公式並存**：同一個 manager 內兩條路徑的費用計算邏輯不同，後續改費率或加滑價時容易只改一邊（[回測滑價與執行係數.md](回測滑價與執行係數.md) 就會踩到）。
2. **多空混合策略的成本口徑不一致**：同一份報表裡 LONG 與 SHORT 的手續費算法不同，多空 PnL 不可嚴格比較。
3. `StockCostModel` 的 LONG 分支目前**沒有生產路徑在用**，等於半個死程式碼，只有測試覆蓋。

---

## S1. 量化新舊兩套公式的差異分布 ⬜

- **目的**：在動生產程式碼之前先知道「差多少、差在哪些邊界」，避免用回歸測試紅燈當作探索工具。
- **做法**：新增比對腳本，對同一組 `(開倉價, 平倉價, 開倉張數, 平倉張數)` 掃過大量組合（**必須涵蓋部分平倉**），分別以 `StockUtils` 與 `StockCostModel` 計算，輸出 `commission` / `tax` / `realized_pnl` / `roi` 四項的差值分布（最大差、差異筆數占比、集中在哪些價格檔位）。
- **產出**：`tests/backtest/compare_cost_formula.py`；差異報告以 CSV 或 markdown 附在本文件。
- **驗證方式**：報告可指出差異是否只集中在取整邊界；若出現非取整因素造成的系統性差異，代表兩套公式的語意本身不同，須回頭釐清後再進 S2。
- **相依**：無。

## S2. 決定收斂口徑 ⬜

- **目的**：在改程式前先定案「以誰為準」，避免實作到一半再翻案。
- **做法**：二選一——
  - **做法 A（推薦）**：以 `StockCostModel` 為準，承認 LONG 結果會有逐元差異，**重新產生 baseline**，於 `tests/backtest/snapshots/` 保留新舊兩份，並在本文件註明切換日期與原因。
  - **做法 B**：讓 `StockCostModel` 的 LONG 分支完全複刻舊公式的取整行為（含 `int()` 截斷），baseline 不變。缺點是把舊的取整瑕疵固化進新模型，與框架文件 §6.0 的取整規則自相矛盾。
- **產出**：本文件補上決策段落（選定做法、理由、切換日期）。
- **驗證方式**：決策內容與 S1 的差異報告相互對應，能解釋為何可接受該差異幅度。
- **相依**：S1。

## S3. 改造 `position_manager.py` 的 LONG 分支 ⬜

- **目的**：讓多空兩條路徑真正共用同一段記帳程式碼。
- **做法**：
  - `open_position()` 的 LONG 分支改呼叫 `self.cost_model.commission(...)`。
  - `close_position()` 的 LONG 分支改呼叫 `cost_model` 的 `commission` / `tax` / `realized_pnl` / `roi`，並以成本模型的等比例攤提取代 `proportional_buy_commission`。
  - 確認 `position.commission` / `transaction_cost` 的遞減邏輯（324–326 行）與新攤提口徑一致。
- **產出**：`core/managers/stock/position_manager.py`。
- **驗證方式**：依做法 A——新 baseline 產生後 `test_long_regression_snapshot` 通過，且 S1 的差異報告附在 commit 說明中；依做法 B——既有 baseline 逐筆相同。兩者皆須通過既有 61 項單元／整合測試。
- **相依**：S2。

## S4. 收斂 `StockUtils` 對外入口與 docstring ⬜

- **目的**：避免留下兩個對外皆可呼叫、語意重疊的記帳入口。
- **做法**：`calculate_net_profit` / `calculate_roi` / `calculate_transaction_commission` / `calculate_transaction_tax` 若收斂後只剩 `StockCostModel` 內部使用，保留為底層純函式即可，但需在 docstring 明確標註「記帳唯一入口為 `StockCostModel`」。
- **產出**：`core/utils/instrument.py`、`core/backtest/models/cost_model.py`。
- **驗證方式**：人工檢視——`core/` 內除 `cost_model.py` 外無其他模組直接呼叫這四個函式。
- **相依**：S3。

---

## 關聯與狀態

- **優先級**：P1（阻擋滑價係數落地；放著會讓兩套公式的差異持續擴大）
- **相關程式**：`core/managers/stock/position_manager.py`、`core/backtest/models/cost_model.py`、`core/utils/instrument.py`、`tests/backtest/test_long_regression.py`、`tests/backtest/snapshots/`
- **相關 backlog**：
  - [放空回測框架規格](../docs/backtest/short-selling-framework.md)（Phase2-1 偏離來源、§6.0 取整規則）
  - [回測滑價與執行係數.md](回測滑價與執行係數.md)（滑價須掛在統一口徑上，建議在本項之後做）
  - [放空回測市場約束補齊.md](放空回測市場約束補齊.md)（融資做多槓桿建議排在本項之後，屆時 baseline 本來就要重產）
