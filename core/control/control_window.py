# core/control/control_window.py
import json
from PyQt5 import QtWidgets, QtCore, QtGui

# Imports robustes (exécution directe ou en module)
try:
    from .config import DEFAULTS
    from .camera_tab import CameraTab
    from .geometry_tab import GeometryTab
    from .appearance_tab import AppearanceTab
    from .dynamics_tab import DynamicsTab
    from .distribution_tab import DistributionTab
    from .mask_tab import MaskTab
    from .system_tab import SystemTab
except ImportError:
    from core.control.config import DEFAULTS
    from core.control.camera_tab import CameraTab
    from core.control.geometry_tab import GeometryTab
    from core.control.appearance_tab import AppearanceTab
    from core.control.dynamics_tab import DynamicsTab
    from core.control.distribution_tab import DistributionTab
    from core.control.mask_tab import MaskTab
    from core.control.system_tab import SystemTab


class ControlWindow(QtWidgets.QMainWindow):
    def __init__(self, app: QtWidgets.QApplication, screen: QtGui.QScreen, view_win):
        super().__init__(None)
        self.setWindowTitle("Dyxten — Control v2")
        self.view_win = view_win

        # Barre d’outils persistante
        tb = QtWidgets.QToolBar("Main")
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.setIconSize(QtCore.QSize(16, 16))
        self.addToolBar(QtCore.Qt.TopToolBarArea, tb)

        act_quit = QtWidgets.QAction("Shutdown", self)
        act_quit.setShortcut(QtGui.QKeySequence("Ctrl+Q"))
        act_quit.setShortcutContext(QtCore.Qt.ApplicationShortcut)
        act_quit.triggered.connect(app.quit)
        self.addAction(act_quit)
        tb.addAction(act_quit)

        # Bouton persistant en bas
        sb = QtWidgets.QStatusBar()
        self.setStatusBar(sb)
        btn_quit = QtWidgets.QPushButton("Shutdown")
        btn_quit.setCursor(QtCore.Qt.PointingHandCursor)
        btn_quit.clicked.connect(app.quit)
        sb.addPermanentWidget(btn_quit)

        # Raccourci redondant
        sc_quit = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Q"), self)
        sc_quit.setContext(QtCore.Qt.ApplicationShortcut)
        sc_quit.activated.connect(app.quit)

        # Onglets
        self.tabs = QtWidgets.QTabWidget()
        self.tab_camera = CameraTab()
        self.tab_geometry = GeometryTab()
        self.tab_appearance = AppearanceTab()
        self.tab_dynamics = DynamicsTab()
        self.tab_distribution = DistributionTab()
        self.tab_mask = MaskTab()
        self.tab_system = SystemTab()

        for t in [
            self.tab_camera,
            self.tab_geometry,
            self.tab_appearance,
            self.tab_dynamics,
            self.tab_distribution,
            self.tab_mask,
            self.tab_system,
        ]:
            t.changed.connect(self.on_delta)

        self.tab_geometry.topologyChanged.connect(self.on_topology_changed)

        self.tabs.addTab(self.tab_camera, "Caméra")
        self.tabs.addTab(self.tab_geometry, "Géométrie")
        self.tabs.addTab(self.tab_appearance, "Apparence")
        self.tabs.addTab(self.tab_dynamics, "Dynamique")
        self.tabs.addTab(self.tab_distribution, "Distribution")
        self.tabs.addTab(self.tab_mask, "Masques")
        self.tabs.addTab(self.tab_system, "Système")

        self.setCentralWidget(self.tabs)

        # Fenêtre
        self.resize(760, 900)
        geo = screen.availableGeometry()
        self.move(
            geo.x() + (geo.width() - self.width()) // 2,
            geo.y() + (geo.height() - self.height()) // 2,
        )
        self.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, True)
        self.show()

        # État initial
        self.state = {k: (v.copy() if isinstance(v, dict) else v) for k, v in DEFAULTS.items()}
        self.push_params()

    def on_delta(self, delta: dict):
        for k, v in delta.items():
            if isinstance(v, dict):
                self.state.setdefault(k, {}).update(v)
            else:
                self.state[k] = v
        try:
            self.view_win.set_transparent(bool(self.state.get("system", {}).get("transparent", True)))
        except Exception:
            pass
        self.push_params()

    def on_topology_changed(self, topo: str):
        pass

    def push_params(self):
        js = (
            "window.setDyxtenParams = window.setDyxtenParams || function(_){};"
            f"window.setDyxtenParams({json.dumps(self.state, ensure_ascii=False)});"
        )
        try:
            self.view_win.view.page().runJavaScript(js)
        except Exception:
            pass
