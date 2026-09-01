"""
資料 API：查詢已入庫的資料，不負責爬取與清洗

`base.py` 是市場與商品皆無關的骨架；各市場的實作在子目錄（`tw/`），
目錄只承載「市場」一條軸，商品類別由檔名承載（見 `docs/dev/naming-axes.md`）。

**刻意不做套件層 eager import**：部分 API 相依選用套件（DolphinDB），
在此 re-export 會讓沒裝的環境一 import 就壞掉。
"""
