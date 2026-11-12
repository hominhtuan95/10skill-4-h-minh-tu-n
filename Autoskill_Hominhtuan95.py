import ctypes
import hashlib
import json
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
import winreg
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

APP = 'Autoskill Hominhtuan95'
PUBLIC_KEY_HEX = 'REPLACE_WITH_PUBLIC_KEY'
LICENSE_DIR = Path(os.getenv('LOCALAPPDATA', str(Path.home()))) / 'AutoskillHominhtuan95'
LICENSE_FILE = LICENSE_DIR / 'license.txt'
USER32 = ctypes.windll.user32
WM_KEYDOWN, WM_KEYUP = 0x0100, 0x0101
VK = {'Tab': 0x09, 'Space': 0x20, **{f'Skill {i}': ord(str(i)) for i in range(1, 10)}, 'Skill 10': ord('0')}
KEYS = list(VK)
DEFAULT_DELAYS = [5000, 300] + [1000] * 10


def machine_hwid():
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Cryptography') as k:
        guid, _ = winreg.QueryValueEx(k, 'MachineGuid')
    return hashlib.sha256(('Autoskill-Hominhtuan95|' + guid).encode()).hexdigest()[:32].upper()


def verify_license(token, hwid):
    try:
        payload_hex, signature_hex = token.strip().split('.')
        payload = bytes.fromhex(payload_hex)
        signature = bytes.fromhex(signature_hex)
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(PUBLIC_KEY_HEX)).verify(signature, payload)
        data = json.loads(payload.decode('utf-8'))
        return data.get('hwid') == hwid and data.get('product') == 'AutoskillHominhtuan95'
    except Exception:
        return False


def require_license(root):
    hwid = machine_hwid()
    try:
        if verify_license(LICENSE_FILE.read_text(encoding='utf-8'), hwid):
            return True
    except OSError:
        pass
    dlg = tk.Toplevel(root)
    dlg.title('Kích hoạt bản quyền theo máy')
    dlg.geometry('660x300')
    dlg.transient(root)
    dlg.grab_set()
    result = {'ok': False}
    ttk.Label(dlg, text='Mã máy (HWID) — gửi mã này cho người cấp phép:').pack(anchor='w', padx=16, pady=(14, 3))
    hwid_var = tk.StringVar(master=dlg, value=hwid)
    entry = ttk.Entry(dlg, textvariable=hwid_var, state='readonly', width=70)
    entry.pack(fill='x', padx=16)
    def copy_hwid():
        dlg.clipboard_clear()
        dlg.clipboard_append(hwid)
    ttk.Button(dlg, text='Sao chép HWID', command=copy_hwid).pack(anchor='w', padx=16, pady=7)
    ttk.Label(dlg, text='Dán mã kích hoạt:').pack(anchor='w', padx=16)
    token_box = tk.Text(dlg, height=4, wrap='word')
    token_box.pack(fill='both', expand=True, padx=16, pady=5)
    def activate():
        token = token_box.get('1.0', 'end').strip()
        if not verify_license(token, hwid):
            messagebox.showerror('Không hợp lệ', 'Mã kích hoạt sai hoặc không thuộc máy này.', parent=dlg)
            return
        LICENSE_DIR.mkdir(parents=True, exist_ok=True)
        LICENSE_FILE.write_text(token, encoding='utf-8')
        result['ok'] = True
        dlg.destroy()
    ttk.Button(dlg, text='Kích hoạt', command=activate).pack(pady=9)
    dlg.protocol('WM_DELETE_WINDOW', dlg.destroy)
    root.wait_window(dlg)
    return result['ok']


def list_game_windows():
    found = []
    cb_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def callback(hwnd, _):
        if not USER32.IsWindowVisible(hwnd):
            return True
        length = USER32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        USER32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        if 'chien quoc' in title.lower() or 'chiến quốc' in title.lower():
            found.append((int(hwnd), title))
        return True
    callback_ref = cb_type(callback)
    USER32.EnumWindows(callback_ref, 0)
    return found


def post_key(hwnd, vk):
    if not USER32.IsWindow(hwnd):
        return False
    USER32.PostMessageW(hwnd, WM_KEYDOWN, vk, 0)
    time.sleep(0.045)
    USER32.PostMessageW(hwnd, WM_KEYUP, vk, 0xC0000001)
    return True


class Slot:
    def __init__(self, parent, number):
        self.number = number
        self.hwnd = None
        self.stop = threading.Event()
        self.thread = None
        self.rows = []
        frame = ttk.LabelFrame(parent, text=f'Cửa sổ {number}', padding=8)
        frame.grid(row=0, column=number-1, sticky='nsew', padx=5, pady=5)
        self.frame = frame
        self.window_var = tk.StringVar(value='Chưa chọn cửa sổ game')
        ttk.Label(frame, textvariable=self.window_var, wraplength=215).pack(fill='x')
        ttk.Button(frame, text='Chọn cửa sổ game', command=self.pick_window).pack(fill='x', pady=5)
        self.enabled = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame, text='Cho phép Auto cửa sổ này', variable=self.enabled).pack(anchor='w')
        headers = ttk.Frame(frame)
        headers.pack(fill='x')
        ttk.Label(headers, text='Chức năng', width=12).pack(side='left')
        ttk.Label(headers, text='Thời gian (ms)').pack(side='left')
        for name, default in zip(KEYS, DEFAULT_DELAYS):
            row = ttk.Frame(frame)
            row.pack(fill='x', pady=1)
            checked = tk.BooleanVar(value=name in ('Tab', 'Space'))
            ttk.Checkbutton(row, text=name, variable=checked, width=11).pack(side='left')
            delay = tk.StringVar(value=str(default))
            ttk.Entry(row, textvariable=delay, width=10).pack(side='left')
            self.rows.append((name, checked, delay))
        self.status = tk.StringVar(value='Đang dừng')
        ttk.Label(frame, textvariable=self.status).pack(pady=6)

    def pick_window(self):
        windows = list_game_windows()
        if not windows:
            messagebox.showwarning('Không tìm thấy', 'Hãy mở game Chiến Quốc trước.')
            return
        popup = tk.Toplevel(self.frame)
        popup.title(f'Chọn game cho cửa sổ {self.number}')
        popup.geometry('530x240')
        popup.grab_set()
        choices = [f'{hwnd} | {title}' for hwnd, title in windows]
        box = tk.Listbox(popup)
        box.pack(fill='both', expand=True, padx=12, pady=12)
        for item in choices:
            box.insert('end', item)
        def choose():
            selection = box.curselection()
            if not selection:
                return
            idx = selection[0]
            self.hwnd = windows[idx][0]
            self.window_var.set(choices[idx])
            popup.destroy()
        ttk.Button(popup, text='Chọn', command=choose).pack(pady=(0, 10))
        box.bind('<Double-Button-1>', lambda _: choose())

    def config(self):
        values = []
        for name, checked, delay in self.rows:
            if not checked.get():
                continue
            try:
                ms = int(delay.get())
                if not 50 <= ms <= 180000:
                    raise ValueError
            except ValueError:
                raise ValueError(f'Cửa sổ {self.number}: {name} phải từ 50 đến 180000 ms')
            values.append((VK[name], ms / 1000, name))
        return values

    def start(self, config):
        self.stop.clear()
        self.thread = threading.Thread(target=self.run, args=(config,), daemon=True)
        self.thread.start()
        self.status.set('Đang chạy')

    def run(self, config):
        next_times = [time.monotonic()] * len(config)
        while not self.stop.is_set():
            now = time.monotonic()
            for i, (vk, interval, _) in enumerate(config):
                if self.stop.is_set():
                    break
                if now >= next_times[i]:
                    if not post_key(self.hwnd, vk):
                        self.stop.set()
                        break
                    next_times[i] = time.monotonic() + interval
            self.stop.wait(0.02)

    def halt(self):
        self.stop.set()
        self.status.set('Đang dừng')


class App:
    def __init__(self, root):
        self.root = root
        self.running = False
        root.title(APP + ' | 4 cửa sổ | HWID')
        root.geometry('1080x650')
        root.minsize(980, 620)
        ttk.Label(root, text='Autoskill Hominhtuan95 — 4 cửa sổ, 10 Skill, Tab, Space', font=('Segoe UI', 13, 'bold')).pack(pady=10)
        outer = ttk.Frame(root)
        outer.pack(fill='both', expand=True)
        for i in range(4):
            outer.columnconfigure(i, weight=1)
        self.slots = [Slot(outer, i+1) for i in range(4)]
        buttons = ttk.Frame(root)
        buttons.pack(pady=10)
        self.toggle_btn = ttk.Button(buttons, text='BẬT AUTO (F1)', command=self.toggle)
        self.toggle_btn.pack(side='left', padx=10)
        ttk.Button(buttons, text='DỪNG TẤT CẢ', command=self.stop_all).pack(side='left')
        ttk.Label(root, text='F1 chỉ hoạt động khi cửa sổ AutoSkill đang được chọn. Gửi phím qua PostMessageW; cần thử với game thực tế.').pack(pady=(0, 8))
        root.bind_all('<F1>', self.on_f1)
        root.protocol('WM_DELETE_WINDOW', self.close)

    def on_f1(self, event):
        self.toggle()
        return 'break'

    def toggle(self):
        if self.running:
            self.stop_all()
            return
        targets = [s for s in self.slots if s.enabled.get() and s.hwnd]
        if not targets:
            messagebox.showwarning('Chưa chọn game', 'Hãy chọn ít nhất một cửa sổ game.')
            return
        handles = [s.hwnd for s in targets]
        if len(set(handles)) != len(handles):
            messagebox.showwarning('Trùng cửa sổ', 'Mỗi ô phải chọn một cửa sổ game khác nhau.')
            return
        try:
            configs = [(s, s.config()) for s in targets]
        except ValueError as exc:
            messagebox.showerror('Sai thời gian', str(exc))
            return
        for s, config in configs:
            s.start(config)
        self.running = True
        self.toggle_btn.configure(text='TẮT AUTO (F1)')

    def stop_all(self):
        for s in self.slots:
            s.halt()
        self.running = False
        self.toggle_btn.configure(text='BẬT AUTO (F1)')

    def close(self):
        self.stop_all()
        self.root.destroy()


def main():
    root = tk.Tk()
    root.withdraw()
    if not require_license(root):
        root.destroy()
        return
    root.deiconify()
    App(root)
    root.mainloop()

if __name__ == '__main__':
    main()
