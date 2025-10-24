# -*- coding: utf-8 -*-
import sys
from pathlib import Path
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings
from PyQt5.QtWebChannel import QWebChannel
from host import Host  # cf. app/host.py plus bas

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "ui" / "web" / "index.html"   # on garde ton chemin

def main():
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication(sys.argv)

    if not HTML.exists():
        QtWidgets.QMessageBox.critical(None, "Erreur", f"HTML introuvable:\n{HTML}")
        sys.exit(1)

    view = QWebEngineView()
    s = view.settings()
    s.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
    s.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, False)
    s.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
    s.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)

    # Pont Python ↔ JS
    host = Host()
    channel = QWebChannel(view.page())
    channel.registerObject("Host", host)
    view.page().setWebChannel(channel)

    view.setWindowTitle("Dyxten Viewer")
    view.resize(1280, 800)
    view.load(QUrl.fromLocalFile(str(HTML.resolve())))
    view.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
