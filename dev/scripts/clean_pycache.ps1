# clean_pycache.ps1
# 用來清除所有 __pycache__ 資料夾與 .pyc 檔案

Write-Host "🔍 正在搜尋 __pycache__ 資料夾..."
$pycacheDirs = Get-ChildItem -Recurse -Directory -Filter "__pycache__"

if ($pycacheDirs.Count -eq 0) {
    Write-Host "✅ 沒有找到任何 __pycache__ 資料夾。"
} else {
    Write-Host "🧹 正在刪除 __pycache__ 資料夾..."
    $pycacheDirs | Remove-Item -Recurse -Force
    Write-Host "✅ __pycache__ 資料夾刪除完畢。"
}

Write-Host "`n🔍 正在搜尋 .pyc 編譯檔..."
$pycFiles = Get-ChildItem -Recurse -Filter "*.pyc"

if ($pycFiles.Count -eq 0) {
    Write-Host "✅ 沒有找到任何 .pyc 檔案。"
} else {
    Write-Host "🧹 正在刪除 .pyc 檔案..."
    $pycFiles | Remove-Item -Force
    Write-Host "✅ .pyc 檔案刪除完畢。"
}

Write-Host "`n✅ 所有暫存編譯檔案清理完成。"
