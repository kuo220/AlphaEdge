#!/usr/bin/env bash
#
# 一鍵跑完回測引擎的兩條回歸線（見 docs/backtest/multi-market-engine.md〈回歸護欄〉）
#
# 多市場抽象重構共 17 個步驟，每一步都要求「回歸雙線逐筆相同」。人工執行的漏跑
# 風險不可接受——漏跑的後果不是當下報錯，而是數步之後才發現、然後要回頭 bisect。
#
# **skip 不算通過**（健檢 F-090）：LONG 線在沒有 `data/db/tw_stock.db` 的機器上會被
# `skipif` 跳過，pytest 回 0，舊版腳本照樣印「回歸雙線通過」——於是「沒有資料庫」
# 與「回歸真的通過」在輸出上長得一模一樣。護欄最不該有的性質就是「不確定有沒有跑」。
#
# 用法：./scripts/run_regression.sh
# 回傳：
#   0  兩條線皆實際執行且通過
#   3  有測試被 skip（護欄未生效，訊息會指出是哪一條與原因）
#   其他  pytest 自身的失敗結束碼（該線失敗即中止，不再往下跑）

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 優先使用專案的 venv，避免抓到系統 python（其未安裝 pytest）
if [[ -x ".venv/bin/python" ]]; then
    PYTHON=".venv/bin/python"
else
    PYTHON="python3"
fi

# 跑一條回歸線；`-rs` 讓 skip 的原因印在 short summary 裡，才有東西可判讀
run_line() {
    local title="$1"
    local target="$2"
    local output
    local code

    echo "=== ${title} ==="

    set +e
    output="$("${PYTHON}" -m pytest "${target}" -q -rs 2>&1)"
    code=$?
    set -e

    echo "${output}"

    if [[ ${code} -ne 0 ]]; then
        echo ""
        echo "!!! ${title} 失敗（pytest 結束碼 ${code}），不再往下跑 !!!"
        exit "${code}"
    fi

    if grep -q "SKIPPED" <<<"${output}"; then
        echo ""
        echo "!!! ${title} 未實際執行：有測試被 skip，本次回歸不算通過 !!!"
        echo "被 skip 的項目與原因："
        grep "SKIPPED" <<<"${output}" | sed 's/^/    /'
        echo ""
        echo "LONG 線需要 data/db/tw_stock.db；沒有資料庫的機器請在有資料庫的機器上跑。"
        exit 3
    fi
}

run_line "[1/2] SHORT 回歸線（純記憶體，秒級）" "tests/backtest/test_short_regression.py"
echo ""
run_line "[2/2] LONG 回歸線（需 data/db/tw_stock.db，約 55 秒）" "tests/backtest/test_long_regression.py"

echo ""
echo "=== 回歸雙線通過（兩條線都實際執行，無 skip）==="
