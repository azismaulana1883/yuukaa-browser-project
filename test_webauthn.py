import sys
from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineScript, QWebEngineProfile

app = QApplication(sys.argv)

script = QWebEngineScript()
script.setName("BlockWebAuthn")
script.setSourceCode("""
    // Timpa PublicKeyCredential
    window.PublicKeyCredential = undefined;
    // Timpa navigator.credentials
    if (navigator.credentials) {
        navigator.credentials.get = function() {
            return Promise.reject(new Error("Not allowed"));
        };
    }
""")
script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)

profile = QWebEngineProfile.defaultProfile()
profile.scripts().insert(script)

view = QWebEngineView()
view.setUrl(QUrl("https://www.facebook.com"))
view.show()

sys.exit(app.exec())
