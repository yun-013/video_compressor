# 動画圧縮ツール

画質をなるべく保ったまま、動画のファイルサイズを大幅に小さくするツールです。
Windows / macOS / Linux で動作します。ドラッグ&ドロップして「圧縮開始」を押すだけで使えます。

- 1ファイルでもフォルダ一括でも OK（mp4 / mov / mkv / avi など主要形式に対応）
- 出力形式を選べます（MP4 / MKV / MOV / WebM、音声のみの MP3 / M4A / WAV / FLAC も）
- OBS などの**多重音声トラック録画に対応** — 全トラックを保持したまま圧縮（DaVinci Resolve 等でそのまま複数トラックとして読めます）、または特定トラックだけを選択
- 「ファイル情報」でトラック構成（映像・音声・字幕）を確認できます
- GPU を自動検出して高速圧縮（NVIDIA / Intel / AMD / Apple Silicon 対応）
- 進捗バー・残り時間表示つき。途中で安全に中止できます
- 目安: 一般的な動画で **元の 20% 前後のサイズ**（80%減）まで小さくなります

## ダウンロード (Windows)

**[📦 最新版をダウンロード](https://github.com/yun-013/video_compressor/releases/latest)** — `video-compressor-windows.zip` をクリック

1. ダウンロードした zip を解凍して、「動画圧縮ツール」フォルダごと好きな場所に置きます
2. フォルダ内の **`動画圧縮ツール.exe`** をダブルクリックして起動します

Python や FFmpeg のインストールは不要です（すべて同梱されています）。
対応 OS: Windows 10 / 11 (64bit)

> **「WindowsによってPCが保護されました」と表示されたら**
> 個人配布の署名なしアプリのため、初回起動時に警告が出ることがあります。
> 「**詳細情報**」→「**実行**」の順にクリックすると起動できます。

## ダウンロード (macOS)

**[📦 最新版をダウンロード](https://github.com/yun-013/video_compressor/releases/latest)** — `video-compressor-macos.zip` をクリック

1. zip を解凍して出てきた **`動画圧縮ツール.app`** をアプリケーションフォルダなど好きな場所に置きます
2. ダブルクリックで起動します

ffmpeg は同梱されているためインストール不要です。
対応機種: **Apple Silicon (M1 以降) の Mac**。Intel Mac は後述の「ソースから実行」を使ってください。

> **「開発元を検証できないため開けません」と表示されたら**
> 署名なしの個人配布アプリのため、初回はブロックされます。
> アプリを**右クリック →「開く」→「開く」**、それでも開けない場合は
> **システム設定 → プライバシーとセキュリティ →「このまま開く」** で起動できます。
> 起動後に「ffmpeg が見つかりません」等が出る場合は、ターミナルで
> `xattr -cr /Applications/動画圧縮ツール.app` を実行してから再起動してください
> （ダウンロード由来の検疫属性を外すコマンドです。置き場所に合わせてパスは読み替えてください）。

GPU エンコード: VideoToolbox を自動使用します。

## ダウンロード (Linux)

**[📦 最新版をダウンロード](https://github.com/yun-013/video_compressor/releases/latest)** — `video-compressor-linux-x86_64.tar.gz` をクリック

```bash
sudo apt install ffmpeg        # 事前に ffmpeg を入れる (Fedora: sudo dnf install ffmpeg)
tar -xzf video-compressor-linux-x86_64.tar.gz
./video-compressor             # GUI が起動します
```

Ubuntu 24.04 以降相当の環境 (glibc 2.39+) で動作します。古い環境では後述の「ソースから実行」を使ってください。

GPU エンコード: NVENC (NVIDIA) / QSV (Intel) / VAAPI (Intel・AMD) を自動検出します（ffmpeg と GPU ドライバが対応している範囲で使用。VAAPI はユーザーが `render` グループに入っている必要があります）。

## ソースから実行する (macOS / Linux)

Python 3.8+ があれば配布版を使わずソースから実行できます。

```bash
# macOS (Homebrew)
brew install ffmpeg python-tk

# Ubuntu / Debian
sudo apt install ffmpeg python3-tk

# Fedora
sudo dnf install ffmpeg python3-tkinter
```

```bash
git clone https://github.com/yun-013/video_compressor.git
cd video_compressor
python3 gui.py              # GUI 版を起動
python3 compress.py --help  # コマンドライン版
```

ドラッグ&ドロップを使う場合は `pip3 install tkinterdnd2` も実行してください（なくても D&D 以外は動作します）。

## 使い方

1. **動画を追加する** — 動画ファイルやフォルダをウィンドウに**ドラッグ&ドロップ**します
   （「ファイル追加」「フォルダ追加」ボタンでも OK。フォルダを入れると中の動画を一括圧縮）
2. **圧縮設定を選ぶ** — 迷ったらそのままで OK。既定設定（品質24・H.265・GPU）が標準です
   - 動画の一部だけ欲しい場合は「**切り出し**」に開始・終了時間（例: `90` や `1:30`）を入れると、その区間だけを切り出して圧縮します（空欄 = 全体）
   - 中身を確認したいときは「**ファイル情報**」ボタンでトラック構成（映像・音声・字幕など）を表示できます
3. **保存方法を選ぶ** — 出力形式と保存先を選択
   - **出力形式**: 既定は MP4。MKV / MOV / WebM のほか、**MP3 / M4A / WAV / FLAC を選ぶと音声だけを書き出します**（BGM 抽出などに）
   - **同じフォルダに別名で保存**（既定）: 元の動画は残り、`～_compressed.mp4` ができます
   - **指定フォルダに保存**: まとめて別の場所に出力します
   - **元ファイルを置き換える**: 圧縮後に元動画を削除します（⚠ 元に戻せません。確認あり）
4. **「圧縮開始」を押す** — 進捗・速度・残り時間が表示されます。「中止」でいつでも止められます（作りかけのファイルは自動削除されるので安心です)

## 設定の目安

### 品質（いちばん大事な設定）

数値が**小さいほど高画質・大容量**、大きいほど低画質・小容量です。

| 値 | 用途 |
|---|---|
| 18〜20 | 高画質重視。ほぼ見分けがつきません |
| 22〜24 | **標準（既定: 24）**。通常の視聴では劣化に気づかないレベル |
| 26〜28 | 容量優先。背景動画など多少の劣化が許容できる用途 |

### コーデック

| 選択肢 | 用途 |
|---|---|
| H.265 / HEVC（推奨） | 高圧縮。最近の PC・スマホ・テレビなら問題なく再生できます |
| H.264（互換性重視） | 古い機器や一部の編集ソフトで読み込む場合はこちら |
| AV1（高圧縮・低速） | 最高の圧縮率ですが、古い PC では再生が重いことがあります |

### エンコード（GPU / CPU）

- **GPU（既定・自動検出）**: 高速（実測で約4倍速）。大量・長時間の動画はこちら
- **CPU**: 数倍遅いかわりに、同じ画質でさらに1〜2割小さくなります。「とにかく小さく・きれいに」ならこちら

### 圧縮の実測例（1080p/30fps・8Mbps の H.264 ゲーム映像）

| 設定 | サイズ | 知覚画質 (VMAF) |
|---|---|---|
| 元ファイル | 100% | — |
| 既定（GPU / 品質24） | 20%（80%減） | 89.4 |
| CPU / 品質24 | 18%（82%減） | 93.1 |
| CPU / 品質20 | 29%（71%減） | 95.0（見分け不可レベル） |
| 720p/24fps 指定（GPU / 品質24） | 11%（89%減） | — |

## よくある質問

**Q. 圧縮したら元より大きくなった**
すでに強く圧縮されている動画（H.265 や AV1 など）で起こります。品質の数値を上げる（大きくする）か、その動画は元のまま使ってください。ログにも注意書きが表示されます。

**Q. 音声はどうなる?**
既定では無劣化でそのままコピーされます。設定で「AAC に再圧縮」「削除」も選べます。

**Q. 音声だけ取り出したい**
出力形式で MP3 / M4A / WAV / FLAC を選ぶと音声のみ書き出します。音声設定が「そのままコピー」で形式が合う場合（例: AAC → M4A）は無劣化で取り出されます。

**Q. 動画の中身（トラック構成）を知りたい**
「ファイル情報」ボタンで映像・音声・字幕などのトラック一覧を表示します。なお編集ソフトのレイヤーは書き出し時に1本の映像へ合成されるため、動画ファイルには残りません（確認できるのはトラック単位の構造です）。

**Q. OBS で複数音声トラック（マイク・ゲーム音など）に分けて録画したファイルは?**
既定では1本（既定トラック）だけが残ります。「音声トラック」で「**すべて保持**」を選ぶと全トラックを保ったまま圧縮でき、DaVinci Resolve などに読み込むと複数の音声トラックとして展開されます。「音声N のみ」で特定トラックだけ残す（または音声形式と組み合わせてマイクだけ抽出する）こともできます。番号は「ファイル情報」の 音声1, 音声2... に対応します。

**Q. 元の動画が消えることはない?**
「元ファイルを置き換える」を選ばない限り、元の動画には一切手を加えません。

---

## 上級者向け: コマンドライン版

Python 3.8+ がある環境（Windows / macOS / Linux）では、`compress.py` を直接実行できます。
ffmpeg / ffprobe は「スクリプトと同じフォルダ → `bin` サブフォルダ → PATH」の順で探します。

```powershell
# フォルダ内の動画をすべて圧縮（元ファイルは残し、_compressed 付きで保存）
python compress.py "D:\videos"

# 出力先フォルダを指定
python compress.py "D:\videos" -o "D:\videos_compressed"

# フレームレート・解像度・品質を指定
python compress.py "video.mp4" --fps 30 --height 720 -q 22

# 1分30秒〜5分の区間だけを切り出して圧縮（クリップ）
python compress.py "video.mp4" --start 1:30 --end 5:00

# MKV コンテナで出力 / 音声のみ MP3 で書き出し
python compress.py "video.mp4" --format mkv
python compress.py "video.mp4" --format mp3

# OBS の多重音声トラックをすべて保持して圧縮 / トラック2 (マイク等) だけ MP3 で抽出
python compress.py "obs_rec.mkv" --audio-track all
python compress.py "obs_rec.mkv" --format mp3 --audio-track 2

# トラック構成（映像/音声/字幕）を表示
python compress.py "video.mp4" --info

# 元ファイルを置き換える（確認プロンプトあり。--yes でスキップ）
python compress.py "video.mp4" --replace-original

# CPU エンコードで最高圧縮率（低速）
python compress.py "video.mp4" --hw none
```

### 主なオプション

| オプション | 説明 |
|---|---|
| `-q, --quality N` | 品質値 CRF/QP（既定: 24、小さいほど高画質） |
| `--start TIME` | クリップ開始位置（例: `90` / `1:30` / `0:01:30.5`）。指定区間のみ切り出して圧縮 |
| `--end TIME` | クリップ終了位置（省略時は末尾まで） |
| `--fps N` | 出力フレームレート（元より高い値は無視） |
| `--height N` | 出力の縦解像度（例: 720。元より大きい値は無視） |
| `--codec hevc\|h264\|av1` | 出力コーデック（既定: hevc） |
| `--format mp4\|mkv\|mov\|webm\|mp3\|m4a\|wav\|flac` | 出力形式（既定: mp4）。音声形式を選ぶと音声のみ書き出し |
| `--info` | 変換せずトラック構成（映像/音声/字幕）を表示 |
| `--hw auto\|nvenc\|qsv\|amf\|videotoolbox\|vaapi\|none` | ハードウェアエンコード（既定: auto。`none` で CPU） |
| `--preset NAME` | CPU エンコード時の x264/x265 プリセット（既定: medium） |
| `--audio copy\|aac\|none` | 音声処理（既定: copy = 無劣化。none = 音声削除） |
| `--audio-track auto\|all\|N` | 使用する音声トラック（既定: auto）。`all` = 全トラック保持（OBS 多重録音向け）、`N` = N番目のみ |
| `--audio-bitrate N` | `--audio aac` 時のビットレート（既定: 160k） |
| `--yes` | `--replace-original` 時の確認プロンプトをスキップ |
| `-o, --output-dir DIR` | 出力先フォルダ |
| `--suffix STR` | 出力ファイル名の接尾辞（既定: `_compressed`） |
| `--replace-original` | 圧縮後に元ファイルを削除して置き換える |
| `--overwrite` | 既存の出力ファイルを上書き（既定はスキップ） |
| `--dry-run` | 実行せず ffmpeg コマンドのみ表示 |

GUI 版を Python から起動する場合: `python gui.py`（または `動画圧縮ツール.bat`）。
ドラッグ&ドロップには `pip install tkinterdnd2` が必要です（なくても D&D 以外は動作）。

## ファイル構成

- `gui.py` — GUI 版(tkinter)
- `compress.py` — コア処理 + コマンドライン版
- `動画圧縮ツール.bat` — GUI をコンソールなしで起動するランチャー (Windows)
- `build_exe.ps1` — Windows 配布用 exe ビルドスクリプト（ビルド・リリース手順は冒頭のコメント参照）
- `.github/workflows/release-builds.yml` — リリース公開時に macOS / Linux 版を自動ビルドして添付
- `使い方.txt` — Windows 配布フォルダに同梱する説明書

## ライセンス

本ツールのソースコードは [MIT License](LICENSE) です。

配布版 (Windows zip / macOS .app) に同梱している [FFmpeg](https://ffmpeg.org/) は GPL/LGPL のオープンソースソフトウェアです
（ビルド入手元: Windows は [gyan.dev](https://www.gyan.dev/ffmpeg/builds/)、macOS は [ffmpeg.martin-riedl.de](https://ffmpeg.martin-riedl.de/)。
ライセンス全文は同梱の `FFMPEG_LICENSE.txt`（Windows: `bin` フォルダ内、macOS: アプリ内 `Contents/Resources`）、
ソースコードは <https://ffmpeg.org/download.html> で入手できます）。
