import urllib.request
import urllib.parse

def test_jsonp():
    url = f"http://suggestqueries.google.com/complete/search?client=chrome&q=face&callback=myFunc"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=2) as response:
            print("Response:", response.read().decode('utf-8'))
    except Exception as e:
        print("Error:", e)

test_jsonp()
