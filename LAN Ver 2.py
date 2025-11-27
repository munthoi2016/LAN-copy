import os
import shutil
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from tkinter import *
from tkinter import ttk, messagebox, filedialog
from tkcalendar import Calendar
import subprocess

SCAN_THREADS = 80
COPY_THREADS = 40

def is_host_alive(ip):
    try:
        result = subprocess.run(
            ["ping", "-n", "1", "-w", "300", ip],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=0x08000000
        )
        return result.returncode == 0
    except:
        return False

def scan_lan(ip_prefix):
    alive_hosts = []

    def scan_ip(i):
        ip = f"{ip_prefix}{i}"
        if is_host_alive(ip):
            alive_hosts.append(ip)

    with ThreadPoolExecutor(max_workers=SCAN_THREADS) as executor:
        executor.map(scan_ip, range(1, 255))

    return alive_hosts

def copy_csv_from_host(ip, selected_dates, save_root, log_callback, shared_name):
    try:
        shared_path = f"\\\\{ip}\\{shared_name}\\"
        if not os.path.exists(shared_path):
            log_callback(f"[{ip}] Không truy cập được share → Bỏ qua")
            return

        try:
            hostname = socket.gethostbyaddr(ip)[0]
        except:
            hostname = ip

        matched_files = []

        for file in os.listdir(shared_path):
            if not file.lower().endswith(".csv"):
                continue

            fpath = os.path.join(shared_path, file)
            try:
                ctime = datetime.fromtimestamp(os.path.getctime(fpath)).date()
                log_callback(f"[{ip}] Tìm thấy file: {file} — ngày tạo: {ctime}")

                if ctime in selected_dates:
                    matched_files.append((fpath, file))
            except Exception as e:
                log_callback(f"[{ip}] Lỗi đọc file: {file} → {e}")

        if matched_files:
            machine_folder = os.path.join(save_root, hostname)
            os.makedirs(machine_folder, exist_ok=True)
            for fpath, file in matched_files:
                shutil.copy2(fpath, os.path.join(machine_folder, file))
                log_callback(f"[{ip}] Copied: {file}")
        else:
            log_callback(f"[{ip}] Không có file CSV phù hợp → Không tạo thư mục")
    except Exception as e:
        log_callback(f"[{ip}] ERROR: {e}")

class MultiDatePicker(Toplevel):
    def __init__(self, master, selected_dates_callback):
        super().__init__(master)
        self.title("Chọn nhiều ngày")
        self.geometry("350x350")
        self.selected_dates = set()
        self.callback = selected_dates_callback

        Label(self, text="Click để chọn nhiều ngày").pack(pady=10)
        self.cal = Calendar(self, selectmode="day", date_pattern="yyyy-mm-dd")
        self.cal.pack(pady=10)

        Button(self, text="Thêm ngày", command=self.add_date).pack(pady=5)
        Button(self, text="Xong", command=self.finish).pack(pady=5)

        self.listbox = Listbox(self)
        self.listbox.pack(fill="both", expand=True, pady=10)

    def add_date(self):
        date_str = self.cal.get_date()
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        if date_obj not in self.selected_dates:
            self.selected_dates.add(date_obj)
            self.listbox.insert(END, str(date_obj))

    def finish(self):
        self.callback(self.selected_dates)
        self.destroy()

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("LAN CSV Collector — Multi-Date")
        self.root.geometry("750x700")

        self.selected_dates = set()
        self.shared_folder_name = StringVar(value="Logs")

        frame = Frame(root)
        frame.pack(pady=10)

        Button(frame, text="Chọn nhiều ngày CSV", command=self.open_multi_date_picker,
               bg="#4b8fea", fg="white").grid(row=0, column=0, padx=10)
        self.date_label = Label(frame, text="Chưa chọn ngày")
        self.date_label.grid(row=0, column=1)

        self.save_path_var = StringVar()
        Entry(frame, textvariable=self.save_path_var, width=45).grid(row=1, column=0, columnspan=2, pady=5)
        Button(frame, text="Chọn thư mục lưu", command=self.choose_folder).grid(row=1, column=2, padx=5)

        Label(frame, text="Tên thư mục chia sẻ:").grid(row=2, column=0, sticky="e", padx=5)
        Entry(frame, textvariable=self.shared_folder_name, width=30).grid(row=2, column=1, pady=5)

        Button(root, text="Quét máy trong LAN", command=self.scan_network,
               width=30, bg="#3fa9f5", fg="white").pack(pady=10)
        Button(root, text="Hiển thị IP & Tên máy", command=self.show_hosts,
               width=30, bg="#f5a742", fg="white").pack(pady=5)
        Button(root, text="Copy CSV theo ngày đã chọn", command=self.start_copy,
               width=30, bg="#32c832", fg="white").pack(pady=10)

        Label(root, text="Logs:").pack()
        self.log_box = Text(root, width=90, height=28)
        self.log_box.pack(pady=5)

        self.online_hosts = []

    def log(self, text):
        self.log_box.insert(END, text + "\n")
        self.log_box.see(END)

    def choose_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.save_path_var.set(path)

    def open_multi_date_picker(self):
        MultiDatePicker(self.root, self.update_selected_dates)

    def update_selected_dates(self, dates_set):
        self.selected_dates = dates_set
        if dates_set:
            text = ", ".join(sorted([str(d) for d in dates_set]))
        else:
            text = "Chưa chọn ngày"
        self.date_label.config(text=text)

    def scan_network(self):
        ip_local = socket.gethostbyname(socket.gethostname())
        ip_prefix = ".".join(ip_local.split(".")[:-1]) + "."
        self.log(f"Đang quét LAN: {ip_prefix}1 → 254 ...")

        def thread_scan():
            self.online_hosts = scan_lan(ip_prefix)
            self.log("====== SCAN FINISHED ======")
            self.log(f"Máy online tìm thấy: {len(self.online_hosts)}")

        threading.Thread(target=thread_scan, daemon=True).start()

    def show_hosts(self):
        if not self.online_hosts:
            messagebox.showinfo("Thông tin", "Chưa có danh sách máy online.")
            return
        self.log("=== DANH SÁCH MÁY ONLINE ===")
        for ip in self.online_hosts:
            try:
                name = socket.gethostbyaddr(ip)[0]
            except:
                name = "(Không xác định)"
            self.log(f"{ip} — {name}")

    def start_copy(self):
        if not self.online_hosts:
            messagebox.showerror("Lỗi", "Chưa có danh sách máy online! Hãy quét mạng trước.")
            return
        if not self.selected_dates:
            messagebox.showerror("Lỗi", "Chưa chọn ngày CSV!")
            return
        save_root = self.save_path_var.get().strip()
        if not save_root:
            messagebox.showerror("Lỗi", "Chưa chọn thư mục lưu!")
            return
        shared_name = self.shared_folder_name.get().strip()
        if not shared_name:
            messagebox.showerror("Lỗi", "Chưa nhập tên thư mục chia sẻ!")
            return

        self.log("=== COPY CSV BẮT ĐẦU ===")

        def thread_copy():
            with ThreadPoolExecutor(max_workers=COPY_THREADS) as executor:
                for ip in self.online_hosts:
                    executor.submit(copy_csv_from_host, ip, self.selected_dates, save_root, self.log, shared_name)
            self.log("=== COPY CSV HOÀN TẤT ===")

        threading.Thread(target=thread_copy, daemon=True).start()

if __name__ == "__main__":
    root = Tk()
    app = App(root)
    root.mainloop()
