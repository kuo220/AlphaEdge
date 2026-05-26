# notebooks — 探索性 Jupyter Notebook

放隨手實驗、視覺化、教學示範用的 `.ipynb`。

## 適合放這裡的東西

- 快速畫圖、看資料、試模型
- 教學筆記（給自己或他人複習用）
- 把 `data_analysis/` 或 `strategies/` 的中間結果視覺化
- 試別人的論文 / 程式範例

## 命名建議

```
notebooks/
└── YYYY_MM_<主題>.ipynb     # 例：2026_05_macro_momentum_eda.ipynb
```

依時間排序，方便回溯「當初是哪天做的實驗」。

## 寫作小技巧

- **第一個 cell** 寫研究問題、結論、TODO，方便日後重看。
- **變數命名要可讀**：notebook 寫太隨意，幾週後自己會看不懂。
- **不要在 notebook 內定義會被其他模組 import 的函式**；若要重用，搬到 `data_analysis/` 或 `strategies/` 的 `.py`。
- 重的計算盡量 **cache 結果到 CSV**，重開 notebook 不用重跑。

## 與 repo 的關係

- Notebook 通常很大、`diff` 不好看，commit 前建議 **Restart & Clear All Outputs** 再儲存。
- 若是長期保留的研究結論，請整理成 `data_analysis/` 的 `.py` 或 `ideas/` 的 markdown。
