# core/control/control_window.py
import json
from typing import Optional
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
    from .profile_manager import ProfileManager
except ImportError:
    from core.control.config import DEFAULTS
    from core.control.camera_tab import CameraTab
    from core.control.geometry_tab import GeometryTab
    from core.control.appearance_tab import AppearanceTab
    from core.control.dynamics_tab import DynamicsTab
    from core.control.distribution_tab import DistributionTab
    from core.control.mask_tab import MaskTab
    from core.control.system_tab import SystemTab
    from core.control.profile_manager import ProfileManager


class ControlWindow(QtWidgets.QMainWindow):
    def __init__(self, app: QtWidgets.QApplication, screen: QtGui.QScreen, view_win):
        super().__init__(None)
        self.setWindowTitle("Dyxten — Control v2")
        self.view_win = view_win
        self.profile_mgr = ProfileManager()
        self._loading_profile = False
        self._updating_profiles = False
        self._dirty = False
        self._view_ready = False
        self._pending_js: Optional[str] = None
        self.state = {}
        self.current_profile = ProfileManager.DEFAULT_PROFILE

        self.profile_mgr = ProfileManager()
        self._loading_profile = False
        self._updating_profiles = False
        self._dirty = False


        self.state = {}

        self.current_profile = ProfileManager.DEFAULT_PROFILE



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

        tb.addSeparator()
        lbl_profile = QtWidgets.QLabel("Profil :")
        tb.addWidget(lbl_profile)
        self.cb_profiles = QtWidgets.QComboBox()
        self.cb_profiles.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.cb_profiles.setMinimumContentsLength(8)
        self.cb_profiles.currentTextChanged.connect(self.on_profile_selected)
        tb.addWidget(self.cb_profiles)

        self.act_save_profile = QtWidgets.QAction("Sauver", self)
        self.act_save_profile.setShortcut(QtGui.QKeySequence("Ctrl+S"))
        self.act_save_profile.setShortcutContext(QtCore.Qt.ApplicationShortcut)
        self.act_save_profile.triggered.connect(self.save_profile)
        self.addAction(self.act_save_profile)
        tb.addAction(self.act_save_profile)

        self.act_save_as_profile = QtWidgets.QAction("Sauver sous…", self)
        self.act_save_as_profile.setShortcut(QtGui.QKeySequence("Ctrl+Shift+S"))
        self.act_save_as_profile.setShortcutContext(QtCore.Qt.ApplicationShortcut)
        self.act_save_as_profile.triggered.connect(self.save_profile_as)
        self.addAction(self.act_save_as_profile)
        tb.addAction(self.act_save_as_profile)

        self.act_rename_profile = QtWidgets.QAction("Renommer", self)
        self.act_rename_profile.triggered.connect(self.rename_profile)
        tb.addAction(self.act_rename_profile)

        self.act_delete_profile = QtWidgets.QAction("Supprimer", self)
        self.act_delete_profile.triggered.connect(self.delete_profile)
        tb.addAction(self.act_delete_profile)

        self.act_reload_profile = QtWidgets.QAction("Recharger", self)
        self.act_reload_profile.setShortcut(QtGui.QKeySequence("F5"))
        self.act_reload_profile.setShortcutContext(QtCore.Qt.ApplicationShortcut)
        self.act_reload_profile.triggered.connect(self.reload_profile)
        self.addAction(self.act_reload_profile)
        tb.addAction(self.act_reload_profile)

        # Barre de statut pour les messages utilisateur
        sb = QtWidgets.QStatusBar()
        self.setStatusBar(sb)

        view = getattr(self.view_win, "view", None)
        if view is not None:
            try:
                view.loadFinished.connect(self._on_view_ready)
            except Exception:
                pass
            try:
                if hasattr(view, "isLoading") and not view.isLoading():
                    QtCore.QTimer.singleShot(0, lambda: self._on_view_ready(True))
            except Exception:
                pass

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
        self.refresh_profiles(select=self.current_profile)
        if self.current_profile:
            self.load_profile(self.current_profile)

    # ----------------------------------------------------------------- profil
    def refresh_profiles(self, select: Optional[str] = None):
        names = list(self.profile_mgr.list_profiles())
        if not names:
            names = [ProfileManager.DEFAULT_PROFILE]
        self._updating_profiles = True
        try:
            with QtCore.QSignalBlocker(self.cb_profiles):
                self.cb_profiles.clear()
                self.cb_profiles.addItems(names)
            target = select or self.current_profile
            if target in names:
                idx = self.cb_profiles.findText(target)
                if idx != -1:
                    self.cb_profiles.setCurrentIndex(idx)
            else:
                self.cb_profiles.setCurrentIndex(0)
        finally:
            self._updating_profiles = False

    def on_profile_selected(self, name: str):
        if self._updating_profiles or self._loading_profile:
            return
        if name:
            self.load_profile(name)

    def load_profile(self, name: str):
        self._loading_profile = True
        try:
            profile = self.profile_mgr.get_profile(name)
            self.state = {k: (v.copy() if isinstance(v, dict) else v) for k, v in profile.items()}
            self.tab_camera.set_defaults(self.state.get("camera"))
            self.tab_geometry.set_defaults(self.state.get("geometry"))
            self.tab_appearance.set_defaults(self.state.get("appearance"))
            self.tab_dynamics.set_defaults(self.state.get("dynamics"))
            self.tab_distribution.set_defaults(self.state.get("distribution"))
            self.tab_mask.set_defaults(self.state.get("mask"))
            self.tab_system.set_defaults(self.state.get("system"))
        finally:
            self._loading_profile = False
        self.current_profile = name
        self.set_dirty(False)
        self.refresh_profiles(select=name)
        self._apply_transparency()
        self.push_params()
        self.statusBar().showMessage(f"Profil '{name}' chargé", 3000)

    def reload_profile(self):
        if self.current_profile:
            self.load_profile(self.current_profile)

    def collect_state(self) -> dict:
        return dict(
            camera=self.tab_camera.collect(),
            geometry=self.tab_geometry.collect(),
            appearance=self.tab_appearance.collect(),
            dynamics=self.tab_dynamics.collect(),
            distribution=self.tab_distribution.collect(),
            mask=self.tab_mask.collect(),
            system=self.tab_system.collect(),
        )

    def save_profile(self):
        if not self.current_profile:
            self.save_profile_as()
            return
        self.state = self.collect_state()
        try:
            self.profile_mgr.save_profile(self.current_profile, self.state)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Erreur", str(exc))
            return
        self.set_dirty(False)
        self.statusBar().showMessage(f"Profil '{self.current_profile}' enregistré", 3000)

    def save_profile_as(self):
        name, ok = QtWidgets.QInputDialog.getText(self, "Sauver le profil", "Nom du profil :", text=self.current_profile or "")
        if not ok:
            return
        name = name.strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Nom invalide", "Veuillez saisir un nom de profil.")
            return
        if self.profile_mgr.has_profile(name) and name != self.current_profile:
            resp = QtWidgets.QMessageBox.question(
                self,
                "Écraser le profil",
                f"Le profil '{name}' existe déjà. Voulez-vous l'écraser ?",
            )
            if resp != QtWidgets.QMessageBox.Yes:
                return
        state = self.collect_state()
        try:
            self.profile_mgr.save_profile(name, state)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Erreur", str(exc))
            return
        self.state = state
        self.current_profile = name
        self.refresh_profiles(select=name)
        self.set_dirty(False)
        self.statusBar().showMessage(f"Profil '{name}' enregistré", 3000)

    def rename_profile(self):
        if self.current_profile == ProfileManager.DEFAULT_PROFILE:
            QtWidgets.QMessageBox.information(self, "Action impossible", "Le profil par défaut ne peut pas être renommé.")
            return
        name, ok = QtWidgets.QInputDialog.getText(self, "Renommer le profil", "Nouveau nom :", text=self.current_profile)
        if not ok:
            return
        name = name.strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Nom invalide", "Veuillez saisir un nom de profil.")
            return
        if self.profile_mgr.has_profile(name):
            QtWidgets.QMessageBox.warning(self, "Nom déjà utilisé", "Un profil avec ce nom existe déjà.")
            return
        try:
            self.profile_mgr.rename_profile(self.current_profile, name)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Erreur", str(exc))
            return
        self.current_profile = name
        self.refresh_profiles(select=name)
        self.set_dirty(False)
        self.statusBar().showMessage(f"Profil renommé en '{name}'", 3000)

    def delete_profile(self):
        if self.current_profile == ProfileManager.DEFAULT_PROFILE:
            QtWidgets.QMessageBox.information(self, "Action impossible", "Le profil par défaut ne peut pas être supprimé.")
            return
        resp = QtWidgets.QMessageBox.question(
            self,
            "Supprimer le profil",
            f"Voulez-vous vraiment supprimer le profil '{self.current_profile}' ?",
        )
        if resp != QtWidgets.QMessageBox.Yes:
            return
        try:
            self.profile_mgr.delete_profile(self.current_profile)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Erreur", str(exc))
            return
        self.statusBar().showMessage("Profil supprimé", 3000)
        self.current_profile = ProfileManager.DEFAULT_PROFILE
        self.refresh_profiles(select=self.current_profile)
        self.load_profile(self.current_profile)

    def set_dirty(self, dirty: bool):
        self._dirty = dirty
        self.update_window_title()
        self.act_rename_profile.setEnabled(self.current_profile != ProfileManager.DEFAULT_PROFILE)
        self.act_delete_profile.setEnabled(self.current_profile != ProfileManager.DEFAULT_PROFILE)

    def update_window_title(self):
        suffix = ""
        if self.current_profile:
            suffix = f" — {self.current_profile}{'*' if self._dirty else ''}"
        self.setWindowTitle("Dyxten — Control v2" + suffix)

    def _apply_transparency(self):
        try:
            self.view_win.set_transparent(bool(self.state.get("system", {}).get("transparent", True)))
        except Exception:
            pass

    def on_delta(self, delta: dict):
        for k, v in delta.items():
            if isinstance(v, dict):
                self.state.setdefault(k, {}).update(v)
            else:
                self.state[k] = v
        self._apply_transparency()
        if not self._loading_profile:
            self.set_dirty(not self.profile_mgr.profile_equals(self.current_profile, self.state))
        self.push_params()

    def on_topology_changed(self, topo: str):
        pass

    def push_params(self):
        js = (
            "window.setDyxtenParams = window.setDyxtenParams || function(_){};"
            f"window.setDyxtenParams({json.dumps(self.state, ensure_ascii=False)});"
        )
        if not self._view_ready:
            self._pending_js = js
            return
        self._run_js(js)

    def _on_view_ready(self, ok: bool):
        if not ok:
            self.statusBar().showMessage("Impossible de charger l’aperçu web", 5000)
            return
        self._view_ready = True
        if self._pending_js:
            pending = self._pending_js
            self._pending_js = None
            self._run_js(pending)

    def _run_js(self, js: str):
        try:
            self.view_win.view.page().runJavaScript(js)
        except Exception:
            pass
