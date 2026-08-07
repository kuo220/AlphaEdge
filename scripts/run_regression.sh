#!/usr/bin/env bash
#
# 一鍵跑完回測引擎的兩條回歸線（見 backlog/回測引擎多市場抽象.md Phase0-1）
#
# 多市場抽象重構共 17 個步驟，每一步都要求「回歸雙線逐筆相同」。人工執行的漏跑
# 風險不可接受——漏跑的後果不是當下報錯，而是數步之後才發現、然後要回頭 bisect。
#
# 用法：./scripts/run_regression.sh
# 回傳：兩條線皆通過為 0；任一條失敗即以非零狀態碼結束，且不再往下跑。

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 優先使用專案的 venv，避免抓到系統 python（其未安裝 pytest）
if [[ -x ".venv/bin/python" ]]; then
    PYTHON=".venv/bin/python"
else
    PYTHON="python3"
fi

echo "=== [1/2] SHORT 回歸線（純記憶體，秒級）==="
"$PYTHON" -m pytest tests/backtest/test_short_regression.py -q

echo ""
echo "=== [2/2] LONG 回歸線（需 core/database/stock.db，約 55 秒）==="
"$PYTHON" -m pytest tests/backtest/test_long_regression.py -q

echo ""
echo "=== 回歸雙線通過 ==="
