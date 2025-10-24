# -*- coding: utf-8 -*-
import sys
from pathlib import Path
from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "ui" / "web" / "index.html"


class HtmlFrameless(QtWidgets.QMainWindow):
    def __init__(self, html_path: Path, screen: QtGui.QScreen):
        super().__init__(None)
        # Fenêtre sans bordure
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)

        # Vue Web
        view = QWebEngineView(self)
        s = view.settings()
        s.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        s.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, False)
        s.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        s.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)

        if not html_path.exists():
            QtWidgets.QMessageBox.critical(self, "Erreur", f"HTML introuvable:\n{html_path}")
            sys.exit(1)

        view.load(QUrl.fromLocalFile(str(html_path.resolve())))
        self.setCentralWidget(view)

        # Occuper tout l'écran cible
        geo = screen.availableGeometry()
        self.setGeometry(geo)
        # self.showFullScreen()  # option plein écran

        QtWidgets.QShortcut(Qt.Key_Escape, self, activated=self.close)


class ControlOnSecond(QtWidgets.QMainWindow):
    def __init__(self, app: QtWidgets.QApplication, screen: QtGui.QScreen):
        super().__init__(None)
        self.setWindowTitle("Dyxten — Control")

        btn = QtWidgets.QPushButton("Shutdown")
        btn.setMinimumHeight(48)
        btn.clicked.connect(app.quit)

        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.addWidget(btn)
        self.setCentralWidget(w)

        # Taille et placement sur le second écran
        self.resize(300, 120)
        geo = screen.availableGeometry()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + (geo.height() - self.height()) // 2
        self.move(x, y)

        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.show()


def main():
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication(sys.argv)

    screens = QtGui.QGuiApplication.screens()
    primary = QtGui.QGuiApplication.primaryScreen()
    second = screens[1] if len(screens) > 1 else primary

    html_win = HtmlFrameless(HTML, primary)
    html_win.show()

    ctrl_win = ControlOnSecond(app, second)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
