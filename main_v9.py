import sys
import os
import json
import threading
import webview

# ======================================
# CONFIG MANAGER
# ======================================
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

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

# ======================================
# ADBLOCK LOADER
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
        except Exception as e:
            print(f"Gagal load adblock: {e}")
    return blocked

# ======================================
# TAB MANAGER
# ======================================
class TabManager:
    """Manages multiple webview windows as tabs."""
    def __init__(self):
        self.tabs = {}      # tab_id -> webview.Window
        self.active_tab = None

    def add(self, tab_id, window):
        self.tabs[tab_id] = window
        self.active_tab = tab_id

    def get(self, tab_id):
        return self.tabs.get(tab_id)

    def remove(self, tab_id):
        self.tabs.pop(tab_id, None)

    def switch_to(self, tab_id):
        if tab_id in self.tabs:
            self.active_tab = tab_id
            return True
        return False

tab_manager = TabManager()

# ======================================
# PYTHON API (exposed to JS)
# ======================================
class BrowserAPI:
    def __init__(self, config, blocked_domains):
        self.config = config
        self.blocked_domains = blocked_domains
        self.main_window = None  # set after window creation

    def get_config(self):
        return self.config

    def navigate(self, tab_id, url):
        """Navigate a tab to a URL."""
        win = tab_manager.get(int(tab_id))
        if win:
            win.load_url(url)

    def go_back(self, tab_id):
        win = tab_manager.get(int(tab_id))
        if win:
            win.evaluate_js("history.back()")

    def go_forward(self, tab_id):
        win = tab_manager.get(int(tab_id))
        if win:
            win.evaluate_js("history.forward()")

    def reload(self, tab_id):
        win = tab_manager.get(int(tab_id))
        if win:
            win.evaluate_js("location.reload()")

    def new_tab(self, tab_id, incognito):
        """Create a new webview window for a tab (hidden until navigated)."""
        # We use the existing main window for content (single-process approach)
        # New tabs share the main window's webview
        tab_manager.add(int(tab_id), self.main_window)

    def switch_tab(self, tab_id, url):
        """Switch active content to this tab's URL."""
        tab_manager.switch_to(int(tab_id))
        if url:
            win = tab_manager.get(int(tab_id))
            if win:
                win.load_url(url)

    def open_settings(self, tab_id):
        """Load settings page."""
        settings_path = resource_path("settings.html")
        settings_url = f"file:///{settings_path.replace(chr(92), '/')}"
        theme = "dark" if self.config.get("theme") == "dark" else "light"
        engine = self.config.get("engine", "google")
        dns = self.config.get("dns", "none")
        custom_dns = self.config.get("customDns", "")
        
        full_url = f"{settings_url}?theme={theme}&engine={engine}&dns={dns}&customDns={custom_dns}"
        win = tab_manager.get(int(tab_id))
        if win:
            win.load_url(full_url)

    def toggle_theme(self, is_dark):
        self.config["theme"] = "dark" if is_dark else "light"
        save_config(self.config)

    def clear_data(self):
        pass  # WebView2 handles its own data clearing

    def save_settings(self, settings_json):
        """Called from settings.html to save config."""
        try:
            data = json.loads(settings_json)
            self.config.update(data)
            save_config(self.config)
        except Exception as e:
            print(f"Error saving settings: {e}")


# ======================================
# COSMETIC ADBLOCK JS
# ======================================
COSMETIC_JS = """
(function() {
    const selectors = [
        'div[style*="z-index: 2147483647"]',
        'div[style*="z-index: 2147483646"]',
        'div[style*="z-index: 999999"]',
        'iframe[src*="exoclick"]',
        'iframe[src*="popads"]',
        'iframe[src*="highcpm"]',
        '[id*="popunder"]',
        '[class*="popunder"]',
        '[class*="overlay-ad"]'
    ];

    function destroyAds() {
        try {
            document.querySelectorAll(selectors.join(',')).forEach(el => el.remove());
        } catch(e) {}
    }

    destroyAds();
    new MutationObserver(() => destroyAds()).observe(
        document.documentElement,
        { childList: true, subtree: true }
    );
})();
"""

# ======================================
# PAGE LOAD CALLBACKS
# ======================================
def on_loaded(window, api_instance, tab_id):
    """Inject AdBlock JS after page loads."""
    dns = api_instance.config.get("dns", "none")
    custom_dns = api_instance.config.get("customDns", "")
    is_adguard = (dns == "adguard") or (dns == "custom" and "adguard" in custom_dns.lower())
    
    if is_adguard:
        window.evaluate_js(COSMETIC_JS)

# ======================================
# MAIN
# ======================================
def main():
    config = load_config()
    blocked_domains = load_adblock_list()
    
    api = BrowserAPI(config, blocked_domains)
    
    # Load browser UI HTML
    ui_path = resource_path("browser_ui.html")
    ui_url = f"file:///{ui_path.replace(chr(92), '/')}"
    
    # Create main window
    main_window = webview.create_window(
        title="Yuukaa Search V9",
        url=ui_url,
        width=1280,
        height=800,
        min_size=(800, 600),
        js_api=api,
        frameless=False,
    )
    
    api.main_window = main_window
    tab_manager.add(1, main_window)  # First tab

    def on_page_loaded():
        on_loaded(main_window, api, 1)

    main_window.events.loaded += on_page_loaded

    # Start with Edge WebView2 backend (supports H.264 + Widevine)
    webview.start(
        gui='edgechromium',
        debug=False,
    )

if __name__ == '__main__':
    main()
