#!/bin/bash

echo "🔍 搜尋並刪除所有 __pycache__ 資料夾..."
find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null
echo "✅ __pycache__ 資料夾刪除完畢。"

echo
echo "🔍 搜尋並刪除所有 .pyc 檔案..."
find . -type f -name "*.pyc" -delete 2>/dev/null
echo "✅ .pyc 檔案刪除完畢。"

echo
echo "✅ 所有暫存編譯檔案清理完成。"
