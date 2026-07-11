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
from PyQt6.QtCore import QUrl, Qt, QTimer, QEvent, QThread, pyqtSignal, QStringListModel
from PyQt6.QtWidgets import (QApplication, QMainWindow, QLineEdit,
                             QToolBar, QTabBar, QStackedLayout, QWidget, QVBoxLayout, QMenu, QToolButton, QFileDialog, QCompleter)
from PyQt6.QtGui import QAction, QIcon, QKeySequence, QShortcut
from qtwebview2 import QtWebViewWidget
import urllib.request
import urllib.error
from urllib.parse import urlparse
import threading
import gc
import time

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

# BUG FIX KEKAL UNTUK FULLSCREEN/MINIMIZE BLACK SCREEN:
# qtwebview2 memiliki bug fatal di Windows dimana ia melakukan reparenting native HWND 
# ke jendela baru saat video masuk mode fullscreen. Ini merusak DirectComposition DirectX.
# Dengan menonaktifkan fungsi ini, video akan membesar 100% mengikuti ukuran tab (Theater Mode)
# tanpa pernah merusak atau memisahkan native window.
def _safe_fullscreen_handler(self, enter: bool):
    # Biarkan WebView2 menangani fullscreen secara internal di dalam batas widget.
    # Jika webview tidak merespons, trigger resize paksa.
    from PyQt6.QtGui import QResizeEvent
    from PyQt6.QtCore import QSize
    from PyQt6.QtWidgets import QApplication
    try:
        old_size = self.size()
        fake_size = QSize(old_size.width(), old_size.height() - 1)
        QApplication.sendEvent(self, QResizeEvent(fake_size, old_size))
        QApplication.sendEvent(self, QResizeEvent(old_size, fake_size))
        self.eval_js("window.dispatchEvent(new Event('resize'))")
    except: pass

QtWebViewWidget._default_fullscreen_handler = _safe_fullscreen_handler


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
    suggestions_ready = pyqtSignal(list)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.query = ""
        self._lock = threading.Lock()
        
    def set_query(self, query):
        with self._lock:
            self.query = query
        
    def run(self):
        with self._lock:
            q = self.query
        if not q or not q.strip():
            self.suggestions_ready.emit([])
            return
            
        url = f"http://suggestqueries.google.com/complete/search?client=chrome&q={urllib.parse.quote(q)}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'})
        try:
            with urllib.request.urlopen(req, timeout=2) as response:
                import json
                data = json.loads(response.read().decode('utf-8'))
                if len(data) > 1 and isinstance(data[1], list):
                    self.suggestions_ready.emit(data[1][:10]) # Limit to 10 suggestions
        except Exception as e:
            pass # Ignore network errors silently

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
        self.layout.addWidget(self.webview)
        
        if hasattr(self, '_new_window_handler_set'):
            delattr(self, '_new_window_handler_set')

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

        # Karena eval_js di wry tidak me-return nilai secara sinkron, kita buat judul dari URL
        title_str = ""
        if url_str and not url_str.startswith("file://") and url_str != "about:blank":
            from urllib.parse import urlparse
            parsed = urlparse(url_str)
            title_str = parsed.netloc.replace("www.", "") if parsed.netloc else "Website"
            if parsed.path and len(parsed.path) > 1:
                # Tambahkan sedikit path agar kelihatan navigasi berubah
                path_part = parsed.path.strip("/")
                if len(path_part) > 10:
                    path_part = path_part[:10] + "..."
                title_str = f"{title_str} - {path_part}"
        elif "settings.html" in url_str:
            title_str = "⚙️ Settings"
        elif "home.html" in url_str:
            title_str = "Homepage"

        # URL changed
        if url_str and url_str not in ("about:blank", "None", "") and url_str != self._current_url:
            self._current_url = url_str
            self._inject_adblock()
            if self.main_window:
                idx = self.main_window.tab_layout.indexOf(self)
                if idx == self.main_window.tab_bar.currentIndex():
                    self.main_window.update_url_bar_str(url_str)

        # Title changed
        if title_str and title_str != self._title:
            self._title = title_str
            if self.main_window:
                idx = self.main_window.tab_layout.indexOf(self)
                if idx != -1:
                    self.main_window._set_tab_title(idx, title_str, self)

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
# MAIN BROWSER WINDOW
# ======================================
class YuukaaBrowser(QMainWindow):
    def __init__(self, cfg):
        super().__init__()
        self.config = cfg
        self.setWindowTitle("Yuukaa Search V12")
        self.setGeometry(100, 100, 1280, 800)

        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.is_dark_mode = (cfg.get("theme") == "dark")
        self.search_engine = cfg.get("engine", "google")
        self._last_repaint_time = 0

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
        btn_back.triggered.connect(lambda: self._cur_tab() and self._cur_tab().back())
        nav.addAction(btn_back)

        btn_fwd = QAction("Forward ->", self)
        btn_fwd.setShortcut(QKeySequence("Alt+Right"))
        btn_fwd.triggered.connect(lambda: self._cur_tab() and self._cur_tab().forward())
        nav.addAction(btn_fwd)

        btn_reload = QAction("Reload", self)
        btn_reload.setShortcuts([QKeySequence("Ctrl+R"), QKeySequence("F5"), QKeySequence("Ctrl+Shift+R")])
        btn_reload.triggered.connect(lambda: self._cur_tab() and self._cur_tab().reload())
        nav.addAction(btn_reload)

        btn_new = QAction("+ New Tab", self)
        btn_new.setShortcut(QKeySequence("Ctrl+T"))
        btn_new.triggered.connect(lambda: self.new_tab(url=self.get_home_url(), label="Homepage"))
        nav.addAction(btn_new)
        
        # Tab closing shortcut
        shortcut_close = QShortcut(QKeySequence("Ctrl+W"), self)
        shortcut_close.activated.connect(lambda: self.close_tab(self.tab_bar.currentIndex()))

        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Cari atau masukkan URL...")
        self.url_bar.returnPressed.connect(self.navigate_from_bar)
        nav.addWidget(self.url_bar)

        # Completer for Auto-suggestions
        self.url_completer_model = QStringListModel()
        self.url_completer = QCompleter(self.url_completer_model, self)
        self.url_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.url_bar.setCompleter(self.url_completer)
        
        # Worker for Auto-suggestions
        self.suggest_worker = SuggestWorker(self)
        self.suggest_worker.suggestions_ready.connect(self.on_suggestions_ready)
        self.url_bar.textEdited.connect(self.on_url_text_edited)

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

    def new_tab(self, url=None, label="New Tab", incognito=False):
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
        tab.webview.raise_()
        return tab

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
            self.setWindowTitle(f"{title} - Yuukaa Search V12")
            
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

    def _set_tab_title(self, idx, title, tab):
        if "settings.html" in tab.url_str():
            display = "⚙️ Settings"
        elif len(title) > 22:
            display = title[:19] + "..."
        else:
            display = title
        if tab.incognito and not display.startswith("🕵️"):
            display = "🕵️ " + display
        self.tab_bar.setTabText(idx, display)
        if self.tab_bar.currentIndex() == idx:
            self.setWindowTitle(f"{title} - Yuukaa Search V12")

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
            self.setWindowTitle(f"[ {msg} ] - Yuukaa Search V12")
            
        def on_finished(final_path):
            self.setWindowTitle("Download Selesai! - Yuukaa Search V12")
            QTimer.singleShot(3000, lambda: self.setWindowTitle("Yuukaa Search V12"))
            
        def on_error(err):
            print("Download Error:", err)
            self.setWindowTitle("Download Gagal! - Yuukaa Search V12")
            QTimer.singleShot(3000, lambda: self.setWindowTitle("Yuukaa Search V12"))
            
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
            
    def on_suggestions_ready(self, suggestions):
        # Update model without closing the popup
        self.url_completer_model.setStringList(suggestions)

    def navigate_from_bar(self):
        text = self.url_bar.text().strip()
        if not text:
            return

        if text == "yuukaa://settings":
            self.open_settings()
            return

        if " " in text or "." not in text:
            eng = self.search_engine
            q = text.replace(" ", "+")
            if eng == "bing":
                url = f"https://www.bing.com/search?q={q}"
            elif eng == "duckduckgo":
                url = f"https://duckduckgo.com/?q={q}"
            else:
                url = f"https://www.google.com/search?q={q}"
        else:
            url = text if text.startswith("http") else "https://" + text

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
    window.show()
    sys.exit(app.exec())
