# -*- coding: utf-8 -*-
import sys
from pathlib import Path
from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QSurfaceFormat, QColor
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings, QWebEnginePage

# --- autorise l'exécution directe ---
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from .control.control_window import ControlWindow  # exécution via -m
except ImportError:
    from core.control.control_window import ControlWindow  # exécution directe

HTML = ROOT / "ui" / "web" / "index.html"

fmt = QSurfaceFormat()
fmt.setAlphaBufferSize(8)
QSurfaceFormat.setDefaultFormat(fmt)


def _fail_fast_verify():
    import core.control.control_window as cw
    path = Path(cw.__file__).resolve()
    print("Loaded control_window:", path)
    if not hasattr(cw, "ControlWindow"):
        raise SystemExit("FATAL: ControlWindow introuvable dans control_window.py")
    txt = path.read_text(encoding="utf-8", errors="ignore")
    if "Dyxten — Control v2" not in txt or "QStatusBar" not in txt or "ApplicationShortcut" not in txt:
        raise SystemExit("FATAL: Mauvaise version de control_window.py chargée (pas v2).")


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

        w = QtWidgets.QWidget()
        w.setAutoFillBackground(False)
        w.setAttribute(Qt.WA_NoSystemBackground, True)
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.view)
        self.setCentralWidget(w)

        self.view.load(QUrl.fromLocalFile(str(html_path.resolve())))
        self.setGeometry(screen.availableGeometry())
        QtWidgets.QShortcut(Qt.Key_Escape, self, activated=self.close)
        QtCore.QTimer.singleShot(300, lambda: self.set_transparent(True))

    def set_transparent(self, enabled: bool):
        self.setAttribute(Qt.WA_TranslucentBackground, enabled)
        self.setStyleSheet("background: transparent;" if enabled else "")
        self.view.setAttribute(Qt.WA_TranslucentBackground, enabled)
        self.view.setStyleSheet("background: transparent;" if enabled else "")
        try:
            self.view.page().setBackgroundColor(QtGui.QColor(0, 0, 0, 0) if enabled else QtGui.QColor(0, 0, 0, 255))
        except Exception:
            pass
        self.centralWidget().setAutoFillBackground(not enabled)
        self.view.update()
        self.update()


def main():
    _fail_fast_verify()
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication(sys.argv)
    screens = QtGui.QGuiApplication.screens()
    primary = QtGui.QGuiApplication.primaryScreen()
    second = screens[1] if len(screens) > 1 else primary
    view_win = ViewWindow(HTML, primary)
    view_win.show()
    _ = ControlWindow(app, second, view_win)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
