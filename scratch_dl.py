import sys
from PyQt6.QtWidgets import QApplication
from qtwebview2.widget import QtWebViewWidget

app = QApplication(sys.argv)
w = QtWebViewWidget()
# create a data URI download link
html = """
<html><body>
<a href="data:text/plain;charset=utf-8,Hello%20World" download="test.txt">Download File</a>
</body></html>
"""
w.load_html(html)
w.show()
sys.exit(app.exec())
