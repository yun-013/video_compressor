# 配布用 exe をビルドして release フォルダにまとめるスクリプト
#
# 前提:
#   pip install pyinstaller tkinterdnd2
#   ffmpeg.exe / ffprobe.exe を用意しておく (release\動画圧縮ツール\bin に配置済みなら再利用)
#
# 使い方:
#   powershell -ExecutionPolicy Bypass -File build_exe.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# 1. exe ビルド
python -m PyInstaller --noconfirm --onefile --windowed `
    --name "動画圧縮ツール" --collect-data tkinterdnd2 gui.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller のビルドに失敗しました" }

# 2. release フォルダ構成
$rel = Join-Path $PSScriptRoot "release\動画圧縮ツール"
New-Item -ItemType Directory -Force "$rel\bin" | Out-Null
Copy-Item "dist\動画圧縮ツール.exe" $rel -Force
Copy-Item "使い方.txt" $rel -Force

if (-not (Test-Path "$rel\bin\ffmpeg.exe")) {
    Write-Warning "release\動画圧縮ツール\bin に ffmpeg.exe / ffprobe.exe を配置してください"
    Write-Warning "入手先: https://www.gyan.dev/ffmpeg/builds/ (release essentials)"
}

# 3. zip 化
$zip = Join-Path $PSScriptRoot "release\動画圧縮ツール.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path $rel -DestinationPath $zip
Write-Host "完成: $zip"
