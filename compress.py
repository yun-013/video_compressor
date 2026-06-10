#!/usr/bin/env python3
"""汎用動画圧縮ツール (ffmpeg ラッパー) — コア処理 + CLI

画質をなるべく維持しながら動画のファイルサイズを削減する。
ファイル単体・フォルダ一括の両方に対応。GUI 版は gui.py を起動。
Windows / macOS / Linux で動作 (GPU エンコードは
nvenc・qsv・amf / videotoolbox / vaapi を自動検出)。

例:
    python compress.py "D:\\videos"                     # フォルダ内を一括圧縮 (GPU/HEVC)
    python compress.py video.mp4 --quality 22           # 品質を上げて圧縮
    python compress.py video.mp4 --fps 30 --height 720  # 30fps / 720p に変換
    python compress.py video.mp4 --start 1:30 --end 5:00  # 1分30秒〜5分を切り出して圧縮
    python compress.py "D:\\videos" --hw none           # CPU (libx265) で最高圧縮率
    python compress.py video.mp4 -o "D:\\out"           # 出力先フォルダ指定
    python compress.py video.mp4 --replace-original     # 元ファイルを置き換える
"""

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".ts", ".flv", ".wmv", ".mpg", ".mpeg"}

# ハードウェアエンコーダーの優先順位 (検出された順に使用)。OS ごとに利用可能な種類が異なる
if sys.platform == "win32":
    HW_PRIORITY = ["nvenc", "qsv", "amf"]
elif sys.platform == "darwin":
    HW_PRIORITY = ["videotoolbox"]
else:  # Linux など
    HW_PRIORITY = ["nvenc", "qsv", "vaapi"]

CODECS = ("hevc", "h264", "av1")

# Windows でコンソールを出さずにサブプロセスを起動するためのフラグ (GUI 用)
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def _find_tool(name):
    """ffmpeg / ffprobe の実体を探す。

    exe 化 (PyInstaller) して配布した場合に同梱版を使えるよう、
    exe (またはスクリプト) と同じフォルダ → bin サブフォルダ → PATH の順で探す。
    """
    exe = f"{name}.exe" if sys.platform == "win32" else name
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
    for cand in (base / exe, base / "bin" / exe):
        if cand.is_file():
            return str(cand)
    return shutil.which(name)


FFMPEG = _find_tool("ffmpeg")
FFPROBE = _find_tool("ffprobe")


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", creationflags=CREATE_NO_WINDOW, **kw)


def detect_hw_encoders():
    """ffmpeg が対応しているハードウェアエンコーダーを検出する。"""
    res = run([FFMPEG, "-hide_banner", "-encoders"])
    available = set()
    for line in res.stdout.splitlines():
        for hw in HW_PRIORITY:
            for codec in CODECS:
                if f"{codec}_{hw}" in line:
                    available.add(hw)
    return available


def hw_input_args(hw):
    """入力 (-i) より前に置く、HWエンコーダー固有のオプション。"""
    if hw == "vaapi":
        # デバイス省略時は /dev/dri/renderD128 などが自動選択される
        return ["-init_hw_device", "vaapi=va", "-filter_hw_device", "va"]
    return []


def hw_filter_args(hw):
    """-vf チェーンの末尾に追加する、HWエンコーダー固有のフィルター。"""
    if hw == "vaapi":
        return ["format=nv12", "hwupload"]
    return []


def hw_encoder_works(codec, hw, quality):
    """実際に1フレームエンコードして、そのHWエンコーダーが動くか確認する。

    本番の圧縮と同じオプションでテストすることで、エンコーダー自体は存在しても
    使用モードに非対応な環境 (例: Intel Mac の VideoToolbox は定品質モード不可) を弾く。
    """
    cmd = [FFMPEG, "-hide_banner", "-v", "error", *hw_input_args(hw),
           "-f", "lavfi", "-i", "color=black:size=320x240:duration=0.1"]
    hw_vf = hw_filter_args(hw)
    if hw_vf:
        cmd += ["-vf", ",".join(hw_vf)]
    cmd += ["-frames:v", "1", *build_video_args(codec, hw, quality, "medium"),
            "-f", "null", "-"]
    return run(cmd).returncode == 0


def pick_hw(codec, hw_request="auto", quality=24):
    """使用するHWエンコーダーを決める。None = CPU。不可なら ValueError。"""
    if hw_request == "none":
        return None
    if hw_request == "auto":
        detected = detect_hw_encoders()
        for cand in HW_PRIORITY:
            if cand in detected and hw_encoder_works(codec, cand, quality):
                return cand
        return None
    if not hw_encoder_works(codec, hw_request, quality):
        raise ValueError(f"{codec}_{hw_request} はこの環境で使用できません。")
    return hw_request


def encoder_label(codec, hw):
    if hw:
        return f"GPU ({codec}_{hw})"
    sw = {"hevc": "libx265", "h264": "libx264", "av1": "libsvtav1"}[codec]
    return f"CPU ({sw})"


def parse_time(text):
    """"90" / "1:30" / "0:01:30.5" のような時間表記を秒 (float) に変換する。"""
    parts = text.strip().split(":")
    if not 1 <= len(parts) <= 3:
        raise ValueError(f"時間の形式が不正です: {text}")
    try:
        sec = 0.0
        for p in parts:
            sec = sec * 60 + float(p or 0)
    except ValueError:
        raise ValueError(f"時間の形式が不正です: {text}") from None
    if sec < 0:
        raise ValueError(f"時間は 0 以上で指定してください: {text}")
    return sec


def probe(path: Path):
    """動画の長さ・解像度・fps・コーデックを取得する。"""
    res = run([
        FFPROBE, "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height,r_frame_rate",
        "-show_entries", "format=duration,size,bit_rate",
        "-of", "json", str(path),
    ])
    if res.returncode != 0:
        return None
    data = json.loads(res.stdout)
    if not data.get("streams"):
        return None
    s = data["streams"][0]
    f = data.get("format", {})
    num, _, den = s.get("r_frame_rate", "0/1").partition("/")
    fps = float(num) / float(den or 1) if float(den or 1) else 0
    return {
        "codec": s.get("codec_name", "?"),
        "width": s.get("width", 0),
        "height": s.get("height", 0),
        "fps": fps,
        "duration": float(f.get("duration", 0) or 0),
        "size": int(f.get("size", 0) or 0),
        "bit_rate": int(f.get("bit_rate", 0) or 0),
    }


def build_video_args(codec, hw, quality, preset):
    """コーデックとエンコーダー種別に応じた ffmpeg の映像オプションを組み立てる。"""
    if hw == "nvenc":
        return ["-c:v", f"{codec}_nvenc", "-preset", "p5", "-tune", "hq",
                "-rc", "vbr", "-cq", str(quality), "-b:v", "0"]
    if hw == "qsv":
        return ["-c:v", f"{codec}_qsv", "-global_quality", str(quality), "-preset", "slower"]
    if hw == "amf":
        # AMF の QVBR は数値が大きいほど高画質 (CRF と逆) なので変換する
        qvbr_level = max(1, min(51, 52 - quality))
        return ["-c:v", f"{codec}_amf", "-quality", "quality", "-rc", "qvbr",
                "-qvbr_quality_level", str(qvbr_level)]
    if hw == "videotoolbox":
        # macOS。-q:v は 1-100 で大きいほど高画質なので CRF 風の値から変換する
        # (定品質モードは Apple Silicon のみ対応。Intel Mac では失敗するため CPU を使うこと)
        qv = max(1, min(100, 100 - quality * 2))
        return ["-c:v", f"{codec}_videotoolbox", "-q:v", str(qv)]
    if hw == "vaapi":
        # Linux (Intel/AMD GPU)。固定QPモード
        return ["-c:v", f"{codec}_vaapi", "-qp", str(quality)]
    # ソフトウェアエンコード
    if codec == "hevc":
        return ["-c:v", "libx265", "-crf", str(quality), "-preset", preset,
                "-x265-params", "log-level=error"]
    if codec == "h264":
        return ["-c:v", "libx264", "-crf", str(quality), "-preset", preset]
    if codec == "av1":
        return ["-c:v", "libsvtav1", "-crf", str(quality), "-preset", "6"]
    raise ValueError(f"unknown codec: {codec}")


def build_command(src: Path, dst: Path, info, opts, hw):
    """1ファイル分の ffmpeg コマンドを組み立てる。"""
    vf = []
    if opts.height and info["height"] > opts.height:
        vf.append(f"scale=-2:{opts.height}")
    if opts.fps and info["fps"] > opts.fps + 0.01:
        vf.append(f"fps={opts.fps}")

    vf += hw_filter_args(hw)

    start = getattr(opts, "clip_start", None)
    end = getattr(opts, "clip_end", None)

    cmd = [FFMPEG, "-hide_banner", "-v", "error", "-y", *hw_input_args(hw)]
    if start:
        cmd += ["-ss", f"{start:g}"]
    cmd += ["-i", str(src)]
    if end is not None:
        cmd += ["-t", f"{end - (start or 0):g}"]
    if vf:
        cmd += ["-vf", ",".join(vf)]
    cmd += build_video_args(opts.codec, hw, opts.quality, opts.preset)
    if hw != "vaapi":  # vaapi は hwupload 後の GPU フレームを渡すため pix_fmt 指定不可
        cmd += ["-pix_fmt", "yuv420p"]
    if opts.codec == "hevc" and dst.suffix.lower() == ".mp4":
        cmd += ["-tag:v", "hvc1"]  # macOS / iOS の標準プレイヤーで再生可能にする
    if opts.audio == "none":
        cmd += ["-an"]
    elif opts.audio == "copy":
        cmd += ["-c:a", "copy"]
    else:
        cmd += ["-c:a", "aac", "-b:a", opts.audio_bitrate]
    if dst.suffix.lower() == ".mp4":
        cmd += ["-movflags", "+faststart"]
    cmd += ["-progress", "pipe:1", "-nostats", str(dst)]
    return cmd


def human_size(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f}{unit}" if unit != "B" else f"{n}B"
        n /= 1024


def fmt_time(sec):
    sec = int(sec)
    h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def compress_file(src: Path, dst: Path, opts, hw,
                  on_progress=None, cancel=None, log=print):
    """1ファイルを圧縮する。

    戻り値: "ok" / "failed" / "skipped" / "cancelled"
    on_progress(pct, speed_x, eta_sec) が定期的に呼ばれる。
    cancel は threading.Event。セットされると中断し出力を削除する。
    """
    info = probe(src)
    if info is None:
        log(f"  スキップ: 動画情報を取得できません: {src.name}")
        return "skipped"

    # クリップ指定がある場合、進捗計算に使う長さを切り出し後の長さにする
    clip_start = getattr(opts, "clip_start", None) or 0
    clip_end = getattr(opts, "clip_end", None)
    if clip_start or clip_end is not None:
        end = min(clip_end, info["duration"]) if clip_end is not None else info["duration"]
        if end - clip_start <= 0:
            log(f"  スキップ: クリップ範囲が動画の長さ ({fmt_time(info['duration'])}) の外です")
            return "skipped"
        info = dict(info, duration=end - clip_start)

    cmd = build_command(src, dst, info, opts, hw)

    if opts.dry_run:
        log("  [dry-run] " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
        return "skipped"

    start = time.time()
    duration = info["duration"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace",
                            creationflags=CREATE_NO_WINDOW)
    last_cb = 0.0
    try:
        for line in proc.stdout:
            if cancel is not None and cancel.is_set():
                proc.kill()
                proc.wait()
                if dst.exists():
                    dst.unlink()
                log("  中断しました (出力ファイルを削除)")
                return "cancelled"
            if line.startswith("out_time_us=") and duration > 0 and on_progress:
                try:
                    t = int(line.split("=", 1)[1]) / 1_000_000
                except ValueError:
                    continue
                now = time.time()
                if now - last_cb >= 0.5:
                    last_cb = now
                    pct = min(t / duration * 100, 100)
                    speed = t / max(now - start, 0.001)
                    eta = (duration - t) / speed if speed > 0 else 0
                    on_progress(pct, speed, eta)
    except KeyboardInterrupt:
        proc.kill()
        proc.wait()
        if dst.exists():
            dst.unlink()
        log("\n  中断しました (出力ファイルを削除)")
        raise
    proc.wait()

    if proc.returncode != 0:
        err = proc.stderr.read().strip()
        log(f"  失敗: {src.name}\n    {err[-500:]}")
        if dst.exists():
            dst.unlink()
        return "failed"

    src_size, dst_size = src.stat().st_size, dst.stat().st_size
    ratio = dst_size / src_size * 100 if src_size else 0
    elapsed = time.time() - start
    log(f"  完了: {human_size(src_size)} -> {human_size(dst_size)} ({ratio:.0f}%)  [{fmt_time(elapsed)}]")
    if dst_size >= src_size:
        log("  ※ 元より大きくなりました。--quality の値を上げる(数値を大きく)か、元のままの使用を検討してください。")
    return "ok"


def replace_original(src: Path, tmp: Path):
    """圧縮成功後、一時ファイルで元ファイルを置き換える。最終パスを返す。"""
    final = src.with_suffix(".mp4")
    src.unlink()
    tmp.rename(final)
    return final


def temp_output_path(src: Path):
    """置き換えモード用の一時出力パス。"""
    return src.with_name(src.stem + ".__compress_tmp__.mp4")


def collect_inputs(paths, log=print):
    files = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            files += sorted(f for f in path.iterdir()
                            if f.is_file() and f.suffix.lower() in VIDEO_EXTS
                            and "__compress_tmp__" not in f.name)
        elif path.is_file():
            files.append(path)
        else:
            log(f"警告: 見つかりません: {p}")
    return files


def check_ffmpeg():
    return bool(FFMPEG and FFPROBE)


# ---------------------------------------------------------------- CLI

def _console_progress(pct, speed, eta):
    bar = "#" * int(pct // 4) + "-" * (25 - int(pct // 4))
    sys.stdout.write(f"\r  [{bar}] {pct:5.1f}%  {speed:4.1f}x  残り {fmt_time(eta)}   ")
    sys.stdout.flush()


def main():
    ap = argparse.ArgumentParser(
        description="画質をなるべく維持して動画ファイルサイズを圧縮するツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="品質の目安 (--quality): 小さいほど高画質・大容量\n"
               "  18-20: ほぼ劣化なし / 22-24: 標準(推奨) / 26-28: 容量優先\n",
    )
    ap.add_argument("inputs", nargs="+", help="動画ファイルまたはフォルダ (複数可)")
    ap.add_argument("-o", "--output-dir", help="出力先フォルダ (省略時: 元と同じ場所に _compressed 付きで保存)")
    ap.add_argument("--suffix", default="_compressed", help="出力ファイル名に付ける接尾辞 (既定: _compressed)")
    ap.add_argument("--replace-original", action="store_true",
                    help="圧縮後に元ファイルを削除して置き換える (注意: 元に戻せません)")
    ap.add_argument("-q", "--quality", type=int, default=24,
                    help="品質値 CRF/QP (既定: 24。小さいほど高画質)")
    ap.add_argument("--codec", choices=list(CODECS), default="hevc",
                    help="出力コーデック (既定: hevc = H.265)")
    ap.add_argument("--start", dest="clip_start", type=parse_time, metavar="TIME",
                    help="クリップ開始位置 (例: 90 / 1:30 / 0:01:30.5)。指定区間のみ切り出して圧縮")
    ap.add_argument("--end", dest="clip_end", type=parse_time, metavar="TIME",
                    help="クリップ終了位置 (例: 300 / 5:00)。省略時は末尾まで")
    ap.add_argument("--fps", type=float, help="出力フレームレート (例: 30)。元より高い値は無視")
    ap.add_argument("--height", type=int, help="出力の縦解像度 (例: 720)。元より大きい値は無視")
    ap.add_argument("--hw", choices=["auto", "nvenc", "qsv", "amf", "videotoolbox", "vaapi", "none"],
                    default="auto",
                    help="ハードウェアエンコード (既定: auto=自動検出, none=CPUで最高圧縮率)")
    ap.add_argument("--preset", default="medium",
                    help="CPUエンコード時のプリセット (既定: medium。slow でさらに圧縮)")
    ap.add_argument("--audio", choices=["copy", "aac", "none"], default="copy",
                    help="音声処理 (既定: copy=無劣化コピー, none=音声を削除)")
    ap.add_argument("--audio-bitrate", default="160k", help="--audio aac 時のビットレート (既定: 160k)")
    ap.add_argument("--overwrite", action="store_true", help="出力先に既存ファイルがあっても上書きする")
    ap.add_argument("--yes", action="store_true", help="--replace-original 時の確認をスキップ")
    ap.add_argument("--dry-run", action="store_true", help="実行せずコマンドのみ表示")
    args = ap.parse_args()

    if not check_ffmpeg():
        sys.exit("エラー: ffmpeg / ffprobe が見つかりません。インストールして PATH を通してください。")

    if args.clip_start is not None and args.clip_end is not None and args.clip_end <= args.clip_start:
        sys.exit("エラー: --end は --start より後の時間を指定してください。")

    try:
        hw = pick_hw(args.codec, args.hw, args.quality)
    except ValueError as e:
        sys.exit(f"エラー: {e}")

    print(f"エンコーダー: {encoder_label(args.codec, hw)} / 品質: {args.quality}"
          + (f" / fps: {args.fps}" if args.fps else "")
          + (f" / 高さ: {args.height}px" if args.height else "")
          + (f" / クリップ: {fmt_time(args.clip_start or 0)}-"
             + (fmt_time(args.clip_end) if args.clip_end is not None else "末尾")
             if args.clip_start or args.clip_end is not None else ""))

    files = collect_inputs(args.inputs)
    if not files:
        sys.exit("対象の動画ファイルが見つかりません。")
    print(f"対象: {len(files)} ファイル")

    if args.replace_original and not args.dry_run and not args.yes:
        ans = input(f"元ファイル {len(files)} 件を圧縮後に削除して置き換えます。元に戻せません。よろしいですか? [y/N]: ")
        if ans.strip().lower() not in ("y", "yes"):
            sys.exit("中止しました。")
    print()

    out_dir = Path(args.output_dir) if args.output_dir else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    total_src = total_dst = done = failed = skipped = 0
    for i, src in enumerate(files, 1):
        if args.replace_original:
            dst = temp_output_path(src)
        elif out_dir:
            dst = out_dir / (src.stem + ".mp4")
        else:
            dst = src.with_name(src.stem + args.suffix + ".mp4")
        if dst.resolve() == src.resolve():
            dst = src.with_name(src.stem + "_compressed.mp4")

        print(f"[{i}/{len(files)}] {src.name}")
        if not args.replace_original and dst.exists() and not args.overwrite:
            print(f"  スキップ: 出力先に既に存在します ({dst.name})。--overwrite で上書き可能")
            skipped += 1
            continue

        src_size = src.stat().st_size

        def progress_done():
            sys.stdout.write("\r" + " " * 70 + "\r")

        result = compress_file(src, dst, args, hw, on_progress=_console_progress,
                               log=lambda m, _p=progress_done: (_p(), print(m)))
        if result == "ok":
            if args.replace_original:
                dst = replace_original(src, dst)
            total_src += src_size
            total_dst += dst.stat().st_size
            done += 1
        elif result == "failed":
            failed += 1
        else:
            skipped += 1

    print("\n===== 結果 =====")
    print(f"成功: {done} / 失敗: {failed} / スキップ: {skipped}")
    if total_src:
        saved = total_src - total_dst
        print(f"合計: {human_size(total_src)} -> {human_size(total_dst)} "
              f"(削減 {human_size(saved)}, {saved / total_src * 100:.0f}%減)")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        main()
    except KeyboardInterrupt:
        sys.exit("\n中断されました。")
