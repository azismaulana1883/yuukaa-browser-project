import socket
import ssl
import tkinter as tk
import urllib.parse
from tkinter import font

# =========================================
# 1. NETWORK LAYER
# =========================================
def request(url):
    try:
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "http://" + url
            
        scheme, url = url.split("://", 1)
        if "/" not in url:
            url = url + "/"
        host, path = url.split("/", 1)
        path = "/" + path
        
        port = 80 if scheme == "http" else 443
        if ":" in host:
            host, port = host.split(":", 1)
            port = int(port)
            
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5.0)
        s.connect((host, port))
        
        if scheme == "https":
            ctx = ssl.create_default_context()
            s = ctx.wrap_socket(s, server_hostname=host)
            
        s.send(("GET {} HTTP/1.1\r\nHost: {}\r\nConnection: close\r\nUser-Agent: YuukaaToyBrowser/3.0\r\n\r\n".format(path, host)).encode("utf8"))
                
        response = s.makefile("r", encoding="utf8", newline="\r\n", errors="ignore")
        statusline = response.readline()
        
        # Abaikan header
        while True:
            line = response.readline()
            if line == "\r\n": break
            
        body = response.read()
        s.close()
        return body
    except Exception as e:
        return f"<html><body><p>Error memuat halaman: {e}</p></body></html>"

# =========================================
# 2. DOM PARSER (HTML Tree)
# =========================================
class TextNode:
    def __init__(self, text):
        self.text = text

class ElementNode:
    def __init__(self, tag, attributes=None):
        self.tag = tag
        self.attributes = attributes or {}
        self.children = []

def parse_attributes(attr_str):
    attrs = {}
    parts = attr_str.split()
    for part in parts:
        if "=" in part:
            k, v = part.split("=", 1)
            v = v.strip("'\"")
            attrs[k.lower()] = v
    return attrs

def parse_html(body):
    text = ""
    in_tag = False
    
    root = ElementNode("html")
    current_node = root
    stack = [root]
    
    i = 0
    while i < len(body):
        # Abaikan komentar
        if body[i:i+4] == "<!--":
            end = body.find("-->", i)
            i = end + 3 if end != -1 else len(body)
            continue
            
        # Abaikan isi <script> dan <style> sepenuhnya
        if body[i:i+7].lower() == "<script":
            end = body.lower().find("</script>", i)
            i = end + 9 if end != -1 else len(body)
            continue
        if body[i:i+6].lower() == "<style":
            end = body.lower().find("</style>", i)
            i = end + 8 if end != -1 else len(body)
            continue
            
        c = body[i]
        
        if c == "<":
            in_tag = True
            if text.strip():
                # Masukkan sisa teks sebagai TextNode
                clean_text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
                current_node.children.append(TextNode(clean_text))
            text = ""
        elif c == ">":
            in_tag = False
            tag_content = text.strip()
            text = ""
            
            if tag_content.startswith("/"):
                # Tag Penutup (</...>) - Naik kembali ke struktur pohon atasnya
                tag_name = tag_content[1:].split()[0].lower()
                if len(stack) > 1:
                    stack.pop()
                    current_node = stack[-1]
            elif tag_content.startswith("!"):
                pass
            else:
                # Tag Pembuka (<...>) - Buat cabang (ElementNode) baru
                parts = tag_content.split(None, 1)
                tag_name = parts[0].lower()
                attrs = parse_attributes(parts[1]) if len(parts) > 1 else {}
                
                new_node = ElementNode(tag_name, attrs)
                current_node.children.append(new_node)
                
                if tag_name not in ["br", "img", "meta", "link", "input", "hr"]:
                    current_node = new_node
                    stack.append(current_node)
        else:
            text += c
            
        i += 1
        
    return root

# =========================================
# 3. LAYOUT ENGINE (Membaca DOM Tree)
# =========================================
class WordLayout:
    def __init__(self, x, y, w, h, text, font_weight, font_style, color, url):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.text = text
        self.font_weight = font_weight
        self.font_style = font_style
        self.color = color
        self.url = url

WIDTH = 800
def layout_tree(node, cx, cy, font_w="normal", font_s="roman", color="black", link_url=None):
    display_list = []
    
    if isinstance(node, TextNode):
        words = node.text.split()
        for word in words:
            # Estimasi kasaran ukuran font (untuk deteksi klik)
            char_width = 8 if font_w == "normal" else 10
            char_height = 20
            w = len(word) * char_width
            
            # Word wrap
            if cx + w > WIDTH - 20:
                cy += char_height + 5
                cx = 20
                
            display_list.append(WordLayout(cx, cy, w, char_height, word, font_w, font_s, color, link_url))
            cx += w + char_width
            
    elif isinstance(node, ElementNode):
        # Format teks berdasarkan Tag
        if node.tag in ["h1", "h2", "h3", "b", "strong"]:
            font_w = "bold"
        if node.tag in ["i", "em"]:
            font_s = "italic"
        if node.tag == "a":
            color = "blue"
            link_url = node.attributes.get("href", link_url)
        if node.tag == "font":
            color = node.attributes.get("color", color)
            
        # Jika blok baru, paksa turun baris
        if node.tag in ["p", "h1", "h2", "h3", "div", "br", "li"]:
            cy += 25
            cx = 20
        if node.tag == "hr":
            cy += 40
            cx = 20
            
        # Panggil fungsi rekursif untuk membaca "Anak-anak" di dalam cabang ini
        for child in node.children:
            child_list, cx, cy = layout_tree(child, cx, cy, font_w, font_s, color, link_url)
            display_list.extend(child_list)
            
        if node.tag in ["p", "h1", "h2", "h3", "div", "ul", "hr"]:
            cy += 25
            cx = 20
            
    return display_list, cx, cy

# =========================================
# 4. RENDERER & GUI WINDOW (Interaktif)
# =========================================
class Browser:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("Yuukaa Engine V3 - DOM & Clickable Links")
        self.window.geometry(f"{WIDTH}x700")
        
        self.scroll_y = 0
        self.display_list = []
        self.current_url = ""
        
        # UI
        top_frame = tk.Frame(self.window)
        top_frame.pack(fill=tk.X)
        self.address_bar = tk.Entry(top_frame, font=("Arial", 12))
        self.address_bar.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.address_bar.bind("<Return>", self.on_enter)
        
        go_btn = tk.Button(top_frame, text="Kunjungi", command=self.on_enter_btn)
        go_btn.pack(side=tk.RIGHT, padx=5, pady=5)

        self.canvas = tk.Canvas(self.window, width=WIDTH, height=600, bg="white")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # BINDING MOUSE & KEYBOARD
        self.window.bind("<Up>", self.scrollup)
        self.window.bind("<Down>", self.scrolldown)
        self.window.bind("<MouseWheel>", self.mouse_scroll)
        self.canvas.bind("<Button-1>", self.on_click)

    def on_enter_btn(self):
        self.on_enter(None)
        
    def on_enter(self, event):
        query = self.address_bar.get()
        if not (query.startswith("http://") or query.startswith("https://")):
            # Arahkan ke Server Pencarian Lokal buatan kita sendiri
            query = "http://localhost:8001/search?q=" + urllib.parse.quote(query)
            self.address_bar.delete(0, tk.END)
            self.address_bar.insert(0, query)
        
        self.load(query)

    def scrolldown(self, e):
        self.scroll_y += 50; self.draw()

    def scrollup(self, e):
        self.scroll_y = max(self.scroll_y - 50, 0); self.draw()
        
    def mouse_scroll(self, e):
        if e.delta > 0:
            self.scroll_y = max(self.scroll_y - 50, 0)
        else:
            self.scroll_y += 50
        self.draw()

    def load(self, url):
        self.current_url = url
        self.scroll_y = 0
        self.canvas.delete("all")
        self.canvas.create_text(20, 20, text=f"Memuat DOM dari {url}...", anchor="nw", font=("Arial", 12))
        self.window.update()
        
        body = request(url)
        # 1. PARSE: Ubah teks HTML jadi Pohon (DOM)
        dom_tree = parse_html(body)
        # 2. LAYOUT: Baca pohon DOM dan tentukan kordinat X Y tiap kata
        self.display_list, _, _ = layout_tree(dom_tree, 20, 20)
        # 3. DRAW: Gambar ke Layar
        self.draw()
        
    def draw(self):
        self.canvas.delete("all")
        for word in self.display_list:
            draw_y = word.y - self.scroll_y
            if draw_y > -20 and draw_y < 700:
                # Gunakan font dan warna berdasarkan DOM Tree (Bold/Italic/Blue)
                fnt = ("Arial", 12, word.font_weight, word.font_style)
                # Jika kata ini punya atribut url (ia adalah Link <a>), garis bawahi
                if word.url:
                    self.canvas.create_text(word.x, draw_y, text=word.text, anchor="nw", font=fnt, fill=word.color)
                    # Gambar garis bawah manual
                    self.canvas.create_line(word.x, draw_y+16, word.x + word.w, draw_y+16, fill=word.color)
                else:
                    self.canvas.create_text(word.x, draw_y, text=word.text, anchor="nw", font=fnt, fill=word.color)

    # EVENT: Saat Layar di-Klik Mouse
    def on_click(self, event):
        click_x = event.x
        click_y = event.y + self.scroll_y # Kalkulasi offset scroll
        
        for word in self.display_list:
            # Pengecekan tabrakan: Apakah klik masuk dalam kordinat (X, Y, Lebar, Tinggi) kata ini?
            if word.x <= click_x <= word.x + word.w and word.y <= click_y <= word.y + word.h:
                if word.url:
                    # Gabungkan URL relatif (seperti /about) menjadi absolute (http://...)
                    target_url = urllib.parse.urljoin(self.current_url, word.url)
                    print(f"Mengklik Hyperlink: {target_url}")
                    
                    self.address_bar.delete(0, tk.END)
                    self.address_bar.insert(0, target_url)
                    self.load(target_url)
                    break

if __name__ == "__main__":
    browser = Browser()
    browser.load("http://example.org")
    tk.mainloop()
