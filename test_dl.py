import sys
from PyQt6.QtWidgets import QApplication
from qtwebview2.widget import QtWebViewWidget
from PyQt6.QtCore import QTimer

app = QApplication(sys.argv)
w = QtWebViewWidget()
# Direct download link for a small zip file (Python source release)
w.load_url("https://www.python.org/ftp/python/3.11.0/Python-3.11.0.tar.xz")
w.show()
QTimer.singleShot(5000, app.quit)
sys.exit(app.exec())
