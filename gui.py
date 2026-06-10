#!/usr/bin/env python3
"""動画圧縮ツール GUI 版 (tkinter)

起動: python gui.py  (コンソールを出したくない場合: pythonw gui.py)
"""

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from types import SimpleNamespace

import compress as core

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

CODEC_CHOICES = {
    "H.265 / HEVC (推奨)": "hevc",
    "H.264 (互換性重視)": "h264",
    "AV1 (高圧縮・低速)": "av1",
}
HW_CHOICES = {
    "GPU (自動検出・高速)": "auto",
    "CPU (高圧縮・低速)": "none",
}
AUDIO_CHOICES = {
    "そのままコピー (無劣化)": "copy",
    "AAC 160kbps に再圧縮": "aac",
    "なし (音声を削除)": "none",
}
FPS_CHOICES = ["変更しない", "60", "30", "24"]
HEIGHT_CHOICES = ["変更しない", "2160 (4K)", "1440 (WQHD)", "1080 (フルHD)", "720", "480"]
NO_CHANGE = "変更しない"


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("動画圧縮ツール")
        root.minsize(640, 640)

        self.worker = None
        self.cancel_event = threading.Event()
        self.msg_queue = queue.Queue()

        self._build_ui()
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(100, self._poll_queue)

        if not core.check_ffmpeg():
            messagebox.showerror("エラー", "ffmpeg / ffprobe が見つかりません。\n"
                                 "インストールして PATH を通してから再起動してください。")
            self.start_btn.config(state="disabled")

    # ---------------------------------------------------------- UI 構築
    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}
        main = ttk.Frame(self.root, padding=8)
        main.pack(fill="both", expand=True)

        # --- 入力ファイル ---
        in_title = "入力 (ファイルまたはフォルダ)"
        if HAS_DND:
            in_title += " — ここにドラッグ&ドロップできます"
        in_frame = ttk.LabelFrame(main, text=in_title, padding=6)
        in_frame.pack(fill="x", **pad)

        list_row = ttk.Frame(in_frame)
        list_row.pack(fill="x")
        self.input_list = tk.Listbox(list_row, height=5, selectmode="extended")
        self.input_list.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(list_row, orient="vertical", command=self.input_list.yview)
        sb.pack(side="left", fill="y")
        self.input_list.config(yscrollcommand=sb.set)

        if HAS_DND:
            try:
                for widget in (self.root, self.input_list):
                    widget.drop_target_register(DND_FILES)
                    widget.dnd_bind("<<Drop>>", self.on_drop)
            except Exception:
                pass  # tkdnd が使えない環境では D&D なしで動作させる

        btn_row = ttk.Frame(in_frame)
        btn_row.pack(fill="x", pady=(4, 0))
        ttk.Button(btn_row, text="ファイル追加", command=self.add_files).pack(side="left", padx=2)
        ttk.Button(btn_row, text="フォルダ追加", command=self.add_folder).pack(side="left", padx=2)
        ttk.Button(btn_row, text="選択を削除", command=self.remove_selected).pack(side="left", padx=2)
        ttk.Button(btn_row, text="クリア", command=lambda: self.input_list.delete(0, "end")).pack(side="left", padx=2)

        # --- 圧縮設定 ---
        opt_frame = ttk.LabelFrame(main, text="圧縮設定", padding=6)
        opt_frame.pack(fill="x", **pad)
        opt_frame.columnconfigure(1, weight=1)
        opt_frame.columnconfigure(3, weight=1)

        ttk.Label(opt_frame, text="品質:").grid(row=0, column=0, sticky="e", padx=4, pady=3)
        qrow = ttk.Frame(opt_frame)
        qrow.grid(row=0, column=1, sticky="w", pady=3)
        self.quality_var = tk.IntVar(value=24)
        ttk.Spinbox(qrow, from_=14, to=35, width=5, textvariable=self.quality_var).pack(side="left")
        ttk.Label(qrow, text=" 小=高画質・大容量 (18:ほぼ無劣化 / 24:標準 / 28:容量優先)").pack(side="left")

        ttk.Label(opt_frame, text="コーデック:").grid(row=1, column=0, sticky="e", padx=4, pady=3)
        self.codec_var = tk.StringVar(value=list(CODEC_CHOICES)[0])
        ttk.Combobox(opt_frame, textvariable=self.codec_var, values=list(CODEC_CHOICES),
                     state="readonly", width=22).grid(row=1, column=1, sticky="w", pady=3)

        ttk.Label(opt_frame, text="エンコード:").grid(row=1, column=2, sticky="e", padx=4, pady=3)
        self.hw_var = tk.StringVar(value=list(HW_CHOICES)[0])
        ttk.Combobox(opt_frame, textvariable=self.hw_var, values=list(HW_CHOICES),
                     state="readonly", width=22).grid(row=1, column=3, sticky="w", pady=3)

        ttk.Label(opt_frame, text="フレームレート:").grid(row=2, column=0, sticky="e", padx=4, pady=3)
        self.fps_var = tk.StringVar(value=NO_CHANGE)
        ttk.Combobox(opt_frame, textvariable=self.fps_var, values=FPS_CHOICES,
                     width=22).grid(row=2, column=1, sticky="w", pady=3)

        ttk.Label(opt_frame, text="解像度 (高さ):").grid(row=2, column=2, sticky="e", padx=4, pady=3)
        self.height_var = tk.StringVar(value=NO_CHANGE)
        ttk.Combobox(opt_frame, textvariable=self.height_var, values=HEIGHT_CHOICES,
                     width=22).grid(row=2, column=3, sticky="w", pady=3)

        ttk.Label(opt_frame, text="音声:").grid(row=3, column=0, sticky="e", padx=4, pady=3)
        self.audio_var = tk.StringVar(value=list(AUDIO_CHOICES)[0])
        ttk.Combobox(opt_frame, textvariable=self.audio_var, values=list(AUDIO_CHOICES),
                     state="readonly", width=22).grid(row=3, column=1, sticky="w", pady=3)

        ttk.Label(opt_frame, text="切り出し:").grid(row=4, column=0, sticky="e", padx=4, pady=3)
        clip_row = ttk.Frame(opt_frame)
        clip_row.grid(row=4, column=1, columnspan=3, sticky="w", pady=3)
        self.clip_start_var = tk.StringVar()
        self.clip_end_var = tk.StringVar()
        ttk.Label(clip_row, text="開始").pack(side="left")
        ttk.Entry(clip_row, textvariable=self.clip_start_var, width=10).pack(side="left", padx=(2, 10))
        ttk.Label(clip_row, text="終了").pack(side="left")
        ttk.Entry(clip_row, textvariable=self.clip_end_var, width=10).pack(side="left", padx=(2, 10))
        ttk.Label(clip_row, text="(例: 90 や 1:30。空欄 = 全体)").pack(side="left")

        # --- 出力設定 ---
        out_frame = ttk.LabelFrame(main, text="出力設定", padding=6)
        out_frame.pack(fill="x", **pad)
        out_frame.columnconfigure(1, weight=1)

        self.outmode_var = tk.StringVar(value="suffix")

        ttk.Radiobutton(out_frame, text="同じフォルダに別名で保存 / 接尾辞:",
                        variable=self.outmode_var, value="suffix",
                        command=self._update_outmode).grid(row=0, column=0, sticky="w", pady=2)
        self.suffix_var = tk.StringVar(value="_compressed")
        self.suffix_entry = ttk.Entry(out_frame, textvariable=self.suffix_var, width=20)
        self.suffix_entry.grid(row=0, column=1, sticky="w", padx=4, pady=2)

        ttk.Radiobutton(out_frame, text="指定フォルダに保存:",
                        variable=self.outmode_var, value="dir",
                        command=self._update_outmode).grid(row=1, column=0, sticky="w", pady=2)
        dir_row = ttk.Frame(out_frame)
        dir_row.grid(row=1, column=1, sticky="ew", padx=4, pady=2)
        dir_row.columnconfigure(0, weight=1)
        self.outdir_var = tk.StringVar()
        self.outdir_entry = ttk.Entry(dir_row, textvariable=self.outdir_var)
        self.outdir_entry.grid(row=0, column=0, sticky="ew")
        self.outdir_btn = ttk.Button(dir_row, text="参照...", command=self.browse_outdir, width=8)
        self.outdir_btn.grid(row=0, column=1, padx=(4, 0))

        ttk.Radiobutton(out_frame, text="元ファイルを置き換える (元動画は削除されます)",
                        variable=self.outmode_var, value="replace",
                        command=self._update_outmode).grid(row=2, column=0, columnspan=2, sticky="w", pady=2)

        self.overwrite_var = tk.BooleanVar(value=False)
        self.overwrite_chk = ttk.Checkbutton(
            out_frame, text="出力先に同名ファイルがあれば上書きする (オフ: スキップ)",
            variable=self.overwrite_var)
        self.overwrite_chk.grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))

        self._update_outmode()

        # --- 実行 ---
        run_frame = ttk.Frame(main)
        run_frame.pack(fill="x", **pad)
        self.start_btn = ttk.Button(run_frame, text="圧縮開始", command=self.start)
        self.start_btn.pack(side="left", padx=2)
        self.cancel_btn = ttk.Button(run_frame, text="中止", command=self.cancel, state="disabled")
        self.cancel_btn.pack(side="left", padx=2)
        self.status_var = tk.StringVar(value="待機中")
        ttk.Label(run_frame, textvariable=self.status_var).pack(side="left", padx=12)

        self.progress = ttk.Progressbar(main, maximum=100)
        self.progress.pack(fill="x", padx=8, pady=(0, 4))

        # --- ログ ---
        self.log_box = scrolledtext.ScrolledText(main, height=12, state="disabled", wrap="word")
        self.log_box.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _update_outmode(self):
        mode = self.outmode_var.get()
        self.suffix_entry.config(state="normal" if mode == "suffix" else "disabled")
        state = "normal" if mode == "dir" else "disabled"
        self.outdir_entry.config(state=state)
        self.outdir_btn.config(state=state)
        self.overwrite_chk.config(state="disabled" if mode == "replace" else "normal")

    # ---------------------------------------------------------- 入力操作
    def add_files(self):
        exts = " ".join(f"*{e}" for e in sorted(core.VIDEO_EXTS))
        paths = filedialog.askopenfilenames(
            title="動画ファイルを選択",
            filetypes=[("動画ファイル", exts), ("すべてのファイル", "*.*")])
        for p in paths:
            self._add_input(p)

    def add_folder(self):
        path = filedialog.askdirectory(title="フォルダを選択")
        if path:
            self._add_input(path)

    def _add_input(self, path):
        existing = self.input_list.get(0, "end")
        if path not in existing:
            self.input_list.insert("end", path)

    def on_drop(self, event):
        self._add_dropped(event.data)

    def _add_dropped(self, data):
        """ドロップされたパス文字列 (スペース含みは {} 囲み) を解析して追加する。"""
        for p in self.root.tk.splitlist(data):
            path = Path(p)
            if path.is_dir() or (path.is_file() and path.suffix.lower() in core.VIDEO_EXTS):
                self._add_input(str(path))

    def remove_selected(self):
        for i in reversed(self.input_list.curselection()):
            self.input_list.delete(i)

    def browse_outdir(self):
        path = filedialog.askdirectory(title="出力先フォルダを選択")
        if path:
            self.outdir_var.set(path)

    # ---------------------------------------------------------- 実行
    def _gather_options(self):
        """UI から設定を読み取って検証する。問題があれば None を返す。"""
        inputs = list(self.input_list.get(0, "end"))
        if not inputs:
            messagebox.showwarning("入力がありません", "ファイルまたはフォルダを追加してください。")
            return None

        fps_s = self.fps_var.get().strip()
        height_s = self.height_var.get().strip().split()[0] if self.height_var.get().strip() else ""
        try:
            fps = None if fps_s in (NO_CHANGE, "") else float(fps_s)
            height = None if height_s in (NO_CHANGE, "") else int(height_s)
        except ValueError:
            messagebox.showwarning("入力エラー", "フレームレート・解像度は数値で指定してください。")
            return None

        try:
            clip_start = (core.parse_time(self.clip_start_var.get())
                          if self.clip_start_var.get().strip() else None)
            clip_end = (core.parse_time(self.clip_end_var.get())
                        if self.clip_end_var.get().strip() else None)
        except ValueError:
            messagebox.showwarning("入力エラー", "切り出しの時間は 90 や 1:30 のような形式で指定してください。")
            return None
        if clip_start is not None and clip_end is not None and clip_end <= clip_start:
            messagebox.showwarning("入力エラー", "切り出しの終了時間は開始時間より後にしてください。")
            return None

        mode = self.outmode_var.get()
        outdir = None
        if mode == "dir":
            outdir = self.outdir_var.get().strip()
            if not outdir:
                messagebox.showwarning("入力エラー", "出力先フォルダを指定してください。")
                return None

        suffix = self.suffix_var.get().strip() or "_compressed"

        opts = SimpleNamespace(
            quality=self.quality_var.get(),
            codec=CODEC_CHOICES[self.codec_var.get()],
            hw=HW_CHOICES[self.hw_var.get()],
            fps=fps,
            height=height,
            clip_start=clip_start,
            clip_end=clip_end,
            audio=AUDIO_CHOICES[self.audio_var.get()],
            audio_bitrate="160k",
            preset="medium",
            dry_run=False,
        )
        return SimpleNamespace(inputs=inputs, mode=mode, outdir=outdir, suffix=suffix,
                               overwrite=self.overwrite_var.get(), opts=opts)

    def start(self):
        cfg = self._gather_options()
        if cfg is None:
            return
        if cfg.mode == "replace":
            if not messagebox.askyesno(
                    "確認",
                    "圧縮後に元の動画ファイルを削除して置き換えます。\n"
                    "この操作は元に戻せません。続行しますか?",
                    icon="warning", default="no"):
                return

        self.cancel_event.clear()
        self.start_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self.progress["value"] = 0
        self.worker = threading.Thread(target=self._run_jobs, args=(cfg,), daemon=True)
        self.worker.start()

    def cancel(self):
        self.cancel_event.set()
        self.status_var.set("中止しています...")
        self.cancel_btn.config(state="disabled")

    def on_close(self):
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno("確認", "圧縮の実行中です。中止して終了しますか?"):
                return
            self.cancel_event.set()
        self.root.destroy()

    # ---------------------------------------------------------- ワーカー
    def _post(self, kind, *payload):
        self.msg_queue.put((kind, payload))

    def _run_jobs(self, cfg):
        log = lambda m: self._post("log", m)
        try:
            try:
                hw = core.pick_hw(cfg.opts.codec, cfg.opts.hw)
            except ValueError as e:
                self._post("error", str(e))
                return

            files = core.collect_inputs(cfg.inputs, log=log)
            if not files:
                self._post("error", "対象の動画ファイルが見つかりません。")
                return

            log(f"エンコーダー: {core.encoder_label(cfg.opts.codec, hw)} / 品質: {cfg.opts.quality}"
                + (f" / fps: {cfg.opts.fps:g}" if cfg.opts.fps else "")
                + (f" / 高さ: {cfg.opts.height}px" if cfg.opts.height else "")
                + (f" / 切り出し: {core.fmt_time(cfg.opts.clip_start or 0)}-"
                   + (core.fmt_time(cfg.opts.clip_end) if cfg.opts.clip_end is not None else "末尾")
                   if cfg.opts.clip_start or cfg.opts.clip_end is not None else ""))
            log(f"対象: {len(files)} ファイル\n")

            out_dir = None
            if cfg.mode == "dir":
                out_dir = Path(cfg.outdir)
                out_dir.mkdir(parents=True, exist_ok=True)

            total_src = total_dst = done = failed = skipped = 0
            for i, src in enumerate(files, 1):
                if self.cancel_event.is_set():
                    log("中止されました。")
                    break

                if cfg.mode == "replace":
                    dst = core.temp_output_path(src)
                elif out_dir:
                    dst = out_dir / (src.stem + ".mp4")
                else:
                    dst = src.with_name(src.stem + cfg.suffix + ".mp4")
                if dst.resolve() == src.resolve():
                    dst = src.with_name(src.stem + "_compressed.mp4")

                self._post("file", i, len(files), src.name)
                log(f"[{i}/{len(files)}] {src.name}")

                if cfg.mode != "replace" and dst.exists() and not cfg.overwrite:
                    log(f"  スキップ: 出力先に既に存在します ({dst.name})")
                    skipped += 1
                    continue

                src_size = src.stat().st_size
                result = core.compress_file(
                    src, dst, cfg.opts, hw,
                    on_progress=lambda p, s, e: self._post("progress", p, s, e),
                    cancel=self.cancel_event, log=log)

                if result == "ok":
                    if cfg.mode == "replace":
                        dst = core.replace_original(src, dst)
                    total_src += src_size
                    total_dst += dst.stat().st_size
                    done += 1
                elif result == "failed":
                    failed += 1
                elif result == "cancelled":
                    break
                else:
                    skipped += 1

            log("\n===== 結果 =====")
            log(f"成功: {done} / 失敗: {failed} / スキップ: {skipped}")
            if total_src:
                saved = total_src - total_dst
                log(f"合計: {core.human_size(total_src)} -> {core.human_size(total_dst)} "
                    f"(削減 {core.human_size(saved)}, {saved / total_src * 100:.0f}%減)")
        except Exception as e:  # 予期しないエラーは UI に表示する
            self._post("error", f"予期しないエラー: {e}")
        finally:
            self._post("finished")

    # ---------------------------------------------------------- UI 更新
    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.msg_queue.get_nowait()
                if kind == "log":
                    self._append_log(payload[0])
                elif kind == "file":
                    i, n, name = payload
                    self.status_var.set(f"{i}/{n}: {name}")
                    self.progress["value"] = 0
                elif kind == "progress":
                    pct, speed, eta = payload
                    self.progress["value"] = pct
                    cur = self.status_var.get().split("  |")[0]
                    self.status_var.set(f"{cur}  | {pct:.0f}%  {speed:.1f}x  残り {core.fmt_time(eta)}")
                elif kind == "error":
                    self._append_log("エラー: " + payload[0])
                    messagebox.showerror("エラー", payload[0])
                elif kind == "finished":
                    self.status_var.set("完了")
                    self.progress["value"] = 0
                    self.start_btn.config(state="normal")
                    self.cancel_btn.config(state="disabled")
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    def _append_log(self, text):
        self.log_box.config(state="normal")
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.config(state="disabled")


def main():
    root = TkinterDnD.Tk() if HAS_DND else tk.Tk()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)  # 高DPI対応
    except Exception:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
