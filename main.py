import sys
import os
import json
import gc
import time

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

CONFIG_FILE = "config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {"theme": "dark", "engine": "google", "dns": "none"}

def save_config(config):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f)
    except:
        pass

config = load_config()

# Import PyQt6 FIRST (tidak perlu env trick karena pakai WebView2)
from PyQt6.QtCore import QUrl, Qt, QTimer, QEvent, QThread, pyqtSignal, QStringListModel, QPoint
from PyQt6.QtWidgets import (QApplication, QMainWindow, QLineEdit,
                             QToolBar, QTabBar, QStackedLayout, QWidget, QVBoxLayout, QMenu, QToolButton, QFileDialog, QCompleter,
                             QDialog, QFormLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QListWidget, QListWidgetItem, QFrame)
from PyQt6.QtGui import QAction, QIcon, QKeySequence, QShortcut
from qtwebview2 import QtWebViewWidget
import urllib.request
import urllib.error
import urllib.parse
from urllib.parse import urlparse
import threading
import gc
import time
import ctypes
import ctypes.wintypes

class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", ctypes.wintypes.DWORD),
        ("scanCode", ctypes.wintypes.DWORD),
        ("flags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.wintypes.ULONG))
    ]

LRESULT = ctypes.c_ssize_t
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM)

_global_hook_proc = None
_global_hook_id = None
_browser_instance = None
_app_instance = None

def is_yuukaa_focused():
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    if not hwnd: return False
    
    # 1. Cek apakah ini window utama kita atau anak-anaknya (termasuk Edge WebView2)
    if _browser_instance:
        main_hwnd = int(_browser_instance.winId())
        if hwnd == main_hwnd: return True
        if ctypes.windll.user32.IsChild(main_hwnd, hwnd): return True
        
        buf = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetClassNameW(hwnd, buf, 256)
        cname = buf.value
        if cname in ("Chrome_WidgetWin_0", "Chrome_WidgetWin_1", "Chrome_RenderWidgetHostHWND"):
            rect = ctypes.wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
            main_rect = ctypes.wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(main_hwnd, ctypes.byref(main_rect))
            
            center_x = (rect.left + rect.right) // 2
            center_y = (rect.top + rect.bottom) // 2
            if main_rect.left <= center_x <= main_rect.right and main_rect.top <= center_y <= main_rect.bottom:
                return True
        
    # 2. Cek PID sebagai fallback untuk dialog/jendela lain milik Python
    pid = ctypes.c_ulong()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value == os.getpid()

def _keyboard_hook(nCode, wParam, lParam):
    global _browser_instance, _app_instance
    try:
        if nCode >= 0 and _browser_instance and _app_instance:
            if wParam == 0x0100 or wParam == 0x0104: # WM_KEYDOWN or WM_SYSKEYDOWN
                if is_yuukaa_focused():
                    kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                    vk = kb.vkCode
                    
                    # Gunakan GetAsyncKeyState untuk akurasi maksimal di OS level
                    ctrl = (ctypes.windll.user32.GetAsyncKeyState(0x11) & 0x8000) != 0
                    
                    if ctrl:
                        if vk == 0x54: # T
                            with open('nav.log', 'a', encoding='utf-8') as f:
                                f.write("\n[HOOK] Ctrl+T triggered new_tab\n")
                            QTimer.singleShot(0, lambda: _browser_instance.new_tab(url=_browser_instance.get_home_url(), label="Homepage"))
                            return 1 # Suppress
                        elif vk == 0x57: # W
                            QTimer.singleShot(0, lambda: _browser_instance.close_tab(_browser_instance.tab_bar.currentIndex()))
                            return 1
                        elif vk == 0x52: # R
                            QTimer.singleShot(0, lambda: _browser_instance._cur_tab() and _browser_instance._cur_tab().reload())
                            return 1
                        elif 0x31 <= vk <= 0x39: # 1-9
                            idx = vk - 0x31
                            QTimer.singleShot(0, lambda: _browser_instance._switch_to_tab_index(idx))
                            return 1
                    
                    if vk == 0x1B: # ESC
                        if _browser_instance.isFullScreen():
                            QTimer.singleShot(0, lambda: _browser_instance._cur_tab() and hasattr(_browser_instance._cur_tab(), 'webview') and _browser_instance._cur_tab().webview.eval_js("document.exitFullscreen()"))
                            return 1 # Suppress
                            
    except Exception as e:
        pass
    
    return ctypes.windll.user32.CallNextHookEx(_global_hook_id, nCode, wParam, lParam)

def install_keyboard_hook(app, browser_instance):
    global _global_hook_proc, _global_hook_id, _browser_instance, _app_instance
    _browser_instance = browser_instance
    _app_instance = app
    
    # PERBAIKAN KRUSIAL: Mencegah Python 64-bit memotong pointer memori menjadi 32-bit
    ctypes.windll.kernel32.GetModuleHandleW.restype = ctypes.wintypes.HMODULE
    ctypes.windll.kernel32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
    
    ctypes.windll.user32.SetWindowsHookExW.restype = ctypes.wintypes.HHOOK
    ctypes.windll.user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, ctypes.wintypes.HINSTANCE, ctypes.wintypes.DWORD]
    
    ctypes.windll.user32.CallNextHookEx.restype = LRESULT
    ctypes.windll.user32.CallNextHookEx.argtypes = [ctypes.wintypes.HHOOK, ctypes.c_int, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM]
    
    _global_hook_proc = HOOKPROC(_keyboard_hook)
    h_mod = ctypes.windll.kernel32.GetModuleHandleW(None)
    _global_hook_id = ctypes.windll.user32.SetWindowsHookExW(13, _global_hook_proc, h_mod, 0) # WH_KEYBOARD_LL = 13

# ======================================
# ADBLOCK (domain-based)
# ======================================
def load_adblock_list():
    blocked = set()
    adblock_path = resource_path("adblock.txt")
    if os.path.exists(adblock_path):
        try:
            with open(adblock_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        parts = line.split()
                        if len(parts) >= 2 and parts[0] in ("0.0.0.0", "127.0.0.1"):
                            blocked.add(parts[1])
            print(f"AdBlocker: {len(blocked)} domain dimuat.")
        except Exception as e:
            print(f"Gagal load adblock: {e}")
    return blocked

BLOCKED_DOMAINS = load_adblock_list()

COSMETIC_JS = """
(function() {
    if (document.getElementById('yuukaa-adblock')) return;
    const style = document.createElement('style');
    style.id = 'yuukaa-adblock';
    style.textContent = `
        div[style*="z-index: 2147483647"],
        div[style*="z-index: 2147483646"],
        iframe[src*="exoclick"],
        iframe[src*="popads"],
        iframe[src*="highcpm"],
        [id*="popunder"],
        [class*="popunder"] {
            display: none !important;
            opacity: 0 !important;
            pointer-events: none !important;
            width: 0 !important;
            height: 0 !important;
        }
    `;
    if (document.head) {
        document.head.appendChild(style);
    } else {
        document.documentElement.appendChild(style);
    }
})();
"""

def _logging_fullscreen_handler(self, enter: bool):
    """
    PERBAIKAN FINAL FULLSCREEN:
    Jangan pernah me-reparent WebView2 ke jendela baru (itu merusak DirectX / Black Screen).
    Alih-alih, buat jendela utama (QMainWindow) menjadi Fullscreen, 
    lalu sembunyikan Tab Bar dan URL Bar agar video memenuhi seluruh layar!
    """
    try:
        main_win = None
        if hasattr(self, 'parent'):
            p = self.parent()
            while p:
                from PyQt6.QtWidgets import QMainWindow
                if isinstance(p, QMainWindow):
                    main_win = p
                    break
                p = p.parent()
                
        if not main_win:
            return
            
        from PyQt6.QtWidgets import QToolBar

        if enter:
            main_win._was_maximized = main_win.isMaximized()
            main_win.setUpdatesEnabled(False)
            try:
                main_win.showFullScreen()
                main_win.tab_bar.hide()
                for tb in main_win.findChildren(QToolBar):
                    tb.hide()
            finally:
                main_win.setUpdatesEnabled(True)
        else:
            main_win.setUpdatesEnabled(False)
            try:
                if getattr(main_win, '_was_maximized', False):
                    main_win.showMaximized()
                else:
                    main_win.showNormal()
                    
                main_win.tab_bar.show()
                for tb in main_win.findChildren(QToolBar):
                    tb.show()
            finally:
                main_win.setUpdatesEnabled(True)
                
        # Paksa resize webview agar ukurannya pas
        self._resize_webview()
        
    except Exception as e:
        import traceback
        with open('fullscreen.log', 'a', encoding='utf-8') as f:
            f.write(f"\nCRASHED in True Fullscreen: {e}\n{traceback.format_exc()}\n")

QtWebViewWidget._default_fullscreen_handler = _logging_fullscreen_handler


# ======================================
# DOWNLOAD MANAGER
# ======================================
DOWNLOAD_EXTENSIONS = (
    '.zip', '.rar', '.7z', '.tar', '.gz', '.xz', '.bz2',
    '.exe', '.msi', '.apk', '.dmg', '.pkg', '.deb', '.rpm',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv',
    '.mp3', '.wav', '.flac', '.aac', '.ogg',
    '.iso', '.img', '.bin', '.torrent'
)

class DownloadWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, url, cookies, save_path):
        super().__init__()
        self.url = url
        self.cookies = cookies
        self.save_path = save_path

    def run(self):
        try:
            req = urllib.request.Request(self.url, headers={"User-Agent": "YuukaaBrowser/12.0"})
            if self.cookies:
                cookie_str = "; ".join([f"{c.name}={c.value}" for c in self.cookies])
                req.add_header("Cookie", cookie_str)
            
            with urllib.request.urlopen(req, timeout=15) as res:
                filename = ""
                cd = res.headers.get("Content-Disposition", "")
                if "filename=" in cd:
                    parts = cd.split("filename=")
                    if len(parts) > 1:
                        filename = parts[1].split(";")[0].strip('"\'')
                
                if not filename:
                    parsed = urlparse(self.url)
                    filename = os.path.basename(parsed.path)
                    if not filename:
                        filename = "downloaded_file"
                
                final_path = os.path.join(self.save_path, filename)
                
                base, ext = os.path.splitext(final_path)
                counter = 1
                while os.path.exists(final_path):
                    final_path = f"{base} ({counter}){ext}"
                    counter += 1
                
                total_size = res.headers.get("Content-Length")
                total_size = int(total_size) if total_size else 0
                downloaded = 0
                
                with open(final_path, 'wb') as f:
                    while True:
                        chunk = res.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        mb_dl = downloaded / (1024 * 1024)
                        if total_size > 0:
                            pct = int((downloaded / total_size) * 100)
                            mb_tot = total_size / (1024 * 1024)
                            self.progress.emit(f"Downloading: {pct}% ({mb_dl:.1f}MB / {mb_tot:.1f}MB)")
                        else:
                            self.progress.emit(f"Downloading: {mb_dl:.1f}MB")
                            
                self.finished.emit(final_path)
        except Exception as e:
            self.error.emit(str(e))

# ======================================
# AUTO-SUGGEST WORKER
# ======================================
class SuggestWorker(QThread):
    suggestions_ready = pyqtSignal(list, list)
    
    def __init__(self, browser_window):
        super().__init__(browser_window)
        self.browser = browser_window
        self.query = ""
        self._lock = threading.Lock()
        
    def set_query(self, query):
        with self._lock:
            self.query = query
        
    def run(self):
        with self._lock:
            q = self.query.lower()
        if not q or not q.strip():
            self.suggestions_ready.emit([], [])
            return
            
        local_matches = []
        if hasattr(self.browser, 'bookmarks'):
            for b in self.browser.bookmarks:
                if q in b.get('title', '').lower() or q in b.get('url', '').lower():
                    local_matches.append(b)
                    if len(local_matches) >= 3:
                        break
                        
        url = f"https://duckduckgo.com/ac/?q={urllib.parse.quote(q)}&type=list"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        try:
            with urllib.request.urlopen(req, timeout=2) as response:
                import json
                data = json.loads(response.read().decode('utf-8'))
                if len(data) > 1 and isinstance(data[1], list):
                    self.suggestions_ready.emit(local_matches, data[1][:7])
        except:
            self.suggestions_ready.emit(local_matches, [])

# ======================================
# BROWSER TAB
# ======================================
class SafeQtWebViewWidget(QtWebViewWidget):
    """
    BUG FIX KEKAL (POISON BYPASS):
    qtwebview2 memiliki bug fatal di mana hideEvent akan memanggil w._webview.set_visible(False).
    Jika set_visible(False) dipanggil pada Wry (Edge), ia akan mati suri dan menolak klik 
    selamanya saat set_visible(True) dipanggil kembali (saat restore dari minimize).
    Kita mem-bypass fungsi hideEvent ini agar Wry tidak pernah diracuni!
    """
    def hideEvent(self, event):
        # Sengaja dilewatkan agar tidak memanggil super().hideEvent(event)
        pass

from PyQt6.QtWidgets import QLabel

class BrowserTab(QWidget):
    def __init__(self, url="", incognito=False, main_window=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.incognito = incognito
        self._pending_url = url
        self._current_url = ""
        self._title = "Memuat..."
        self.last_accessed = time.time()
        self.is_sleeping = False

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Placeholder for sleeping tab
        self.sleep_label = QLabel("😴 Tab Sedang Tidur\n(Klik untuk memuat ulang)")
        self.sleep_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sleep_label.setStyleSheet("color: gray; font-size: 18px;")
        self.sleep_label.hide()
        self.layout.addWidget(self.sleep_label)

        self._create_webview()

        # Poll timer: cek URL & title setiap 600ms
        self._timer = QTimer(self)
        self._timer.setInterval(600)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

    def _create_webview(self):
        self.webview = SafeQtWebViewWidget(incognito=self.incognito)
        if config.get("theme") == "dark":
            self.webview.set_background_color(43, 43, 43)
        else:
            self.webview.set_background_color(255, 255, 255)
            
        # Hubungkan signal judul asli dari halaman web
        if hasattr(self.webview, 'signals'):
            self.webview.signals.title_changed.connect(self._on_title_changed)
            
        self.layout.addWidget(self.webview)
        
        if hasattr(self, '_new_window_handler_set'):
            delattr(self, '_new_window_handler_set')

    def _on_title_changed(self, title):
        if not title:
            return
            
        # Potong judul jika terlalu panjang agar tab tidak melar
        if len(title) > 30:
            title = title[:27] + "..."
            
        self._title = title
        if self.main_window:
            idx = self.main_window.tab_layout.indexOf(self)
            if idx != -1:
                self.main_window._set_tab_title(idx, title, self)

    def sleep(self):
        if self.is_sleeping or not hasattr(self, 'webview'):
            return
        self.is_sleeping = True
        try:
            self.webview.eval_js("window.location.href = 'about:blank';")
        except:
            pass
        self.webview.hide()
        self.sleep_label.show()
        
    def wake_up(self):
        if not self.is_sleeping:
            return
        self.is_sleeping = False
        self.sleep_label.hide()
        self.webview.show()
        self.load(self._current_url or self._pending_url)

    def _do_pending_load(self):
        if self._pending_url:
            self._load_now(self._pending_url)
            self._pending_url = ""

    def _load_now(self, url):
        try:
            # BUG FIX: Menggunakan JS location.href untuk navigasi menghindari 
            # black screen crash pada fungsi load_url bawaan wryview.
            if self._current_url and self._current_url not in ("about:blank", ""):
                safe_url = url.replace("'", "\\'")
                self.webview.eval_js(f"window.location.href = '{safe_url}';")
            else:
                self.webview.load_url(url)
            self._current_url = url
        except Exception as e:
            print(f"load_url error: {e}")

    def load(self, url):
        if not url:
            return
        self._pending_url = ""
        self._load_now(url)

    def back(self):
        try: self.webview.eval_js("history.back()")
        except: pass

    def forward(self):
        try: self.webview.eval_js("history.forward()")
        except: pass

    def reload(self):
        try: self.webview.reload()
        except: pass

    def run_js(self, script):
        try: self.webview.eval_js(script)
        except Exception as e: print(f"JS err: {e}")

    def _poll(self):
        """Polling URL karena qtwebview2 rc5 belum expose Qt signals."""
        if self.is_sleeping:
            return
            
        if not hasattr(self, '_new_window_handler_set'):
            try:
                if hasattr(self, 'webview') and hasattr(self.webview, "_webview") and self.webview._webview:
                    def on_new_window(url):
                        if self.main_window:
                            QTimer.singleShot(0, lambda: self.main_window.new_tab(url=url))
                        return "deny"
                    self.webview._webview.set_on_new_window(on_new_window)
                    
                    def on_navigation(url):
                        if url.startswith("yuukaa-action://"):
                            if self.main_window:
                                QTimer.singleShot(0, lambda: self.main_window.handle_action(url))
                            return False
                        
                        lower_url = url.lower().split('?')[0]
                        if any(lower_url.endswith(ext) for ext in DOWNLOAD_EXTENSIONS):
                            if self.main_window:
                                # AVOID DEADLOCK: Jangan panggil cookies_for_url di dalam handler on_navigation!
                                QTimer.singleShot(0, lambda: self.main_window.start_download(url, self))
                                
                                # Auto-close jika ini tab baru yang kosong
                                if not self._current_url or self._current_url == "about:blank":
                                    def close_this_tab():
                                        if self.main_window:
                                            idx = self.main_window.tab_layout.indexOf(self)
                                            if idx != -1:
                                                self.main_window.close_tab(idx)
                                    QTimer.singleShot(100, close_this_tab)
                            return False # Block navigation, we are downloading it
                        return True
                    
                    if hasattr(self.webview._webview, "set_on_navigation"):
                        self.webview._webview.set_on_navigation(on_navigation)
                    
                    self._new_window_handler_set = True
                    
                    # LOAD URL SEKARANG, KARENA HANDLER SUDAH AKTIF!
                    if self._pending_url:
                        self._do_pending_load()
            except Exception as e:
                pass
                
        # OPTIMASI CPU: Kurangi frekuensi polling untuk tab di background
        is_active = False
        if self.main_window:
            is_active = (self.main_window.tab_layout.currentWidget() == self)
            
        if is_active:
            self._timer.setInterval(500)  # Cepat untuk tab aktif
        else:
            self._timer.setInterval(3000) # Lambat untuk menghemat CPU di background tab

        try:
            url_val = self.webview.url
            url_str = url_val() if callable(url_val) else url_val
        except:
            url_str = ""

        if url_str is None:
            url_str = ""
        else:
            url_str = str(url_str)

        # URL changed
        if url_str and url_str not in ("about:blank", "None", "") and url_str != self._current_url:
            self._current_url = url_str
            self._inject_adblock()
            
            # Set internal titles for local pages on navigation, otherwise use domain as placeholder
            if "settings.html" in url_str:
                self._title = "⚙️ Settings"
            elif "home.html" in url_str:
                self._title = "Homepage"
                    
            if self.main_window:
                idx = self.main_window.tab_layout.indexOf(self)
                if idx != -1: self.main_window._set_tab_title(idx, self._title, self)
                if idx == self.main_window.tab_bar.currentIndex():
                    self.main_window.update_url_bar_str(url_str)

    def _inject_adblock(self):
        dns_prov = config.get("dns", "none")
        custom_dns = config.get("customDns", "")
        is_adguard = (dns_prov == "adguard") or (dns_prov == "custom" and "adguard" in custom_dns.lower())
        if is_adguard:
            self.run_js(COSMETIC_JS)

    def url_str(self):
        return self._current_url

    def title_str(self):
        return self._title


# ======================================
# BOOKMARK DIALOG
# ======================================
class BookmarkDialog(QDialog):
    def __init__(self, parent, default_name="", default_folder="All Bookmarks", folders=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setFixedWidth(300)
        
        if folders is None:
            folders = ["All Bookmarks"]
        if "All Bookmarks" not in folders:
            folders.insert(0, "All Bookmarks")

        # Theming
        is_dark = getattr(parent, 'is_dark_mode', False) if parent else False
        bg_color = "#272727" if is_dark else "#ffffff"
        text_color = "#f3f4f6" if is_dark else "#111827"
        border_color = "#3f3f46" if is_dark else "#e5e7eb"
        input_bg = "#1e1e1e" if is_dark else "#f9fafb"
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 8px;
            }}
            QLabel {{
                color: {text_color};
                font-weight: bold;
            }}
            QLineEdit, QComboBox {{
                background-color: {input_bg};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 6px;
            }}
            QPushButton {{
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
            }}
            QPushButton#btnDone {{
                background-color: #f9a8d4; /* Pastel pink, matching user theme */
                color: #831843;
            }}
            QPushButton#btnRemove {{
                background-color: transparent;
                color: #ef4444;
            }}
            QPushButton#btnRemove:hover {{
                background-color: rgba(239, 68, 68, 0.1);
            }}
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        
        lbl_title = QLabel("Bookmark added")
        layout.addWidget(lbl_title)
        
        form_layout = QFormLayout()
        
        self.name_input = QLineEdit(default_name)
        form_layout.addRow("Name", self.name_input)
        
        self.folder_input = QComboBox()
        self.folder_input.setEditable(True)
        self.folder_input.addItems(folders)
        self.folder_input.setCurrentText(default_folder)
        form_layout.addRow("Folder", self.folder_input)
        
        layout.addLayout(form_layout)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_remove = QPushButton("Remove")
        btn_remove.setObjectName("btnRemove")
        btn_remove.clicked.connect(self.reject)
        
        btn_done = QPushButton("Done")
        btn_done.setObjectName("btnDone")
        btn_done.clicked.connect(self.accept)
        
        btn_layout.addWidget(btn_remove)
        btn_layout.addWidget(btn_done)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def get_data(self):
        return self.name_input.text(), self.folder_input.currentText()

# ======================================
# AUTO-SUGGEST UI CLASSES
# ======================================
class URLPopupList(QFrame):
    def __init__(self, parent_lineedit, browser_window):
        super().__init__(browser_window)
        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.parent_lineedit = parent_lineedit
        self.browser_window = browser_window
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.list_widget = QListWidget()
        self.list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        self.layout.addWidget(self.list_widget)
        
        self.setObjectName("urlPopupList")
        self.setStyleSheet("""
            QFrame#urlPopupList {
                background-color: #202124;
                border: 1px solid #5f6368;
                border-radius: 8px;
            }
            QListWidget {
                background-color: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                border: none;
                color: white;
            }
            QListWidget::item:selected {
                background-color: #3c4043;
                border-radius: 4px;
            }
            QLabel {
                background-color: transparent;
                border: none;
                color: white;
            }
        """)

    def update_suggestions(self, local_matches, google_suggestions):
        self.list_widget.clear()
        
        for b in local_matches:
            item = QListWidgetItem()
            w = QWidget()
            l = QHBoxLayout(w)
            l.setContentsMargins(10, 4, 10, 4)
            l.setSpacing(10)
            
            icon = QLabel("⭐")
            icon.setStyleSheet("color: #8ab4f8; font-size: 14px;")
            title = QLabel(f"<b>{b.get('title', '')}</b> - <span style='color:#8ab4f8'>{b.get('url', '').replace('https://', '').replace('http://', '')}</span>")
            title.setTextFormat(Qt.TextFormat.RichText)
            
            l.addWidget(icon)
            l.addWidget(title)
            l.addStretch()
            
            w.setFixedHeight(32)
            item.setSizeHint(w.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, b.get('url'))
            
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, w)
            
        for sugg in google_suggestions:
            item = QListWidgetItem()
            w = QWidget()
            l = QHBoxLayout(w)
            l.setContentsMargins(10, 4, 10, 4)
            l.setSpacing(10)
            
            icon = QLabel("🔍")
            icon.setStyleSheet("color: #9aa0a6; font-size: 14px;")
            title = QLabel(sugg)
            
            l.addWidget(icon)
            l.addWidget(title)
            l.addStretch()
            
            w.setFixedHeight(32)
            item.setSizeHint(w.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, sugg)
            
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, w)
            
        if self.list_widget.count() > 0:
            self.show_popup()
        else:
            self.hide()

    def show_popup(self):
        pos = self.parent_lineedit.mapToGlobal(QPoint(0, self.parent_lineedit.height() + 5))
        self.move(pos)
        self.setFixedWidth(self.parent_lineedit.width())
        h = min(400, self.list_widget.count() * 40 + 10)
        self.setFixedHeight(h)
        self.show()

    def on_item_clicked(self, item):
        url = item.data(Qt.ItemDataRole.UserRole)
        self.parent_lineedit.setText(url)
        self.browser_window.navigate_from_bar()
        self.hide()

class AddressBar(QLineEdit):
    def __init__(self, browser_window):
        super().__init__()
        self.browser = browser_window
        self.popup = URLPopupList(self, browser_window)
        self.textEdited.connect(self._on_text_edited)
        self._last_len = 0
        
    def _on_text_edited(self, text):
        is_backspace = len(text) < self._last_len
        self._last_len = len(text)
        
        if len(text.strip()) > 0:
            # Inline completion
            if not is_backspace and hasattr(self.browser, 'bookmarks'):
                for b in self.browser.bookmarks:
                    url = b.get('url', '').replace('https://', '').replace('http://', '').replace('www.', '').rstrip('/')
                    if url.lower().startswith(text.lower()) and len(url) > len(text):
                        self.setText(text + url[len(text):])
                        self.setSelection(len(text), len(url) - len(text))
                        break
                        
            self.browser.suggest_worker.set_query(text)
            self.browser.suggest_worker.start()
        else:
            self.popup.hide()
            
    def keyPressEvent(self, e):
        if self.popup.isVisible():
            if e.key() == Qt.Key.Key_Down:
                self.popup.list_widget.setCurrentRow((self.popup.list_widget.currentRow() + 1) % self.popup.list_widget.count())
                return
            elif e.key() == Qt.Key.Key_Up:
                row = self.popup.list_widget.currentRow() - 1
                if row < 0: row = self.popup.list_widget.count() - 1
                self.popup.list_widget.setCurrentRow(row)
                return
            elif e.key() == Qt.Key.Key_Enter or e.key() == Qt.Key.Key_Return:
                if self.popup.list_widget.currentRow() >= 0:
                    item = self.popup.list_widget.currentItem()
                    if item:
                        self.setText(item.data(Qt.ItemDataRole.UserRole))
                        self.popup.hide()
                        self.browser.navigate_from_bar()
                        return
        super().keyPressEvent(e)
        
    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        QTimer.singleShot(200, self.popup.hide)

# ======================================
# MAIN BROWSER WINDOW
# ======================================
class YuukaaBrowser(QMainWindow):
    def __init__(self, cfg):
        super().__init__()
        self.config = cfg
        self.setWindowTitle("Yuukaa Search V13")
        self.setGeometry(100, 100, 1280, 800)

        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.is_dark_mode = (cfg.get("theme") == "dark")
        self.search_engine = cfg.get("engine", "google")
        self._last_repaint_time = 0
        
        # ---- BOOKMARKS ----
        self.bookmarks_file = resource_path("bookmarks.json")
        self.bookmarks = []
        self._load_bookmarks()



        # ---- TABS (StackAll Architecture) ----
        self.tab_widgets = []
        self.tab_container = QWidget()
        self.tab_layout = QStackedLayout(self.tab_container)
        self.tab_layout.setStackingMode(QStackedLayout.StackingMode.StackAll)
        
        self.tab_bar = QTabBar()
        self.tab_bar.setDocumentMode(True)
        self.tab_bar.setTabsClosable(True)
        self.tab_bar.setMovable(True)
        self.tab_bar.setExpanding(False)
        self.tab_bar.tabCloseRequested.connect(self.close_tab)
        self.tab_bar.currentChanged.connect(self.on_tab_changed)
        # Disable scroll wheel on TabBar to prevent rapid switching/waking crashes
        self.tab_bar.wheelEvent = lambda event: event.ignore()
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.tab_bar)
        main_layout.addWidget(self.tab_container)
        
        central = QWidget()
        central.setLayout(main_layout)
        self.setCentralWidget(central)

        # ---- NAVBAR ----
        nav = QToolBar()
        nav.setMovable(False)
        self.addToolBar(nav)

        btn_back = QAction("<- Back", self)
        btn_back.setShortcut(QKeySequence("Alt+Left"))
        btn_back.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        btn_back.triggered.connect(lambda: self._cur_tab() and self._cur_tab().back())
        nav.addAction(btn_back)

        btn_fwd = QAction("Forward ->", self)
        btn_fwd.setShortcut(QKeySequence("Alt+Right"))
        btn_fwd.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        btn_fwd.triggered.connect(lambda: self._cur_tab() and self._cur_tab().forward())
        nav.addAction(btn_fwd)

        btn_reload = QAction("Reload", self)
        btn_reload.setShortcuts([QKeySequence("Ctrl+R"), QKeySequence("F5"), QKeySequence("Ctrl+Shift+R")])
        btn_reload.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        btn_reload.triggered.connect(lambda: self._cur_tab() and self._cur_tab().reload())
        nav.addAction(btn_reload)

        btn_new = QAction("+ New Tab", self)
        btn_new.setShortcut(QKeySequence("Ctrl+T"))
        btn_new.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        btn_new.triggered.connect(lambda: self.new_tab(url=self.get_home_url(), label="Homepage"))
        nav.addAction(btn_new)
        
        # Tab closing shortcut
        shortcut_close = QShortcut(QKeySequence("Ctrl+W"), self)
        shortcut_close.setContext(Qt.ShortcutContext.ApplicationShortcut)
        shortcut_close.activated.connect(lambda: self.close_tab(self.tab_bar.currentIndex()))
        
        # Tab switching shortcuts (Ctrl+1 to Ctrl+9)
        for i in range(1, 10):
            sc = QShortcut(QKeySequence(f"Ctrl+{i}"), self)
            sc.setContext(Qt.ShortcutContext.ApplicationShortcut)
            sc.activated.connect(lambda idx=i-1: self._switch_to_tab_index(idx))

        self.url_bar = AddressBar(self)
        self.url_bar.setPlaceholderText("Cari atau masukkan URL...")
        self.url_bar.returnPressed.connect(self.navigate_from_bar)
        nav.addWidget(self.url_bar)

        try:
            self.btn_bookmark = QAction("⭐", self)
            self.btn_bookmark.setToolTip("Tambahkan halaman ini ke Markah Buku")
            self.btn_bookmark.triggered.connect(self.toggle_current_bookmark)
            nav.addAction(self.btn_bookmark)
        except Exception as e:
            print("Bookmark init error:", e)
            
        # Worker for Auto-suggestions
        self.suggest_worker = SuggestWorker(self)
        self.suggest_worker.suggestions_ready.connect(self.on_suggestions_ready)
        # self.url_bar.textEdited is connected inside AddressBar class

        # ---- MENU ----
        menu = QMenu("Menu", self)

        a_settings = QAction("⚙️ Open Settings", self)
        a_settings.triggered.connect(self.open_settings)
        menu.addAction(a_settings)

        menu.addSeparator()

        a_incognito = QAction("🕵️ New Incognito Tab", self)
        a_incognito.triggered.connect(lambda: self.new_tab(url=self.get_home_url(), incognito=True, label="Homepage"))
        menu.addAction(a_incognito)

        a_clear = QAction("🧹 Hapus Cache", self)
        a_clear.triggered.connect(self.clear_data)
        menu.addAction(a_clear)

        a_devtools = QAction("🔧 DevTools", self)
        a_devtools.triggered.connect(lambda: self._cur_tab() and hasattr(self._cur_tab(), 'webview') and self._cur_tab().webview.open_devtools())
        menu.addAction(a_devtools)

        menu_btn = QToolButton()
        menu_btn.setText("⚙️ Menu")
        menu_btn.setMenu(menu)
        menu_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        nav.addWidget(menu_btn)

        self.apply_theme()

        # Memory Saver Timer (runs every 1 minute)
        self.memory_saver_timer = QTimer(self)
        self.memory_saver_timer.setInterval(60000)
        self.memory_saver_timer.timeout.connect(self._run_memory_saver)
        self.memory_saver_timer.start()

        # Home tab
        self.new_tab(url=self.get_home_url(), label="Homepage")

    def _run_memory_saver(self, force=False):
        # 5 minutes timeout by default
        timeout_seconds = 5 * 60 
        now = time.time()
        active_idx = self.tab_layout.currentIndex()
        
        tabs_to_sleep = []
        for i in range(self.tab_layout.count()):
            if i == active_idx:
                continue # Never sleep the active tab
                
            tab = self.tab_layout.widget(i)
            if isinstance(tab, BrowserTab):
                is_expired = (now - getattr(tab, 'last_accessed', now)) > timeout_seconds
                if not getattr(tab, 'is_sleeping', False) and (is_expired or force):
                    tabs_to_sleep.append(tab)
                    
        # Sleep them sequentially to prevent COM/WebView2 overload crash
        self._sleep_tabs_sequentially(tabs_to_sleep)

    def _sleep_tabs_sequentially(self, tabs):
        if not tabs:
            self._schedule_gc()
            return
        
        t = tabs.pop(0)
        if not getattr(t, 'is_sleeping', False):
            t.sleep()
            
        # Wait 150ms before sleeping the next tab to give Qt time to breathe
        QTimer.singleShot(150, lambda: self._sleep_tabs_sequentially(tabs))

    def _schedule_gc(self):
        if not hasattr(self, '_gc_timer'):
            self._gc_timer = QTimer(self)
            self._gc_timer.setSingleShot(True)
            self._gc_timer.timeout.connect(gc.collect)
        
        # Debounce GC to 1500ms
        self._gc_timer.start(1500)

    # ======================================
    # BOOKMARKS LOGIC
    # ======================================
    def _load_bookmarks(self):
        if os.path.exists(self.bookmarks_file):
            try:
                with open(self.bookmarks_file, 'r', encoding='utf-8') as f:
                    self.bookmarks = json.load(f)
            except Exception as e:
                print(f"Failed to load bookmarks: {e}")
                self.bookmarks = []
        else:
            self.bookmarks = []
            
        # Ensure JS file exists
        js_path = resource_path("bookmarks_data.js")
        if not os.path.exists(js_path):
            try:
                with open(js_path, 'w', encoding='utf-8') as f:
                    f.write(f"window.YUUKAA_BOOKMARKS = {json.dumps(self.bookmarks)};")
            except:
                pass

    def _save_bookmarks(self):
        try:
            with open(self.bookmarks_file, 'w', encoding='utf-8') as f:
                json.dump(self.bookmarks, f, indent=4)
            
            js_path = resource_path("bookmarks_data.js")
            with open(js_path, 'w', encoding='utf-8') as f:
                f.write(f"window.YUUKAA_BOOKMARKS = {json.dumps(self.bookmarks)};")
        except Exception as e:
            print(f"Failed to save bookmarks: {e}")

    def toggle_current_bookmark(self):
        tab = self._cur_tab()
        if not tab:
            return
            
        url = tab.url_str()
        if not url or url.startswith("file://") or url == "about:blank":
            return
            
        # Get unique folders
        folders = list(set([b.get('folder', 'All Bookmarks') for b in self.bookmarks]))
        
        # Check if already bookmarked
        existing = next((b for b in self.bookmarks if b.get('url') == url), None)
        default_name = existing.get('title', getattr(tab, '_title', url)) if existing else getattr(tab, '_title', url)
        default_folder = existing.get('folder', 'All Bookmarks') if existing else 'All Bookmarks'
        
        dialog = BookmarkDialog(self, default_name=default_name, default_folder=default_folder, folders=folders)
        
        # Position below the star button, right-aligned to the button
        widget = self.findChildren(QToolBar)[0].widgetForAction(self.btn_bookmark)
        if widget:
            pos = widget.mapToGlobal(QPoint(widget.width() - 300, widget.height() + 4))
            dialog.move(pos)
            
        result = dialog.exec()
        
        if result == QDialog.DialogCode.Accepted:
            # Done clicked
            name, folder = dialog.get_data()
            if existing:
                existing['title'] = name
                existing['folder'] = folder
            else:
                self.bookmarks.append({"title": name, "url": url, "folder": folder})
        elif result == QDialog.DialogCode.Rejected:
            # Remove clicked
            if existing:
                self.bookmarks.remove(existing)
            else:
                # If they cancelled adding a new bookmark, do nothing
                return
                
        self._save_bookmarks()
        self.update_url_bar_str(url) # This will update the star icon color

    def remove_bookmark(self, url):
        self.bookmarks = [b for b in self.bookmarks if b.get('url') != url]
        self._save_bookmarks()
        if self._cur_tab() and self._cur_tab().url_str() == url:
            self.update_url_bar_str(url)

    def get_home_url(self):
        import urllib.parse
        home_path = resource_path("home.html")
        url = QUrl.fromLocalFile(home_path)
        bg_path = self.config.get("bg_image", "")
        q = urllib.parse.urlencode({
            "theme": "dark" if self.is_dark_mode else "light",
            "bg": bg_path
        })
        url.setQuery(q)
        return url.toString()

    def _cur_tab(self):
        w = self.tab_layout.currentWidget()
        return w if isinstance(w, BrowserTab) else None

    def _switch_to_tab_index(self, idx):
        if 0 <= idx < self.tab_bar.count():
            self.tab_bar.setCurrentIndex(idx)

    def new_tab(self, url=None, label="New Tab", incognito=False):
        try:
            if url is None:
                url = self.get_home_url()
                label = "Homepage"
            tab = BrowserTab(url=url, incognito=incognito, main_window=self, parent=self)
            if incognito and not label.startswith("🕵️"):
                label = "🕵️ " + label
            i = self.tab_bar.addTab(label)
            self.tab_layout.addWidget(tab)
            self.tab_bar.setCurrentIndex(i)
            self.url_bar.clearFocus()
            if hasattr(tab, 'webview'):
                tab.webview.raise_()
            return tab
        except Exception as e:
            import traceback
            with open("newtab_crash.log", "w") as f:
                f.write(traceback.format_exc())
            return None

    def open_settings(self):
        settings_path = resource_path("settings.html")
        dns = self.config.get("dns", "none")
        custom_dns = self.config.get("customDns", "")
        dl_path = self.config.get("download_path", os.path.join(os.path.expanduser("~"), "Downloads"))
        from urllib.parse import urlencode
        q = urlencode({
            "theme": "dark", 
            "engine": self.search_engine, 
            "dns": dns, 
            "customDns": custom_dns,
            "dl_path": dl_path
        })
        url = QUrl.fromLocalFile(settings_path)
        url.setQuery(q)
        tab = self.new_tab(url=url.toString(), label="⚙️ Settings")

    def close_tab(self, i):
        if self.tab_bar.count() < 2:
            return
        widget = self.tab_layout.widget(i)
        self.tab_bar.removeTab(i)
        if isinstance(widget, BrowserTab):
            try:
                # Navigasi ke about:blank untuk menghentikan pemutaran audio/video di background
                widget.webview.eval_js("window.location.href = 'about:blank';")
            except:
                pass
            self.tab_layout.removeWidget(widget)
            widget.webview.setParent(None) # Detach from UI tree immediately
            widget.deleteLater()
            # OPTIMASI RAM: Paksa pembersihan memori secara aman (debounced)
            self._schedule_gc()

    def on_tab_changed(self, i):
        self.tab_layout.setCurrentIndex(i)
        tab = self.tab_layout.widget(i)
        if isinstance(tab, BrowserTab):
            tab.last_accessed = time.time()
            if getattr(tab, 'is_sleeping', False):
                tab.wake_up()
                
            self.update_url_bar_str(tab.url_str())
            
            # Update window title to match the currently selected tab
            title = tab.title_str()
            if not title or title == "None":
                title = "Homepage"
            self.setWindowTitle(f"{title} - Yuukaa Search V13")
            
            self.url_bar.clearFocus()
            if hasattr(tab, 'webview'):
                tab.webview.raise_()
                tab.webview.setFocus()

    def update_url_bar_str(self, url_str):
        if not url_str or "home.html" in url_str:
            self.url_bar.setText("")
        elif "settings.html" in url_str:
            self.url_bar.setText("yuukaa://settings")
        else:
            self.url_bar.setText(url_str)
            self.url_bar.setCursorPosition(0)
            
        # Cek status bookmark
        if hasattr(self, 'btn_bookmark'):
            is_bookmarked = any(b.get('url') == url_str for b in self.bookmarks)
            self.btn_bookmark.setText("🌟" if is_bookmarked else "⭐")

    def _set_tab_title(self, idx, title, tab):
        if title == "Yuukaa Settings" or title == "⚙️ Settings":
            display = "⚙️ Settings"
        elif title == "Yuukaa Home" or title == "Homepage":
            display = "Homepage"
        elif len(title) > 22:
            display = title[:19] + "..."
        else:
            display = title
            
        if tab.incognito and not display.startswith("🕵️"):
            display = "🕵️ " + display
            
        self.tab_bar.setTabText(idx, display)
        if self.tab_bar.currentIndex() == idx:
            self.setWindowTitle(f"{title} - Yuukaa Search V13")

    def start_download(self, url, tab):
        cookies = []
        try:
            if tab and hasattr(tab, 'webview') and hasattr(tab.webview, '_webview'):
                cookies = tab.webview._webview.cookies_for_url(url)
        except Exception as e:
            print(f"Failed to get cookies: {e}")
            
        dl_path = self.config.get("download_path", os.path.join(os.path.expanduser("~"), "Downloads"))
        if not os.path.exists(dl_path):
            os.makedirs(dl_path, exist_ok=True)
            
        worker = DownloadWorker(url, cookies, dl_path)
        # Tangkap event progress untuk menampilkan di title bar window
        def update_progress(msg):
            self.setWindowTitle(f"[ {msg} ] - Yuukaa Search V13")
            
        def on_finished(final_path):
            self.setWindowTitle("Download Selesai! - Yuukaa Search V13")
            QTimer.singleShot(3000, lambda: self.setWindowTitle("Yuukaa Search V13"))
            
        def on_error(err):
            print("Download Error:", err)
            self.setWindowTitle("Download Gagal! - Yuukaa Search V13")
            QTimer.singleShot(3000, lambda: self.setWindowTitle("Yuukaa Search V13"))
            
        worker.progress.connect(update_progress)
        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        
        # Simpan referensi agar tidak di-garbage collect
        if not hasattr(self, '_dl_workers'):
            self._dl_workers = []
        self._dl_workers.append(worker)
        worker.finished.connect(lambda p: self._dl_workers.remove(worker) if worker in self._dl_workers else None)
        worker.error.connect(lambda e: self._dl_workers.remove(worker) if worker in self._dl_workers else None)
        
        worker.start()

    def handle_action(self, url):
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(url)
        action = parsed.netloc or parsed.path.strip("/")
        qs = parse_qs(parsed.query)
        
        if action == "save-settings":
            engine = qs.get("engine", ["google"])[0]
            dns = qs.get("dns", ["none"])[0]
            custom_dns = qs.get("customDns", [""])[0]
            
            self.config["engine"] = engine
            self.config["dns"] = dns
            self.config["customDns"] = custom_dns
            self.search_engine = engine
            save_config(self.config)
            
            # Reload tab
            tab = self._cur_tab()
            if tab:
                tab.reload()
                
        elif action == "edit-bookmark":
            url_to_edit = qs.get("url", [""])[0]
            name = qs.get("name", [""])[0]
            folder = qs.get("folder", ["All Bookmarks"])[0]
            
            for b in self.bookmarks:
                if b.get('url') == url_to_edit:
                    b['title'] = name
                    b['folder'] = folder
                    break
                    
            self._save_bookmarks()
            tab = self._cur_tab()
            if tab:
                tab.reload()
                
        elif action == "delete-bookmark":
            url_to_del = qs.get("url", [""])[0]
            self.remove_bookmark(url_to_del)
            tab = self._cur_tab()
            if tab:
                tab.reload()
                
        elif action == "select-download-dir":
            from PyQt6.QtWidgets import QFileDialog
            dl_path = self.config.get("download_path", os.path.join(os.path.expanduser("~"), "Downloads"))
            new_path = QFileDialog.getExistingDirectory(self, "Pilih Folder Download", dl_path)
            if new_path:
                self.config["download_path"] = new_path
                save_config(self.config)
                # Reload settings tab with new path
                tab = self._cur_tab()
                if tab and "settings.html" in tab.url_str():
                    import urllib.parse
                    from PyQt6.QtCore import QUrl
                    settings_path = resource_path("settings.html")
                    q = urllib.parse.urlencode({
                        "theme": "dark",
                        "engine": self.search_engine,
                        "dns": self.config.get("dns", "none"),
                        "customDns": self.config.get("customDns", ""),
                        "dl_path": new_path
                    })
                    u = QUrl.fromLocalFile(settings_path)
                    u.setQuery(q)
                    tab.load(u.toString())
                    
        elif action == "clear-history":
            self.clear_data()
            
        elif action == "new_incognito":
            self.new_tab(url="yuukaa://home", incognito=True)
            
        elif action == "flush_ram":
            # Force all inactive tabs to sleep and flush GC
            self._run_memory_saver(force=True)
            
        elif action == "upload-bg":
            from PyQt6.QtWidgets import QFileDialog
            img_path, _ = QFileDialog.getOpenFileName(self, "Pilih Foto Background", "", "Images (*.png *.jpg *.jpeg *.webp)")
            if img_path:
                self.config["bg_image"] = img_path
                save_config(self.config)
                # Reload all home tabs to apply changes
                for i in range(self.tab_layout.count()):
                    w = self.tab_layout.widget(i)
                    if isinstance(w, BrowserTab) and "home.html" in w.url_str():
                        w.load(self.get_home_url())
                
                # Show notification in settings tab
                tab = self._cur_tab()
                if tab and "settings.html" in tab.url_str():
                    tab.run_js("showNotification('Background berhasil diunggah!');")
                        
        elif action == "remove-bg":
            self.config["bg_image"] = ""
            save_config(self.config)
            # Reload all home tabs to apply changes
            for i in range(self.tab_layout.count()):
                w = self.tab_layout.widget(i)
                if isinstance(w, BrowserTab) and "home.html" in w.url_str():
                    w.load(self.get_home_url())
                    
            # Show notification in settings tab
            tab = self._cur_tab()
            if tab and "settings.html" in tab.url_str():
                tab.run_js("showNotification('Background berhasil dihapus!');")

    def on_url_text_edited(self, text):
        if len(text.strip()) > 0:
            self.suggest_worker.set_query(text)
            self.suggest_worker.start()
            
    def on_suggestions_ready(self, local_matches, google_suggestions):
        self.url_bar.popup.update_suggestions(local_matches, google_suggestions)

    def navigate_from_bar(self):
        text = self.url_bar.text().strip()
        if not text:
            return

        if text == "yuukaa://settings":
            self.open_settings()
            return

        is_url = False
        url = ""
        
        if text.startswith("http://") or text.startswith("https://") or text.startswith("yuukaa://"):
            is_url = True
            url = text
        elif text.startswith("localhost") or text.startswith("127.0.0.1"):
            is_url = True
            url = "http://" + text
        elif " " not in text and "." in text:
            is_url = True
            url = "https://" + text
            
        if not is_url:
            eng = self.search_engine
            q = urllib.parse.quote_plus(text)
            if eng == "bing":
                url = f"https://www.bing.com/search?q={q}"
            elif eng == "duckduckgo":
                url = f"https://duckduckgo.com/?q={q}"
            else:
                url = f"https://www.google.com/search?q={q}"

        tab = self._cur_tab()
        if tab:
            tab.load(url)
            self.url_bar.clearFocus()
            tab.webview.raise_()

    def clear_data(self):
        tab = self._cur_tab()
        if tab:
            try:
                tab.webview.clear_all_browsing_data()
            except Exception as e:
                print(f"clear data error: {e}")

    def apply_theme(self):
        if self.is_dark_mode:
            self.setStyleSheet("""
                QMainWindow { background-color: #2b2b2b; }
                QToolBar { background-color: #1e1e1e; border: none; padding: 5px; }
                QToolButton { color: #ffffff; background: transparent; padding: 5px; font-weight: bold; }
                QToolButton:hover { background-color: #383838; border-radius: 4px; }
                QLineEdit {
                    background-color: #383838; color: #ffffff;
                    border-radius: 12px; padding: 6px 15px;
                    font-size: 14px; margin: 0px 10px; border: 1px solid #4a4a4a;
                }
                QLineEdit:focus { border: 1px solid #7c4dff; }
                QTabWidget::pane { border: none; }
                QTabBar::tab {
                    background: #2b2b2b; color: #aaaaaa;
                    padding: 8px 15px; border-top-left-radius: 8px; border-top-right-radius: 8px;
                    margin-right: 2px;
                }
                QTabBar::tab:selected { background: #383838; color: #ffffff; font-weight: bold; }
                QTabBar::tab:hover { background: #383838; }
            """)
        else:
            self.setStyleSheet("""
                QMainWindow { background-color: #f0f0f0; }
                QToolBar { background-color: #e0e0e0; border: none; padding: 5px; }
                QToolButton { color: #000000; background: transparent; padding: 5px; font-weight: bold; }
                QToolButton:hover { background-color: #d0d0d0; border-radius: 4px; }
                QLineEdit {
                    background-color: #ffffff; color: #000000;
                    border-radius: 12px; padding: 6px 15px;
                    font-size: 14px; margin: 0px 10px; border: 1px solid #cccccc;
                }
                QLineEdit:focus { border: 1px solid #7c4dff; }
                QTabWidget::pane { border: none; }
                QTabBar::tab {
                    background: #e0e0e0; color: #555555;
                    padding: 8px 15px; border-top-left-radius: 8px; border-top-right-radius: 8px;
                    margin-right: 2px;
                }
                QTabBar::tab:selected { background: #ffffff; color: #000000; font-weight: bold; }
                QTabBar::tab:hover { background: #ffffff; }
            """)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = YuukaaBrowser(config)
    install_keyboard_hook(app, window)
    window.show()
    
    ret = app.exec()
    if _global_hook_id:
        ctypes.windll.user32.UnhookWindowsHookEx(_global_hook_id)
        
    sys.exit(ret)
