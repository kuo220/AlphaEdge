# clean_pycache.ps1
# 📂 自動找出 AlphaEdge 根目錄（也就是此腳本的上兩層）
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Definition
$alphaEdgeRoot = Resolve-Path "$scriptPath\..\.."

Write-Host "📁 從 AlphaEdge 根目錄：$alphaEdgeRoot 開始清理..."

# 🧹 搜尋並刪除 __pycache__ 資料夾
$pycacheDirs = Get-ChildItem -Path $alphaEdgeRoot -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue
if ($pycacheDirs.Count -eq 0) {
    Write-Host "✅ 沒有找到任何 __pycache__ 資料夾。"
} else {
    Write-Host "🧹 正在刪除 __pycache__ 資料夾..."
    $pycacheDirs | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "✅ __pycache__ 資料夾刪除完畢。"
}

# 🧹 搜尋並刪除 .pyc 編譯檔案
$pycFiles = Get-ChildItem -Path $alphaEdgeRoot -Recurse -Filter "*.pyc" -File -ErrorAction SilentlyContinue
if ($pycFiles.Count -eq 0) {
    Write-Host "✅ 沒有找到任何 .pyc 檔案。"
} else {
    Write-Host "🧹 正在刪除 .pyc 檔案..."
    $pycFiles | Remove-Item -Force -ErrorAction SilentlyContinue
    Write-Host "✅ .pyc 檔案刪除完畢。"
}

Write-Host "`n✅ 所有暫存編譯檔案清理完成。"
