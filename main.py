import sys
import os
import json
import gc
import time
import urllib.parse
from urllib.parse import urlparse, parse_qs
from PyQt6.QtCore import QUrl, Qt, QTimer, QPoint
from PyQt6.QtWidgets import (QApplication, QMainWindow, QToolBar, QTabBar, QStackedLayout,
                             QWidget, QVBoxLayout, QMenu, QToolButton, QFileDialog, QDialog)
from PyQt6.QtGui import QAction, QIcon, QKeySequence, QShortcut

from utility.utils import (resource_path, load_config, save_config, 
                   install_keyboard_hook, uninstall_keyboard_hook, _global_hook_id)
from utility.workers import DownloadWorker, SuggestWorker
from utility.ui_components import BrowserTab, BookmarkDialog, AddressBar

config = load_config()

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
            tab = BrowserTab(url=url, incognito=incognito, main_window=self, parent=self, config=self.config)
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
        
        q = urllib.parse.urlencode({
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
                widget.webview.eval_js("window.location.href = 'about:blank';")
            except:
                pass
            self.tab_layout.removeWidget(widget)
            widget.webview.setParent(None)
            widget.deleteLater()
            self._schedule_gc()

    def on_tab_changed(self, i):
        self.tab_layout.setCurrentIndex(i)
        tab = self.tab_layout.widget(i)
        if isinstance(tab, BrowserTab):
            tab.last_accessed = time.time()
            if getattr(tab, 'is_sleeping', False):
                tab.wake_up()
                
            self.update_url_bar_str(tab.url_str())
            
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
        
        if not hasattr(self, '_dl_workers'):
            self._dl_workers = []
        self._dl_workers.append(worker)
        worker.finished.connect(lambda p: self._dl_workers.remove(worker) if worker in self._dl_workers else None)
        worker.error.connect(lambda e: self._dl_workers.remove(worker) if worker in self._dl_workers else None)
        
        worker.start()

    def handle_action(self, url):
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
            dl_path = self.config.get("download_path", os.path.join(os.path.expanduser("~"), "Downloads"))
            new_path = QFileDialog.getExistingDirectory(self, "Pilih Folder Download", dl_path)
            if new_path:
                self.config["download_path"] = new_path
                save_config(self.config)
                
                tab = self._cur_tab()
                if tab and "settings.html" in tab.url_str():
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
            self._run_memory_saver(force=True)
            
        elif action == "upload-bg":
            img_path, _ = QFileDialog.getOpenFileName(self, "Pilih Foto Background", "", "Images (*.png *.jpg *.jpeg *.webp)")
            if img_path:
                self.config["bg_image"] = img_path
                save_config(self.config)
                for i in range(self.tab_layout.count()):
                    w = self.tab_layout.widget(i)
                    if isinstance(w, BrowserTab) and "home.html" in w.url_str():
                        w.load(self.get_home_url())
                
                tab = self._cur_tab()
                if tab and "settings.html" in tab.url_str():
                    tab.run_js("showNotification('Background berhasil diunggah!');")
                        
        elif action == "remove-bg":
            self.config["bg_image"] = ""
            save_config(self.config)
            for i in range(self.tab_layout.count()):
                w = self.tab_layout.widget(i)
                if isinstance(w, BrowserTab) and "home.html" in w.url_str():
                    w.load(self.get_home_url())
                    
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
    # Fix Taskbar Icon on Windows
    try:
        import ctypes
        myappid = 'yuukaa.browser.search.v13'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass
        
    app = QApplication(sys.argv)
    window = YuukaaBrowser(config)
    install_keyboard_hook(app, window)
    window.show()
    
    ret = app.exec()
    uninstall_keyboard_hook()
    sys.exit(ret)
