from __future__ import annotations

import argparse
import os
import shutil
from typing import Iterable, Tuple

from PIL import Image


def iter_images(src_dir: str) -> Iterable[str]:
    for name in os.listdir(src_dir):
        path = os.path.join(src_dir, name)
        if not os.path.isfile(path):
            continue
        ext = os.path.splitext(name)[1].lower()
        if ext in (".jpg", ".jpeg", ".png"):
            yield path


def has_transparency(img: Image.Image) -> bool:
    if img.mode in ("RGBA", "LA"):
        alpha = img.getchannel("A")
        return alpha.getextrema()[0] < 255
    if img.mode == "P":
        return "transparency" in img.info
    return False


def compress_dir(src_dir: str, dst_dir: str, quality: int) -> Tuple[int, int, int]:
    return compress_dir_with_progress(src_dir, dst_dir, quality, None)


def compress_dir_with_progress(
    src_dir: str, dst_dir: str, quality: int, progress_cb
) -> Tuple[int, int, int]:
    os.makedirs(dst_dir, exist_ok=True)
    files = list(iter_images(src_dir))
    total = len(files)
    if progress_cb:
        progress_cb(0, total)
    out_paths = []
    for path in files:
        name = os.path.basename(path)
        base, ext = os.path.splitext(name)
        ext = ext.lower()
        out_path = os.path.join(dst_dir, name)
        out_is_jpeg = ext in (".jpg", ".jpeg")
        with Image.open(path) as img:
            if ext == ".png":
                if has_transparency(img):
                    out_path = os.path.join(dst_dir, base + ".png")
                    img.save(out_path, format="PNG", optimize=True, compress_level=9)
                    out_is_jpeg = False
                else:
                    out_path = os.path.join(dst_dir, base + ".jpg")
                    if img.mode not in ("RGB", "L"):
                        img = img.convert("RGB")
                    out_is_jpeg = True
            if out_is_jpeg:
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")
            exif = img.info.get("exif")
            icc = img.info.get("icc_profile")
            if out_is_jpeg:
                img.save(
                    out_path,
                    format="JPEG",
                    quality=quality,
                    optimize=True,
                    progressive=True,
                    exif=exif,
                    icc_profile=icc,
                )
        # If something went wrong and output is bigger, keep original.
        if os.path.getsize(out_path) > os.path.getsize(path):
            if out_path != os.path.join(dst_dir, name):
                try:
                    os.remove(out_path)
                except OSError:
                    pass
                out_path = os.path.join(dst_dir, name)
            shutil.copy2(path, out_path)
        out_paths.append(out_path)
        if progress_cb:
            progress_cb(1, total, step=True)
    return len(files), sum(os.path.getsize(p) for p in files), sum(
        os.path.getsize(p) for p in out_paths
    )


def run_cli(args: argparse.Namespace) -> None:
    count, src_bytes, dst_bytes = compress_dir(args.src, args.dst, args.quality)
    src_mb = round(src_bytes / (1024 * 1024), 2)
    dst_mb = round(dst_bytes / (1024 * 1024), 2)
    print(f"Processed {count} files")
    print(f"Source: {src_mb} MB")
    print(f"Output: {dst_mb} MB")


def run_gui() -> None:
    import threading
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    def browse_src() -> None:
        path = filedialog.askdirectory(title="원본 폴더 선택")
        if path:
            src_var.set(path)

    def browse_dst() -> None:
        path = filedialog.askdirectory(title="저장 폴더 선택")
        if path:
            dst_var.set(path)

    def set_ui_state(enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        src_entry.configure(state=state)
        dst_entry.configure(state=state)
        quality_entry.configure(state=state)
        browse_src_btn.configure(state=state)
        browse_dst_btn.configure(state=state)
        start_btn.configure(state=state)

    def progress_cb(delta: int, total: int, step: bool = False) -> None:
        def _update() -> None:
            if total == 0:
                progress_var.set(0)
                progress_label.configure(text="진행률: 0/0")
                return
            if step:
                progress_var.set(min(total, progress_var.get() + delta))
            else:
                progress_var.set(delta)
            progress_bar.configure(maximum=total)
            progress_label.configure(
                text=f"진행률: {int(progress_var.get())}/{total}"
            )

        root.after(0, _update)

    def run_worker(src: str, dst: str, quality: int) -> None:
        try:
            count, src_bytes, dst_bytes = compress_dir_with_progress(
                src, dst, quality, progress_cb
            )
        except Exception as exc:
            root.after(0, lambda: messagebox.showerror("오류", f"실패: {exc}"))
            root.after(0, lambda: set_ui_state(True))
            return

        src_mb = round(src_bytes / (1024 * 1024), 2)
        dst_mb = round(dst_bytes / (1024 * 1024), 2)
        root.after(
            0,
            lambda: messagebox.showinfo(
                "완료",
                f"처리된 파일: {count}개\n원본 용량: {src_mb} MB\n결과 용량: {dst_mb} MB",
            ),
        )
        root.after(0, lambda: set_ui_state(True))

    def run() -> None:
        src = src_var.get().strip()
        dst = dst_var.get().strip()
        if not src or not os.path.isdir(src):
            messagebox.showerror("오류", "올바른 원본 폴더를 선택하세요.")
            return
        if not dst:
            messagebox.showerror("오류", "저장 폴더를 선택하세요.")
            return
        try:
            quality = int(quality_var.get())
        except ValueError:
            messagebox.showerror("오류", "품질은 숫자로 입력하세요.")
            return
        if quality < 1 or quality > 95:
            messagebox.showerror("오류", "품질은 1~95 사이여야 합니다.")
            return

        progress_var.set(0)
        progress_label.configure(text="진행률: 0/0")
        set_ui_state(False)
        worker = threading.Thread(
            target=run_worker, args=(src, dst, quality), daemon=True
        )
        worker.start()

    root = tk.Tk()
    root.title("사진 용량 압축기")
    root.resizable(False, False)

    src_var = tk.StringVar()
    dst_var = tk.StringVar()
    quality_var = tk.StringVar(value="10")

    pad = {"padx": 8, "pady": 6}

    tk.Label(root, text="원본 폴더").grid(row=0, column=0, sticky="w", **pad)
    src_entry = tk.Entry(root, textvariable=src_var, width=52)
    src_entry.grid(row=0, column=1, **pad)
    browse_src_btn = tk.Button(root, text="찾기", command=browse_src)
    browse_src_btn.grid(row=0, column=2, **pad)

    tk.Label(root, text="저장 폴더").grid(row=1, column=0, sticky="w", **pad)
    dst_entry = tk.Entry(root, textvariable=dst_var, width=52)
    dst_entry.grid(row=1, column=1, **pad)
    browse_dst_btn = tk.Button(root, text="찾기", command=browse_dst)
    browse_dst_btn.grid(row=1, column=2, **pad)

    tk.Label(root, text="JPEG 품질(1-95)").grid(row=2, column=0, sticky="w", **pad)
    quality_entry = tk.Entry(root, textvariable=quality_var, width=10)
    quality_entry.grid(row=2, column=1, sticky="w", **pad)

    tk.Label(
        root,
        text="숫자가 낮을수록 용량↓ / 높을수록 용량↑",
    ).grid(row=3, column=0, columnspan=3, sticky="w", **pad)

    progress_var = tk.DoubleVar(value=0)
    progress_bar = ttk.Progressbar(
        root, orient="horizontal", length=420, mode="determinate", variable=progress_var
    )
    progress_bar.grid(row=4, column=0, columnspan=3, **pad)
    progress_label = tk.Label(root, text="진행률: 0/0")
    progress_label.grid(row=5, column=0, columnspan=3, **pad)

    start_btn = tk.Button(root, text="압축 시작", command=run, width=20)
    start_btn.grid(row=6, column=0, columnspan=3, pady=12)

    root.mainloop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Compress JPEGs in a folder.")
    parser.add_argument("src", nargs="?", help="Source folder with JPEGs")
    parser.add_argument("dst", nargs="?", help="Destination folder")
    parser.add_argument("--quality", type=int, default=10, help="JPEG quality (1-95)")
    args = parser.parse_args()

    if args.src and args.dst:
        run_cli(args)
    else:
        run_gui()


if __name__ == "__main__":
    main()
