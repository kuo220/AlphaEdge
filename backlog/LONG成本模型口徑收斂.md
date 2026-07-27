# LONG 路徑收斂至 `StockCostModel`（成本口徑統一）

> 來源：[放空回測框架建置.md](放空回測框架建置.md) P2-1 的**已知偏離規格**，該列備註明寫「收斂留待另開 backlog」。

---

## 一、問題

放空框架 Phase 2 原本的規格是：`StockPositionManager` 注入 `cost_model`，**多空兩條路徑都走 `StockCostModel`**。實作時只有 SHORT 分支照做，**LONG 分支維持既有 `StockUtils` 呼叫未改**。

目前程式碼的實際樣貌（`core/managers/stock/position/position_manager.py`）：

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

## 二、目標

讓 LONG 與 SHORT 共用 `StockCostModel`，`StockUtils` 只保留純計算工具函式（檔位、張數換算等），不再承擔記帳口徑。

---

## 三、實作方向

### 1. 先量化差異，再決定要不要改 baseline

在改動前寫一支比對腳本／測試：同一組 `(開倉價, 平倉價, 開倉張數, 平倉張數)` 掃過大量組合（含部分平倉），輸出兩套公式的 `commission` / `tax` / `realized_pnl` / `roi` 差值分布。**先知道差多少、差在哪些邊界，再決定收斂方向**，不要直接改了再看回歸紅不紅。

### 2. 決定口徑（二選一）

- **做法 A（推薦）**：以 `StockCostModel` 為準，承認 LONG 結果會有逐元差異，**重新產生 baseline** 並在 `tests/backtest/snapshots/` 保留新舊兩份，於文件註明切換日期與原因。
- **做法 B**：讓 `StockCostModel` 的 LONG 分支完全複刻舊公式的取整行為（包含 `int()` 截斷），baseline 不變。缺點是把舊的取整瑕疵固化進新模型，與 §6.0 的取整規則自相矛盾。

### 3. 改造 `position_manager.py`

- `open_position()` 的 LONG 分支改呼叫 `self.cost_model.commission(...)`。
- `close_position()` 的 LONG 分支改呼叫 `cost_model` 的 `commission` / `tax` / `realized_pnl` / `roi`，並改用成本模型的等比例攤提取代 `proportional_buy_commission`。
- 確認 `position.commission` / `transaction_cost` 的遞減邏輯（324–326 行）與新攤提口徑一致。

### 4. `StockUtils` 的去留

`calculate_net_profit` / `calculate_roi` / `calculate_transaction_commission` / `calculate_transaction_tax` 若在收斂後只剩 `StockCostModel` 內部使用，保留為底層純函式即可；但**不要留下兩個對外皆可呼叫、語意重疊的入口**，需在 docstring 標明何者為記帳唯一入口。

---

## 四、驗收

1. `position_manager.py` 內不再有 `StockUtils.calculate_transaction_*` / `calculate_net_profit` / `calculate_roi` 的直接呼叫。
2. 部分平倉的等比例攤提，多空兩條路徑走同一段程式碼。
3. 依做法 A：新 baseline 產生後，`test_long_regression_snapshot` 通過，且差異報告（步驟 1 的輸出）附在 commit 說明中；依做法 B：既有 baseline 逐筆相同。
4. 既有 61 項單元／整合測試全數通過。

---

## 五、狀態

- **狀態**：未實作
- **優先級**：P1（阻擋滑價係數落地；放著會讓兩套公式的差異持續擴大）
- **相關程式**：`core/managers/stock/position/position_manager.py`、`core/utils/cost_model.py`、`core/utils/instrument.py`、`tests/backtest/test_long_regression.py`、`tests/backtest/snapshots/`
- **相關 backlog**：
  - [放空回測框架建置.md](放空回測框架建置.md)（P2-1 偏離來源、§6.0 取整規則）
  - [回測滑價與執行係數.md](回測滑價與執行係數.md)（滑價須掛在統一口徑上，建議在本項之後做）
