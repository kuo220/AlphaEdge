#!/bin/bash

# 🔍 取得此腳本實際所在的目錄（即 dev/scripts）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 🔙 推回到 AlphaEdge 根目錄（上兩層）
ROOT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

echo "📂 現在從 AlphaEdge 根目錄：$ROOT_DIR 開始清理..."

echo
echo "🔍 搜尋並刪除所有 __pycache__ 資料夾..."
find "$ROOT_DIR" -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null
echo "✅ __pycache__ 資料夾刪除完畢。"

echo
echo "🔍 搜尋並刪除所有 .pyc 檔案..."
find "$ROOT_DIR" -type f -name "*.pyc" -delete 2>/dev/null
echo "✅ .pyc 檔案刪除完畢。"

echo
echo "✅ 所有暫存編譯檔案清理完成。"
