# -*- coding: utf-8 -*-
import sys
from pathlib import Path
from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QSurfaceFormat
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
        self._target_screen = screen
        self.view = QWebEngineView(self)
        self.view.setPage(QWebEnginePage(self.view))
        s = self.view.settings()
        s.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        s.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, False)
        s.setAttribute(QWebEngineSettings.JavascriptEnabled, True)

        w = QtWidgets.QWidget()
        w.setAttribute(Qt.WA_NoSystemBackground, True)
        w.setAutoFillBackground(False)
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.view)
        self.setCentralWidget(w)

        self.view.load(QUrl.fromLocalFile(str(html_path.resolve())))
        self._apply_screen_geometry(screen)
        QtWidgets.QShortcut(Qt.Key_Escape, self, activated=self.close)
        self._transparent = None
        QtCore.QTimer.singleShot(0, lambda: self.set_transparent(True))

    def _apply_screen_geometry(self, screen: QtGui.QScreen):
        if window_handle := self.windowHandle():
            window_handle.setScreen(screen)
        geometry = screen.geometry()
        width = int(geometry.width() * 0.8)
        height = int(geometry.height() * 0.8)
        left = geometry.left() + (geometry.width() - width) // 2
        top = geometry.top() + (geometry.height() - height) // 2
        self.setGeometry(left, top, width, height)

    def showEvent(self, event: QtGui.QShowEvent):
        self._apply_screen_geometry(self._target_screen)
        super().showEvent(event)

    def set_transparent(self, enabled: bool):
        enabled = bool(enabled)
        if self._transparent == enabled:
            return
        self._transparent = enabled
        bg_style = "background: transparent;" if enabled else ""
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, enabled)
        self.setAttribute(Qt.WA_TranslucentBackground, enabled)
        self.setStyleSheet(bg_style)
        central = self.centralWidget()
        if central is not None:
            central.setAttribute(Qt.WA_StyledBackground, True)
            central.setAutoFillBackground(not enabled)
            central.setAttribute(Qt.WA_NoSystemBackground, enabled)
            central.setAttribute(Qt.WA_TranslucentBackground, enabled)
            central.setStyleSheet(bg_style)
        self.view.setAttribute(Qt.WA_StyledBackground, True)
        self.view.setAttribute(Qt.WA_NoSystemBackground, enabled)
        self.view.setAttribute(Qt.WA_TranslucentBackground, enabled)
        self.view.setStyleSheet(bg_style)
        try:
            page = self.view.page()
        except Exception:
            page = None
        if page is not None:
            try:
                alpha = 0 if enabled else 255
                page.setBackgroundColor(QtGui.QColor(0, 0, 0, alpha))
            except Exception:
                pass
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
    view_win = ViewWindow(HTML, second)
    view_win.show()
    _ = ControlWindow(app, second, view_win)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
