# AlphaEdge Frontend

此目錄提供 AlphaEdge 回測結果的 Streamlit 唯讀檢視器。

## 功能

- 側欄選擇 `trader/backtest/results/<StrategyName>/` 策略資料夾
- 顯示回測核心 Metrics（交易數、勝率、總損益、平均 ROI、最後資產）
- 顯示交易明細表（可依股票代號篩選）
- 顯示互動圖（資產曲線、每日損益）
- 顯示 reporter 輸出的 PNG 圖片（若存在）
- 下載 CSV 與圖片檔

## 安裝

在專案根目錄執行：

```bash
pip install -r frontend/requirements.txt
```

## 啟動

在專案根目錄執行：

```bash
streamlit run frontend/app.py
```

## 結果目錄設定

預設會讀取：

`trader/backtest/results`

可透過環境變數覆寫：

```bash
export ALPHAEDGE_BACKTEST_RESULTS=/your/custom/path
streamlit run frontend/app.py
```
