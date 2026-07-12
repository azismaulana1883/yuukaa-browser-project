import sys
import os
import json
import ctypes
import ctypes.wintypes
from PyQt6.QtCore import QTimer

# ======================================
# CONFIG & PATH UTILS
# ======================================
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

# ======================================
# WINDOWS LOW LEVEL HOOK
# ======================================
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
                    
                    ctrl = (ctypes.windll.user32.GetAsyncKeyState(0x11) & 0x8000) != 0
                    
                    if ctrl:
                        if vk == 0x54: # T
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
    
    ctypes.windll.kernel32.GetModuleHandleW.restype = ctypes.wintypes.HMODULE
    ctypes.windll.kernel32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
    
    ctypes.windll.user32.SetWindowsHookExW.restype = ctypes.wintypes.HHOOK
    ctypes.windll.user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, ctypes.wintypes.HINSTANCE, ctypes.wintypes.DWORD]
    
    ctypes.windll.user32.CallNextHookEx.restype = LRESULT
    ctypes.windll.user32.CallNextHookEx.argtypes = [ctypes.wintypes.HHOOK, ctypes.c_int, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM]
    
    _global_hook_proc = HOOKPROC(_keyboard_hook)
    h_mod = ctypes.windll.kernel32.GetModuleHandleW(None)
    _global_hook_id = ctypes.windll.user32.SetWindowsHookExW(13, _global_hook_proc, h_mod, 0)

def uninstall_keyboard_hook():
    global _global_hook_id
    if _global_hook_id:
        ctypes.windll.user32.UnhookWindowsHookEx(_global_hook_id)

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
