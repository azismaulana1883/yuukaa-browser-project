import os
import urllib.request
import urllib.error
import urllib.parse
from urllib.parse import urlparse
import threading
from PyQt6.QtCore import QThread, pyqtSignal
import json

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
            req = urllib.request.Request(self.url, headers={"User-Agent": "YuukaaBrowser/13.0"})
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
                data = json.loads(response.read().decode('utf-8'))
                if len(data) > 1 and isinstance(data[1], list):
                    self.suggestions_ready.emit(local_matches, data[1][:7])
        except:
            self.suggestions_ready.emit(local_matches, [])
