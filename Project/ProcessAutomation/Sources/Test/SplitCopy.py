import os
import threading
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import json

CONFIG_FILE = "split_copy_config.json"

def save_settings(settings):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"設定保存エラー: {e}")

def load_settings():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def log(msg, log_file, log_text=None):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S] ")
    entry = f"{timestamp}{msg}\n"
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(entry)
    if log_text:
        log_text.insert(tk.END, entry)
        log_text.see(tk.END)

def copy_part(src_path, dest_dir, part_num, chunk_size, total_size, base_name, log_func):
    offset = part_num * chunk_size
    size = min(chunk_size, total_size - offset)
    part_filename = f"{base_name}.part{part_num:03}"
    part_path = os.path.join(dest_dir, part_filename)

    if os.path.exists(part_path) and os.path.getsize(part_path) == size:
        log_func(f"[スキップ] {part_filename}")
        return

    try:
        with open(src_path, 'rb') as src:
            src.seek(offset)
            with open(part_path, 'wb') as dst:
                remaining = size
                while remaining > 0:
                    buf = src.read(min(64 * 1024, remaining))
                    if not buf:
                        break
                    dst.write(buf)
                    remaining -= len(buf)
        log_func(f"[完了] {part_filename}")
    except Exception as e:
        log_func(f"[エラー] {part_filename} - {e}")

def parallel_split_copy(src_path, dest_dir, chunk_size_mb, start_part, max_workers, progress_bar, progress_label, start_button, log_text):
    start_button.config(state="disabled")
    log_file = os.path.join(dest_dir, "split_copy.log")

    def gui_log(msg):
        log(msg, log_file, log_text)

    try:
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)

        total_size = os.path.getsize(src_path)
        chunk_size = chunk_size_mb * 1024 * 1024
        total_parts = (total_size + chunk_size - 1) // chunk_size
        base_name = os.path.basename(src_path)

        completed_parts = 0

        def update_progress():
            nonlocal completed_parts
            completed_parts += 1
            percent = int(completed_parts / (total_parts - start_part) * 100)
            progress_bar["value"] = percent
            progress_label.config(text=f"{percent}% 完了")

        gui_log(f"開始: {src_path} → {dest_dir}")
        gui_log(f"サイズ: {total_size} bytes / 分割数: {total_parts}（{chunk_size_mb}MBごと）")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for part_num in range(start_part, total_parts):
                futures.append(executor.submit(copy_part, src_path, dest_dir, part_num, chunk_size, total_size, base_name, gui_log))

            for future in futures:
                future.result()
                update_progress()

        gui_log("完了しました。")
        messagebox.showinfo("完了", "分割コピーが完了しました。")

    except Exception as e:
        gui_log(f"[致命的エラー] {e}")
        messagebox.showerror("エラー", str(e))

    finally:
        start_button.config(state="normal")

def start_copy(source_entry, dest_entry, size_entry, start_part_entry, thread_entry, progress_bar, progress_label, start_button, log_text):
    # 実行前に保存
    source = source_entry.get()
    dest = dest_entry.get()
    try:
        chunk_mb = int(size_entry.get())
        start_part = int(start_part_entry.get())
        max_threads = int(thread_entry.get())
    except:
        messagebox.showerror("エラー", "サイズ、開始パート番号、スレッド数は数値で入力してください")
        return

    settings = {
        "source": source,
        "dest": dest,
        "chunk_mb": chunk_mb,
        "start_part": start_part,
        "max_threads": max_threads
    }
    save_settings(settings)
    source = source_entry.get()
    dest = dest_entry.get()
    try:
        chunk_mb = int(size_entry.get())
        start_part = int(start_part_entry.get())
        max_threads = int(thread_entry.get())
    except:
        messagebox.showerror("エラー", "サイズ、開始パート番号、スレッド数は数値で入力してください")
        return

    if not os.path.isfile(source):
        messagebox.showerror("エラー", "元ファイルが見つかりません")
        return
    if not os.path.isdir(dest):
        messagebox.showerror("エラー", "保存先フォルダが存在しません")
        return

    # 保存する設定を辞書化
    settings = {
        "source": source,
        "dest": dest,
        "chunk_mb": chunk_mb,
        "start_part": start_part,
        "max_threads": max_threads
    }
    save_settings(settings)

    thread = threading.Thread(
        target=parallel_split_copy,
        args=(source, dest, chunk_mb, start_part, max_threads, progress_bar, progress_label, start_button, log_text),
        daemon=True
    )
    thread.start()

def join_parts(folder_entry, output_entry, log_text):
    folder = folder_entry.get()
    output_file = output_entry.get()
    log_file = os.path.join(folder, "join.log")

    def gui_log(msg):
        log(msg, log_file, log_text)

    try:
        part_files = sorted([f for f in os.listdir(folder) if f.endswith(".part000") or f.endswith(".part001") or f.endswith(".part") or ".part" in f])
        if not part_files:
            raise Exception("分割ファイルが見つかりません")

        base_name = part_files[0].split(".part")[0]
        part_files = sorted([f for f in os.listdir(folder) if f.startswith(base_name) and ".part" in f])

        with open(output_file, 'wb') as out:
            for f in part_files:
                part_path = os.path.join(folder, f)
                gui_log(f"結合: {f}")
                with open(part_path, 'rb') as pf:
                    while True:
                        chunk = pf.read(64 * 1024)
                        if not chunk:
                            break
                        out.write(chunk)
        gui_log("結合完了")
        messagebox.showinfo("完了", "ファイルの結合が完了しました。")
    except Exception as e:
        gui_log(f"[エラー] {e}")
        messagebox.showerror("エラー", str(e))

def create_gui():
    root = tk.Tk()
    root.title("並列分割コピー ツール")
    root.geometry("800x650")

    settings = load_settings()

    tab_control = ttk.Notebook(root)
    copy_tab = tk.Frame(tab_control)
    join_tab = tk.Frame(tab_control)

    tab_control.add(copy_tab, text='分割コピー')
    tab_control.add(join_tab, text='ファイル結合')
    tab_control.pack(expand=1, fill='both')

    # 分割コピータブ
    tk.Label(copy_tab, text="元ファイル:").grid(row=0, column=0, sticky="w", padx=10, pady=5)
    source_entry = tk.Entry(copy_tab, width=60)
    source_entry.grid(row=0, column=1)
    tk.Button(copy_tab, text="参照", command=lambda: source_entry.insert(0, filedialog.askopenfilename())).grid(row=0, column=2)
    source_entry.insert(0, settings.get("source", ""))

    tk.Label(copy_tab, text="保存先フォルダ:").grid(row=1, column=0, sticky="w", padx=10, pady=5)
    dest_entry = tk.Entry(copy_tab, width=60)
    dest_entry.grid(row=1, column=1)
    tk.Button(copy_tab, text="参照", command=lambda: dest_entry.insert(0, filedialog.askdirectory())).grid(row=1, column=2)
    dest_entry.insert(0, settings.get("dest", ""))

    tk.Label(copy_tab, text="分割サイズ(MB):").grid(row=2, column=0, sticky="w", padx=10, pady=5)
    size_entry = tk.Entry(copy_tab, width=10)
    size_entry.insert(0, str(settings.get("chunk_mb", 1024)))
    size_entry.grid(row=2, column=1, sticky="w")

    tk.Label(copy_tab, text="開始パート番号:").grid(row=3, column=0, sticky="w", padx=10, pady=5)
    start_part_entry = tk.Entry(copy_tab, width=10)
    start_part_entry.insert(0, str(settings.get("start_part", 0)))
    start_part_entry.grid(row=3, column=1, sticky="w")

    tk.Label(copy_tab, text="スレッド数:").grid(row=4, column=0, sticky="w", padx=10, pady=5)
    thread_entry = tk.Entry(copy_tab, width=10)
    thread_entry.insert(0, str(settings.get("max_threads", 4)))
    thread_entry.grid(row=4, column=1, sticky="w")

    progress_label = tk.Label(copy_tab, text="進捗: 0%")
    progress_label.grid(row=5, column=0, columnspan=3, pady=5)
    progress_bar = ttk.Progressbar(copy_tab, length=700, mode='determinate')
    progress_bar.grid(row=6, column=0, columnspan=3, padx=20)

    log_text = tk.Text(copy_tab, height=10, wrap="none")
    log_text.grid(row=8, column=0, columnspan=3, padx=10, pady=5)

    start_button = tk.Button(copy_tab, text="分割コピー開始", width=20,
        command=lambda: start_copy(source_entry, dest_entry, size_entry, start_part_entry, thread_entry, progress_bar, progress_label, start_button, log_text))
    start_button.grid(row=7, column=0, columnspan=3, pady=10)

    # 結合タブ
    tk.Label(join_tab, text="分割ファイルのフォルダ:").grid(row=0, column=0, sticky="w", padx=10, pady=5)
    folder_entry = tk.Entry(join_tab, width=60)
    folder_entry.grid(row=0, column=1)
    tk.Button(join_tab, text="参照", command=lambda: folder_entry.insert(0, filedialog.askdirectory())).grid(row=0, column=2)

    tk.Label(join_tab, text="結合後ファイル名:").grid(row=1, column=0, sticky="w", padx=10, pady=5)
    output_entry = tk.Entry(join_tab, width=60)
    output_entry.grid(row=1, column=1)
    tk.Button(join_tab, text="保存先", command=lambda: output_entry.insert(0, filedialog.asksaveasfilename())).grid(row=1, column=2)

    tk.Button(join_tab, text="ファイルを結合", width=20,
        command=lambda: join_parts(folder_entry, output_entry, log_text)).grid(row=2, column=0, columnspan=3, pady=10)

    root.mainloop()

if __name__ == "__main__":
    create_gui()
