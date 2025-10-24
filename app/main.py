# -*- coding: utf-8 -*-
import sys
from pathlib import Path
from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings, QWebEnginePage

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "ui" / "web" / "index.html"

class ViewWindow(QtWidgets.QMainWindow):
    def __init__(self, html_path: Path, screen: QtGui.QScreen):
        super().__init__(None)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.view = QWebEngineView(self)
        self.view.setPage(QWebEnginePage(self.view))

        s = self.view.settings()
        s.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        s.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, False)
        s.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        s.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)

        if not html_path.exists():
            QtWidgets.QMessageBox.critical(self, "Erreur", f"HTML introuvable:\n{html_path}")
            sys.exit(1)

        self._apply_transparency(False)  # démarrage opaque

        self.view.load(QUrl.fromLocalFile(str(html_path.resolve())))
        self.setCentralWidget(self.view)

        geo = screen.availableGeometry()
        self.setGeometry(geo)
        QtWidgets.QShortcut(Qt.Key_Escape, self, activated=self.close)

    def _apply_transparency(self, enabled: bool):
        # Fenêtre
        self.setAttribute(Qt.WA_TranslucentBackground, enabled)
        self.setStyleSheet("background: transparent;" if enabled else "")
        # WebEngine
        self.view.setAttribute(Qt.WA_TranslucentBackground, enabled)
        self.view.setStyleSheet("background: transparent;" if enabled else "")
        try:
            self.view.page().setBackgroundColor(Qt.transparent if enabled else Qt.white)
        except Exception:
            pass
        cw = self.centralWidget()
        if cw: cw.setAutoFillBackground(not enabled)
        self.view.update(); self.update()

    def set_transparent(self, enabled: bool):
        self._apply_transparency(bool(enabled))

class ControlWindow(QtWidgets.QMainWindow):
    def __init__(self, app: QtWidgets.QApplication, screen: QtGui.QScreen, view_win: ViewWindow):
        super().__init__(None)
        self.setWindowTitle("Dyxten — Control")
        self.view_win = view_win

        self.chk_transp = QtWidgets.QCheckBox("Fond HTML transparent")
        self.chk_transp.stateChanged.connect(lambda s: self.view_win.set_transparent(s == Qt.Checked))

        btn = QtWidgets.QPushButton("Shutdown"); btn.setMinimumHeight(40); btn.clicked.connect(app.quit)

        w = QtWidgets.QWidget(); lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(16,16,16,16); lay.setSpacing(12)
        lay.addWidget(self.chk_transp); lay.addWidget(btn)
        self.setCentralWidget(w)

        self.resize(320,140)
        geo = screen.availableGeometry()
        self.move(geo.x() + (geo.width()-self.width())//2, geo.y() + (geo.height()-self.height())//2)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.show()

def main():
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication(sys.argv)

    screens = QtGui.QGuiApplication.screens()
    primary = QtGui.QGuiApplication.primaryScreen()
    second = screens[1] if len(screens) > 1 else primary

    view_win = ViewWindow(HTML, primary); view_win.show()
    _ = ControlWindow(app, second, view_win)

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
