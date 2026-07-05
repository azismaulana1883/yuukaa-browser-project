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
from PyQt6.QtCore import QUrl, Qt, QTimer, QEvent
from PyQt6.QtWidgets import (QApplication, QMainWindow, QLineEdit,
                             QToolBar, QTabBar, QStackedLayout, QWidget, QVBoxLayout, QMenu, QToolButton)
from PyQt6.QtGui import QAction, QIcon
from qtwebview2 import QtWebViewWidget

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

class BrowserTab(QWidget):
    def __init__(self, url="", incognito=False, main_window=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.incognito = incognito
        self._pending_url = url
        self._current_url = ""
        self._title = "Memuat..."

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.webview = SafeQtWebViewWidget(incognito=self.incognito)
        if config.get("theme") == "dark":
            self.webview.set_background_color(43, 43, 43)
        else:
            self.webview.set_background_color(255, 255, 255)
        layout.addWidget(self.webview)

        # Poll timer: cek URL & title setiap 600ms
        self._timer = QTimer(self)
        self._timer.setInterval(600)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

        # Load setelah widget siap
        if url:
            QTimer.singleShot(500, self._do_pending_load)

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
        if not hasattr(self, '_new_window_handler_set'):
            try:
                if hasattr(self.webview, "_webview") and self.webview._webview:
                    def on_new_window(url):
                        if self.main_window:
                            # Gunakan QTimer agar eksekusi new_tab berjalan di main thread UI secara aman
                            QTimer.singleShot(0, lambda: self.main_window.new_tab(url=url))
                        return "deny" # Wry expects "allow" or "deny" string to prevent default window
                    self.webview._webview.set_on_new_window(on_new_window)
                    self._new_window_handler_set = True
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
            url_str = url_val() if callable(url_val) else str(url_val)
        except:
            url_str = ""

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
        self.setWindowTitle("Yuukaa Search V11")
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
        btn_back.triggered.connect(lambda: self._cur_tab() and self._cur_tab().back())
        nav.addAction(btn_back)

        btn_fwd = QAction("Forward ->", self)
        btn_fwd.triggered.connect(lambda: self._cur_tab() and self._cur_tab().forward())
        nav.addAction(btn_fwd)

        btn_reload = QAction("Reload", self)
        btn_reload.triggered.connect(lambda: self._cur_tab() and self._cur_tab().reload())
        nav.addAction(btn_reload)

        btn_new = QAction("+ New Tab", self)
        btn_new.triggered.connect(lambda: self.new_tab())
        nav.addAction(btn_new)

        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Cari atau masukkan URL...")
        self.url_bar.returnPressed.connect(self.navigate_from_bar)
        nav.addWidget(self.url_bar)

        # ---- MENU ----
        menu = QMenu("Menu", self)

        a_settings = QAction("⚙️ Open Settings", self)
        a_settings.triggered.connect(self.open_settings)
        menu.addAction(a_settings)

        menu.addSeparator()

        a_incognito = QAction("🕵️ New Incognito Tab", self)
        a_incognito.triggered.connect(lambda: self.new_tab(url="yuukaa://home", incognito=True))
        menu.addAction(a_incognito)

        a_clear = QAction("🧹 Hapus Cache", self)
        a_clear.triggered.connect(self.clear_data)
        menu.addAction(a_clear)

        a_devtools = QAction("🔧 DevTools", self)
        a_devtools.triggered.connect(lambda: self._cur_tab() and self._cur_tab().webview.open_devtools())
        menu.addAction(a_devtools)

        menu_btn = QToolButton()
        menu_btn.setText("⚙️ Menu")
        menu_btn.setMenu(menu)
        menu_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        nav.addWidget(menu_btn)

        self.apply_theme()

        # Home tab
        home_path = resource_path("home.html")
        url = QUrl.fromLocalFile(home_path)
        url.setQuery("theme=dark")
        self.new_tab(url=url.toString(), label="Homepage")

    def _cur_tab(self):
        w = self.tab_layout.currentWidget()
        return w if isinstance(w, BrowserTab) else None

    def new_tab(self, url="", label="New Tab", incognito=False):
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
        from urllib.parse import urlencode
        q = urlencode({"theme": "dark", "engine": self.search_engine, "dns": dns, "customDns": custom_dns})
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
            widget.deleteLater()
            # OPTIMASI RAM: Paksa pembersihan memori sisa tab dari Python RAM
            gc.collect()

    def on_tab_changed(self, i):
        self.tab_layout.setCurrentIndex(i)
        tab = self.tab_layout.widget(i)
        if isinstance(tab, BrowserTab):
            self.update_url_bar_str(tab.url_str())
            self.url_bar.clearFocus()
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
            self.setWindowTitle(f"{title} - Yuukaa Search V10")

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
