import time
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QDialog,
                             QFormLayout, QLineEdit, QComboBox, QPushButton,
                             QListWidget, QListWidgetItem, QFrame)
from qtwebview2 import QtWebViewWidget
from utility.utils import COSMETIC_JS

# We import DOWNLOAD_EXTENSIONS from workers to avoid circular imports if possible
from utility.workers import DOWNLOAD_EXTENSIONS

# ======================================
# BROWSER TAB & WEBVIEW
# ======================================
def _logging_fullscreen_handler(self, enter: bool):
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
                
        self._resize_webview()
        
    except Exception as e:
        import traceback
        with open('fullscreen.log', 'a', encoding='utf-8') as f:
            f.write(f"\nCRASHED in True Fullscreen: {e}\n{traceback.format_exc()}\n")

class SafeQtWebViewWidget(QtWebViewWidget):
    def hideEvent(self, event):
        pass

SafeQtWebViewWidget._default_fullscreen_handler = _logging_fullscreen_handler


class BrowserTab(QWidget):
    def __init__(self, url="", incognito=False, main_window=None, parent=None, config=None):
        super().__init__(parent)
        self.main_window = main_window
        self.incognito = incognito
        self._pending_url = url
        self._current_url = ""
        self._title = "Memuat..."
        self.last_accessed = time.time()
        self.is_sleeping = False
        self.config = config or {}

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.sleep_label = QLabel("😴 Tab Sedang Tidur\n(Klik untuk memuat ulang)")
        self.sleep_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sleep_label.setStyleSheet("color: gray; font-size: 18px;")
        self.sleep_label.hide()
        self.layout.addWidget(self.sleep_label)

        self._create_webview()

        self._timer = QTimer(self)
        self._timer.setInterval(600)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

    def _create_webview(self):
        self.webview = SafeQtWebViewWidget(incognito=self.incognito)
        if self.config.get("theme") == "dark":
            self.webview.set_background_color(43, 43, 43)
        else:
            self.webview.set_background_color(255, 255, 255)
            
        if hasattr(self.webview, 'signals'):
            self.webview.signals.title_changed.connect(self._on_title_changed)
            
        self.layout.addWidget(self.webview)
        
        if hasattr(self, '_new_window_handler_set'):
            delattr(self, '_new_window_handler_set')

    def _on_title_changed(self, title):
        if not title:
            return
            
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
                                QTimer.singleShot(0, lambda: self.main_window.start_download(url, self))
                                if not self._current_url or self._current_url == "about:blank":
                                    def close_this_tab():
                                        if self.main_window:
                                            idx = self.main_window.tab_layout.indexOf(self)
                                            if idx != -1:
                                                self.main_window.close_tab(idx)
                                    QTimer.singleShot(100, close_this_tab)
                            return False
                        return True
                    
                    if hasattr(self.webview._webview, "set_on_navigation"):
                        self.webview._webview.set_on_navigation(on_navigation)
                    
                    self._new_window_handler_set = True
                    
                    if self._pending_url:
                        self._do_pending_load()
            except Exception as e:
                pass
                
        is_active = False
        if self.main_window:
            is_active = (self.main_window.tab_layout.currentWidget() == self)
            
        if is_active:
            self._timer.setInterval(500)
        else:
            self._timer.setInterval(3000)

        try:
            url_val = self.webview.url
            url_str = url_val() if callable(url_val) else url_val
        except:
            url_str = ""

        if url_str is None:
            url_str = ""
        else:
            url_str = str(url_str)

        if url_str and url_str not in ("about:blank", "None", "") and url_str != self._current_url:
            self._current_url = url_str
            self._inject_adblock()
            
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
        dns_prov = self.config.get("dns", "none")
        custom_dns = self.config.get("customDns", "")
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
                background-color: #f9a8d4;
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
