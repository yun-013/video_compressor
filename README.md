# video_compressor

画質をなるべく維持しながら動画のファイルサイズを圧縮する汎用ツール（ffmpeg ラッパー）。
GUI とコマンドラインの両方で使えます。ファイル単体でもフォルダ一括でも OK。

## 必要なもの

- Python 3.8+（tkinter 同梱の標準インストール）
- ffmpeg / ffprobe（PATH が通っているか、スクリプトと同じ場所の `bin\` フォルダに配置）
- tkinterdnd2（GUI のドラッグ&ドロップに使用・任意）: `pip install tkinterdnd2`
  ※ 未インストールでも D&D が無効になるだけで GUI は動作します

※ 配布用 exe 版（後述）を使う場合は何もインストール不要です。

## GUI 版

`動画圧縮ツール.bat` をダブルクリック（または `python gui.py`）で起動。

1. **入力**: 「ファイル追加」「フォルダ追加」、またはウィンドウへの**ドラッグ&ドロップ**
2. **圧縮設定**: 品質・コーデック・GPU/CPU・フレームレート・解像度（4K / WQHD / フルHD / 720p / 480p）・音声（コピー / AAC / なし）
3. **出力設定**: 保存方法を3つから選択
   - 同じフォルダに別名で保存（接尾辞 `_compressed`）
   - 指定フォルダに保存
   - **元ファイルを置き換える**（元動画は削除。実行前に確認ダイアログあり）
   - 「同名ファイルがあれば上書きする」チェックで既存出力の上書き/スキップを切り替え
4. 「圧縮開始」。進捗バー・速度・残り時間が表示され、「中止」でいつでも安全に止められます
   （作りかけのファイルは自動削除）

## コマンドライン版

```powershell
# フォルダ内の動画をすべて圧縮（元ファイルは残し、_compressed 付きで保存）
python compress.py "G:\マイドライブ\配信\YouTube\さくっと5分解説\素材\背景動画"

# 出力先フォルダを指定
python compress.py "G:\...\背景動画" -o "G:\...\背景動画_圧縮済み"

# フレームレート・解像度・品質を指定
python compress.py "video.mp4" --fps 30 --height 720 -q 22

# 元ファイルを置き換える（確認プロンプトあり。--yes でスキップ）
python compress.py "video.mp4" --replace-original

# CPU エンコードで最高圧縮率（低速）
python compress.py "video.mp4" --hw none
```

### 品質値の目安 (`-q` / `--quality`)

| 値 | 用途 |
|---|---|
| 18〜20 | 高画質重視。CPU エンコードなら VMAF 95（見分け不可レベル）に到達 |
| 22〜24 | 標準。通常の視聴では気づかないレベル（**既定: 24**） |
| 26〜28 | 容量優先。背景動画など多少の劣化が許容できる用途 |

※ GPU (AMF) エンコードは品質値を上げても VMAF 91 前後で頭打ちになるため、
「ほぼ無劣化」を狙う場合は CPU (`--hw none`) + q20 以下を推奨。

### 主なオプション

| オプション | 説明 |
|---|---|
| `-q, --quality N` | 品質値 CRF/QP（既定: 24、小さいほど高画質） |
| `--fps N` | 出力フレームレート（元より高い値は無視） |
| `--height N` | 出力の縦解像度（例: 720。元より大きい値は無視） |
| `--codec hevc\|h264\|av1` | 出力コーデック（既定: hevc） |
| `--hw auto\|nvenc\|qsv\|amf\|none` | ハードウェアエンコード（既定: auto。`none` で CPU） |
| `--preset NAME` | CPU エンコード時の x264/x265 プリセット（既定: medium） |
| `--audio copy\|aac\|none` | 音声処理（既定: copy = 無劣化。none = 音声削除） |
| `--audio-bitrate N` | `--audio aac` 時のビットレート（既定: 160k） |
| `--yes` | `--replace-original` 時の確認プロンプトをスキップ |
| `-o, --output-dir DIR` | 出力先フォルダ |
| `--suffix STR` | 出力ファイル名の接尾辞（既定: `_compressed`） |
| `--replace-original` | 圧縮後に元ファイルを削除して置き換える |
| `--overwrite` | 既存の出力ファイルを上書き（既定はスキップ） |
| `--dry-run` | 実行せず ffmpeg コマンドのみ表示 |

## GPU と CPU の使い分け

- **GPU（既定・自動検出）**: 実測で約4倍速。NVIDIA (NVENC) / Intel (QSV) / AMD (AMF) に対応。
  大量・長時間の動画はこちら推奨。
- **CPU（`--hw none`）**: libx265 による最高の圧縮効率。同じ画質でさらに1〜2割小さくなるが、数倍遅い。

## 実測値（1080p/30fps・8Mbps の H.264 ゲーム映像、AMD Radeon 780M）

| 設定 | サイズ | VMAF（知覚画質） |
|---|---|---|
| 元ファイル | 100% | — |
| 既定（GPU/HEVC q24） | 20%（80%減） | 89.4 |
| GPU q20 | 24%（76%減） | 90.6 |
| CPU（libx265 q24） | 18%（82%減） | 93.1 |
| CPU（libx265 q20） | 29%（71%減） | 95.0 |
| 720p/24fps 指定（GPU q24） | 11%（89%減） | — |

VMAF の目安: 95以上 = 通常の視聴で見分け不可 / 90〜95 = ほぼ気づかない / 80〜90 = 注視・一時停止して比較すれば分かる。
主に犠牲になるのは暗いシーンの微細なノイズ感・グラデーションで、明るく静かなシーンはほぼ完全に保たれる。

## 配布用 exe の作り方（他の PC で使う場合）

Python も ffmpeg も入っていない PC で使えるよう、exe + ffmpeg 同梱の zip を作成できます。

```powershell
pip install pyinstaller tkinterdnd2
powershell -ExecutionPolicy Bypass -File build_exe.ps1
```

`release\動画圧縮ツール.zip`（約82MB）が完成します。中身:

```
動画圧縮ツール\
├─ 動画圧縮ツール.exe   … 本体（ダブルクリックで起動）
├─ 使い方.txt
└─ bin\
   ├─ ffmpeg.exe        … 同梱 FFmpeg（gyan.dev の release essentials ビルド）
   ├─ ffprobe.exe
   └─ FFMPEG_LICENSE.txt
```

相手の PC では zip を解凍してダブルクリックするだけ。インストール不要です。
ffmpeg / ffprobe は「exe と同じフォルダ → `bin\` サブフォルダ → PATH」の順で探します。

- 初回ビルド時は `bin\` に ffmpeg.exe / ffprobe.exe を配置する必要があります
  （入手先: <https://www.gyan.dev/ffmpeg/builds/> の release essentials）
- 初回起動時に SmartScreen の警告が出た場合は「詳細情報 → 実行」

## ファイル構成

- `gui.py` — GUI 版（tkinter）
- `compress.py` — コア処理 + コマンドライン版
- `動画圧縮ツール.bat` — GUI をコンソールなしで起動するランチャー
- `build_exe.ps1` — 配布用 exe ビルドスクリプト
- `使い方.txt` — 配布 zip に同梱する説明書
