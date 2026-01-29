import os
import re
import sys
import threading
from typing import Callable, Tuple


def rename_logs_by_hostname(
    folder_path: str, log_cb: Callable[[str], None] | None = None
) -> Tuple[int, int, int]:
    sysname_re = re.compile(r"SysName\s*:\s*([A-Za-z0-9._-]+)", re.IGNORECASE)
    renamed = 0
    skipped = 0
    failed = 0

    def log(msg: str) -> None:
        if log_cb:
            log_cb(msg)
        else:
            print(msg)

    for filename in os.listdir(folder_path):
        if not filename.lower().endswith(".log"):
            continue

        file_path = os.path.join(folder_path, filename)
        if not os.path.isfile(file_path):
            continue

        hostname = None

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    m = sysname_re.search(line)
                    if m:
                        hostname = m.group(1)
                        break
        except Exception as e:
            log(f"[SKIP] Could not read {filename}: {e}")
            skipped += 1
            continue

        if not hostname:
            log(f"[SKIP] {filename}: SysName not found")
            skipped += 1
            continue

        base = hostname
        ext = ".log"
        new_filename = f"{base}{ext}"
        new_path = os.path.join(folder_path, new_filename)

        if os.path.abspath(new_path) == os.path.abspath(file_path):
            log(f"[OK]   {filename} already named correctly")
            skipped += 1
            continue

        counter = 1
        while os.path.exists(new_path):
            new_filename = f"{base}_{counter}{ext}"
            new_path = os.path.join(folder_path, new_filename)
            counter += 1

        try:
            os.replace(file_path, new_path)
            log(f"[RENAME] {filename} -> {new_filename}")
            renamed += 1
        except Exception as e:
            log(f"[FAIL]   {filename}: {e}")
            failed += 1

    return renamed, skipped, failed


def run_gui() -> None:
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext

    def browse_folder() -> None:
        path = filedialog.askdirectory(title="로그 폴더 선택")
        if path:
            folder_var.set(path)

    def set_ui_state(enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        folder_entry.configure(state=state)
        browse_btn.configure(state=state)
        start_btn.configure(state=state)

    def append_log(msg: str) -> None:
        log_box.configure(state="normal")
        log_box.insert(tk.END, msg + "\n")
        log_box.see(tk.END)
        log_box.configure(state="disabled")

    def run_worker(folder: str) -> None:
        try:
            renamed, skipped, failed = rename_logs_by_hostname(folder, log_cb=log_cb)
        except Exception as exc:
            root.after(0, lambda: messagebox.showerror("오류", f"실패: {exc}"))
            root.after(0, lambda: set_ui_state(True))
            return

        root.after(
            0,
            lambda: messagebox.showinfo(
                "완료",
                f"완료\n이름 변경: {renamed}개\n건너뜀: {skipped}개\n실패: {failed}개",
            ),
        )
        root.after(0, lambda: set_ui_state(True))

    def log_cb(msg: str) -> None:
        root.after(0, lambda: append_log(msg))

    def run() -> None:
        folder = folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("오류", "올바른 폴더를 선택하세요.")
            return
        log_box.configure(state="normal")
        log_box.delete("1.0", tk.END)
        log_box.configure(state="disabled")
        set_ui_state(False)
        worker = threading.Thread(target=run_worker, args=(folder,), daemon=True)
        worker.start()

    root = tk.Tk()
    root.title("로그 파일 이름 변경기")
    root.resizable(False, False)

    folder_var = tk.StringVar()

    pad = {"padx": 8, "pady": 6}

    tk.Label(root, text="로그 폴더").grid(row=0, column=0, sticky="w", **pad)
    folder_entry = tk.Entry(root, textvariable=folder_var, width=52)
    folder_entry.grid(row=0, column=1, **pad)
    browse_btn = tk.Button(root, text="찾기", command=browse_folder)
    browse_btn.grid(row=0, column=2, **pad)

    log_box = scrolledtext.ScrolledText(root, width=72, height=14, state="disabled")
    log_box.grid(row=1, column=0, columnspan=3, **pad)

    start_btn = tk.Button(root, text="이름 변경 시작", command=run, width=20)
    start_btn.grid(row=2, column=0, columnspan=3, pady=12)

    root.mainloop()


def main() -> None:
    if len(sys.argv) > 1:
        target = sys.argv[1]
        if not os.path.isdir(target):
            print(f"Target is not a directory: {target}")
            sys.exit(1)
        rename_logs_by_hostname(target)
    else:
        run_gui()


if __name__ == "__main__":
    main()
