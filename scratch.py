import sys
from PyQt6.QtWidgets import QApplication
from qtwebview2.widget import QtWebViewWidget
from PyQt6.QtCore import QTimer

app = QApplication(sys.argv)
w = QtWebViewWidget()
w.load_html('<html><body><a id="link" href="https://example.com" target="_blank">Click me</a></body></html>')

def on_new_window(*args):
    print("New window requested:", args)
    return True # Prevent default behavior (hopefully?)

w.show()

def set_handler():
    try:
        w._webview.set_on_new_window(on_new_window)
        print("Handler set.")
        w.eval_js("document.getElementById('link').click();")
    except Exception as e:
        print("Error:", e)

QTimer.singleShot(1000, set_handler)
QTimer.singleShot(5000, app.quit) # auto quit

sys.exit(app.exec())
