import http.server
import socketserver
import urllib.parse
import urllib.request
import re

PORT = 8001

class SearchProxyHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        
        if parsed_path.path == "/search":
            query = urllib.parse.parse_qs(parsed_path.query).get('q', [''])[0]
            if query:
                html = self.fetch_real_search(query)
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html.encode("utf-8"))
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"<html><body><h1>Error</h1><p>Kata kunci kosong.</p></body></html>")
        else:
            html = "<html><body><font color='#7c4dff'><h1>Yuukaa Meta-Search Server</h1></font><p>Menunggu pencarian dari Toy Browser...</p></body></html>"
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

    def fetch_real_search(self, query):
        try:
            print(f"[Yuukaa Server] Scraping hasil asli untuk '{query}' dari internet...")
            
            # Melakukan Scraping ke DuckDuckGo versi HTML murni
            url = "https://html.duckduckgo.com/html/"
            data = urllib.parse.urlencode({'q': query}).encode('utf-8')
            req = urllib.request.Request(url, data=data, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Content-Type': 'application/x-www-form-urlencoded'
            })
            
            with urllib.request.urlopen(req) as response:
                html_data = response.read().decode('utf-8')
                
            results = []
            
            # Kita parsing manual (scraping) HTML dari duckduckgo
            # Pecah HTML berdasarkan blok hasil pencarian
            blocks = html_data.split('result__body">')
                
            for block in blocks[1:]:
                # Extract URL Asli dari class="result__a"
                url_match = re.search(r'class="result__a"\s+href="([^"]+)"', block)
                if not url_match: 
                    # Kadang atributnya terbalik (href="..." class="result__a")
                    url_match = re.search(r'href="([^"]+)"\s+class="result__a"', block)
                if not url_match: continue
                link = url_match.group(1)
                
                # Extract Judul
                title_match = re.search(r'<h2 class="result__title">.*?<a[^>]*>(.*?)</a>', block, re.DOTALL)
                title = title_match.group(1) if title_match else "Tanpa Judul"
                title = re.sub(r'<[^>]+>', '', title).strip() # Bersihkan sisa tag HTML
                
                # Extract Snippet Teks
                snippet_match = re.search(r'class="result__snippet[^>]*>(.*?)</a>', block, re.DOTALL)
                snippet = snippet_match.group(1) if snippet_match else ""
                snippet = re.sub(r'<[^>]+>', '', snippet).strip()
                
                # Bersihkan URL tracking dari DuckDuckGo untuk mendapatkan URL asli
                if "uddg=" in link:
                    parsed_link = urllib.parse.urlparse(link)
                    query_params = urllib.parse.parse_qs(parsed_link.query)
                    if "uddg" in query_params:
                        link = query_params["uddg"][0]
                        
                results.append({'title': title, 'url': link, 'snippet': snippet})
                
            # MERAKIT HTML UNTUK TOY BROWSER (Dengan UI yang DIPERCANTIK!)
            html = f"<html><body>"
            # Menggunakan tag khusus <font color="..."> yang akan kita buat dukungannya di Toy Browser
            html += f"<font color='#7c4dff'><h1>Yuukaa Meta-Search</h1></font>"
            html += f"<p>Menampilkan hasil penelusuran asli untuk: <b>{query}</b></p><hr>"
            
            if not results:
                html += "<p>Tidak ditemukan hasil.</p>"
            else:
                for res in results[:10]: # Tampilkan 10 hasil teratas
                    html += f"<div>"
                    html += f"<h2><a href='{res['url']}'>{res['title']}</a></h2>"
                    # Warna hijau untuk URL persis seperti Google
                    html += f"<font color='#006622'>{res['url']}</font><br>" 
                    html += f"<p>{res['snippet']}</p><br><br>"
                    html += f"</div>"
                    
            html += "</body></html>"
            return html
            
        except Exception as e:
            return f"<html><body><font color='red'><h1>Gagal</h1></font><p>Terjadi kesalahan server: {e}</p></body></html>"

if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), SearchProxyHandler) as httpd:
        print(f"Yuukaa Meta-Search Server berjalan di http://localhost:{PORT}")
        httpd.serve_forever()
