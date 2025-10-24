# -*- coding: utf-8 -*-
import sys
from pathlib import Path
from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QSurfaceFormat, QColor
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings, QWebEnginePage

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "ui" / "web" / "index.html"

fmt = QSurfaceFormat()
fmt.setAlphaBufferSize(8)
QSurfaceFormat.setDefaultFormat(fmt)


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

        wrapper = QtWidgets.QWidget()
        wrapper.setAutoFillBackground(False)
        wrapper.setAttribute(Qt.WA_NoSystemBackground, True)
        lay = QtWidgets.QVBoxLayout(wrapper)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.view)
        self.setCentralWidget(wrapper)

        self.view.load(QUrl.fromLocalFile(str(html_path.resolve())))
        self.setGeometry(screen.availableGeometry())
        QtWidgets.QShortcut(Qt.Key_Escape, self, activated=self.close)

        # transparence ON au démarrage
        QtCore.QTimer.singleShot(300, lambda: self.set_transparent(True))

    def set_transparent(self, enabled: bool):
        self.setAttribute(Qt.WA_TranslucentBackground, enabled)
        self.setStyleSheet("background: transparent;" if enabled else "")
        self.view.setAttribute(Qt.WA_TranslucentBackground, enabled)
        self.view.setStyleSheet("background: transparent;" if enabled else "")
        try:
            self.view.page().setBackgroundColor(QColor(0, 0, 0, 0) if enabled else QColor(255, 255, 255, 255))
        except Exception:
            pass
        self.centralWidget().setAutoFillBackground(not enabled)
        self.view.update()
        self.update()


class ControlWindow(QtWidgets.QMainWindow):
    def __init__(self, app: QtWidgets.QApplication, screen: QtGui.QScreen, view_win: ViewWindow):
        super().__init__(None)
        self.setWindowTitle("Dyxten — Control")
        self.view_win = view_win

        # --- sliders ---
        self.sld_height = QtWidgets.QSlider(Qt.Horizontal)  # élévation (°)
        self.sld_height.setRange(-90, 90); self.sld_height.setValue(15)

        self.sld_tilt = QtWidgets.QSlider(Qt.Horizontal)    # inclinaison plane (°)
        self.sld_tilt.setRange(-90, 90); self.sld_tilt.setValue(0)

        self.sld_speed = QtWidgets.QSlider(Qt.Horizontal)   # vitesse (°/s)
        self.sld_speed.setRange(0, 180); self.sld_speed.setValue(20)

        lab1 = QtWidgets.QLabel("Hauteur orbitale (°)")
        lab2 = QtWidgets.QLabel("Inclinaison latérale (°)")
        lab3 = QtWidgets.QLabel("Vitesse orbitale (°/s)")

        btn = QtWidgets.QPushButton("Shutdown")
        btn.setMinimumHeight(40); btn.clicked.connect(app.quit)

        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16); lay.setSpacing(10)
        lay.addWidget(lab1); lay.addWidget(self.sld_height)
        lay.addWidget(lab2); lay.addWidget(self.sld_tilt)
        lay.addWidget(lab3); lay.addWidget(self.sld_speed)
        lay.addWidget(btn)
        self.setCentralWidget(w)

        self.resize(360, 280)
        geo = screen.availableGeometry()
        self.move(geo.x() + (geo.width()-self.width())//2,
                  geo.y() + (geo.height()-self.height())//2)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.show()

        for sld in (self.sld_height, self.sld_tilt, self.sld_speed):
            sld.valueChanged.connect(self.update_js)

        # push initial après chargement, avec polling JS tant que la fonction n'existe pas
        self.view_win.view.page().loadFinished.connect(lambda ok: self.update_js())
        self.update_js()

    def update_js(self):
        h = self.sld_height.value()
        t = self.sld_tilt.value()
        s = self.sld_speed.value()
        # Poll côté page jusqu'à ce que setCameraParams soit défini
        script = (
            "(() => {"
            "  const push = () => {"
            f"    if (typeof window.setCameraParams === 'function') {{ window.setCameraParams({h},{t},{s}); }}"
            "    else { setTimeout(push, 50); }"
            "  };"
            "  push();"
            "})();"
        )
        try:
            self.view_win.view.page().runJavaScript(script)
        except Exception:
            pass


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
