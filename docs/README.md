# API 文檔使用說明

本目錄包含 AlphaEdge 的完整 API 文檔，使用 MkDocs 生成。

## 快速開始

### 1. 安裝 MkDocs 和依賴

```bash
# 使用 pip
pip install mkdocs mkdocs-material mkdocstrings[python]

# 或使用 conda
conda install -c conda-forge mkdocs mkdocs-material
pip install mkdocstrings[python]
```

### 2. 預覽文檔

在專案根目錄執行：

```bash
mkdocs serve
```

然後在瀏覽器中打開 `http://127.0.0.1:8000` 查看文檔。

### 3. 生成靜態文檔

```bash
mkdocs build
```

生成的文檔會在 `site/` 目錄中。

### 4. 部署文檔

#### GitHub Pages

```bash
mkdocs gh-deploy
```

#### 其他平台

將 `site/` 目錄的內容上傳到您的網站伺服器即可。

## 文檔結構

```
docs/
├── index.md                    # 首頁
├── getting-started.md          # 快速開始指南
├── api/                        # API 參考文檔
│   ├── overview.md
│   ├── data/                   # 資料 API
│   │   ├── base.md
│   │   ├── stock_price_api.md
│   │   ├── stock_tick_api.md
│   │   ├── stock_chip_api.md
│   │   ├── monthly_revenue_report_api.md
│   │   └── financial_statement_api.md
│   └── strategy/               # 策略 API
│       └── base_stock_strategy.md
├── examples/                   # 使用範例
│   ├── basic.md
│   ├── strategy.md
│   └── data_query.md
├── best-practices.md           # 最佳實踐
└── faq.md                      # 常見問題
```

## 更新文檔

### 手動更新

1. 編輯對應的 Markdown 檔案
2. 執行 `mkdocs serve` 預覽更改
3. 確認無誤後提交更改

### 自動生成（進階）

可以使用 `scripts/generate_docs.py` 腳本從 Python 原始碼中提取 docstring，但建議手動維護文檔以確保品質。

## 配置說明

文檔配置在 `mkdocs.yml` 檔案中，主要設定包括：

- **主題**: Material（Material for MkDocs）
- **導航**: 在 `nav` 區塊中定義
- **插件**: 
  - `search`: 搜尋功能
  - `mkdocstrings`: 自動從 Python docstring 生成文檔

## 自訂文檔

### 修改主題顏色

編輯 `mkdocs.yml` 中的 `theme.palette` 區塊：

```yaml
theme:
  palette:
    - scheme: default
      primary: indigo  # 修改這裡
      accent: indigo   # 修改這裡
```

### 新增頁面

1. 在 `docs/` 目錄下建立新的 Markdown 檔案
2. 在 `mkdocs.yml` 的 `nav` 區塊中加入新頁面的連結

### 使用 mkdocstrings 自動生成 API 文檔

如果 Python 程式碼中有完整的 docstring，可以使用 mkdocstrings 自動生成文檔：

```markdown
::: trader.api.stock_price_api.StockPriceAPI
    options:
      show_source: true
      show_root_heading: true
```

## 最佳實踐

1. **保持文檔更新**: 當 API 變更時，記得更新對應的文檔
2. **提供範例**: 每個 API 都應該有使用範例
3. **說明參數**: 清楚說明每個參數的類型和用途
4. **錯誤處理**: 說明可能的錯誤情況和處理方式
5. **版本控制**: 如果 API 有版本變更，在文檔中標註

## 相關資源

- [MkDocs 官方文檔](https://www.mkdocs.org/)
- [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)
- [mkdocstrings 文檔](https://mkdocstrings.github.io/)

## 問題回報

如果發現文檔有錯誤或需要改進，請提交 Issue 或 Pull Request。
