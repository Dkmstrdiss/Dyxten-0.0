# core/control/control_window.py
import copy
from typing import Optional

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt


# Imports robustes (exécution directe ou en module)
try:
    from .config import DEFAULTS, PROFILE_PRESET_DESCRIPTIONS
    from .camera_tab import CameraTab
    from .geometry_tab import GeometryTab
    from .appearance_tab import AppearanceTab
    from .dynamics_tab import DynamicsTab
    from .distribution_tab import DistributionTab
    from .system_tab import SystemTab
    from .link_controller_tab import LinkControllerTab
    from .profile_manager import ProfileManager, SubProfileManager
    from ..donut import default_donut_config, sanitize_donut_state
except ImportError:  # pragma: no cover - compatibilité exécution directe
    from core.control.config import DEFAULTS, PROFILE_PRESET_DESCRIPTIONS  # type: ignore
    from core.control.camera_tab import CameraTab  # type: ignore
    from core.control.geometry_tab import GeometryTab  # type: ignore
    from core.control.appearance_tab import AppearanceTab  # type: ignore
    from core.control.dynamics_tab import DynamicsTab  # type: ignore
    from core.control.distribution_tab import DistributionTab  # type: ignore
    from core.control.system_tab import SystemTab  # type: ignore
    from core.control.link_controller_tab import LinkControllerTab  # type: ignore
    from core.control.profile_manager import ProfileManager, SubProfileManager  # type: ignore
    from core.donut import default_donut_config, sanitize_donut_state  # type: ignore


FLAT_TOPOLOGIES = {
    "disk_phyllotaxis",
    "archimede_spiral",
    "log_spiral",
    "rose_curve",
    "superformula_2D",
    "density_warp_disk",
    "poisson_disk",
    "lissajous_disk",
    "concentric_rings",
    "hex_packing_plane",
    "voronoi_seeds",
}


class ControlWindow(QtWidgets.QMainWindow):
    def __init__(self, app: QtWidgets.QApplication, screen: QtGui.QScreen, view_win):
        super().__init__(None)
        self.setWindowTitle("Dyxten — Control v2")
        self.view_win = view_win
        self.profile_mgr = ProfileManager()
        self.subprofile_mgr = SubProfileManager()
        self._loading_profile = False
        self._updating_profiles = False
        self._dirty = False
        self._view_ready = True
        self.state = {"donut": default_donut_config()}
        self.current_profile = ProfileManager.DEFAULT_PROFILE

        self._apply_theme()

        # Barre d’outils persistante
        toolbar = QtWidgets.QToolBar("Main")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setIconSize(QtCore.QSize(18, 18))
        toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)

        self.addToolBar(QtCore.Qt.TopToolBarArea, toolbar)

        style = self.style()

        act_quit = QtWidgets.QAction(
            style.standardIcon(QtWidgets.QStyle.SP_TitleBarCloseButton), "Shutdown", self
        )
        act_quit.setShortcut(QtGui.QKeySequence("Ctrl+Q"))
        act_quit.setShortcutContext(QtCore.Qt.ApplicationShortcut)
        act_quit.triggered.connect(app.quit)
        self.addAction(act_quit)
        toolbar.addAction(act_quit)
        # Style rouge spécifique au bouton Shutdown
        btn_quit = toolbar.widgetForAction(act_quit)
        btn_quit.setStyleSheet("""
            QToolButton {
                background: #b22222;           /* rouge sombre */
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 8px;
                color: #ffffff;
                font-weight: 500;
                padding: 4px 10px;
            }
            QToolButton:hover {
                background: #d32f2f;           /* rouge clair au survol */
            }
            QToolButton:pressed {
                background: #8b0000;           /* rouge profond au clic */
            }
        """)


        toolbar.addSeparator()
        lbl_profile = QtWidgets.QLabel("Profil :")
        toolbar.addWidget(lbl_profile)

        self.cb_profiles = QtWidgets.QComboBox()
        self.cb_profiles.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.cb_profiles.setMinimumContentsLength(8)
        self.cb_profiles.currentTextChanged.connect(self.on_profile_selected)
        toolbar.addWidget(self.cb_profiles)

        # Réduit la largeur de séparation
        spacer = QtWidgets.QWidget()
        spacer.setFixedWidth(12)  # au lieu d'expanding
        toolbar.addWidget(spacer)


        self.act_save_profile = QtWidgets.QAction(
            style.standardIcon(QtWidgets.QStyle.SP_DialogSaveButton), "Sauver", self
        )
        self.act_save_profile.setShortcut(QtGui.QKeySequence("Ctrl+S"))
        self.act_save_profile.setShortcutContext(QtCore.Qt.ApplicationShortcut)
        self.act_save_profile.triggered.connect(self.save_profile)
        self.addAction(self.act_save_profile)
        toolbar.addAction(self.act_save_profile)
        # Sauver
        self.act_save_profile.setToolTip("Sauver")
        self.act_save_profile.setStatusTip("Sauver")

        self.act_save_as_profile = QtWidgets.QAction(
            style.standardIcon(QtWidgets.QStyle.SP_DialogOpenButton), "Sauver sous…", self
        )
        self.act_save_as_profile.setShortcut(QtGui.QKeySequence("Ctrl+Shift+S"))
        self.act_save_as_profile.setShortcutContext(QtCore.Qt.ApplicationShortcut)
        self.act_save_as_profile.triggered.connect(self.save_profile_as)
        self.addAction(self.act_save_as_profile)
        toolbar.addAction(self.act_save_as_profile)
        # Sauver
        self.act_save_profile.setToolTip("Sauver")
        self.act_save_profile.setStatusTip("Sauver")

        self.act_rename_profile = QtWidgets.QAction(
            style.standardIcon(QtWidgets.QStyle.SP_FileDialogNewFolder), "Renommer", self
        )
        self.act_rename_profile.triggered.connect(self.rename_profile)
        toolbar.addAction(self.act_rename_profile)
        # Renommer
        self.act_rename_profile.setToolTip("Renommer")
        self.act_rename_profile.setStatusTip("Renommer")

        self.act_delete_profile = QtWidgets.QAction(
            style.standardIcon(QtWidgets.QStyle.SP_TrashIcon), "Supprimer", self
        )
        self.act_delete_profile.triggered.connect(self.delete_profile)
        toolbar.addAction(self.act_delete_profile)
        # Supprimer
        self.act_delete_profile.setToolTip("Supprimer")
        self.act_delete_profile.setStatusTip("Supprimer")


        self.act_reload_profile = QtWidgets.QAction(
            style.standardIcon(QtWidgets.QStyle.SP_BrowserReload), "Recharger", self
        )
        self.act_reload_profile.setShortcut(QtGui.QKeySequence("F5"))
        self.act_reload_profile.setShortcutContext(QtCore.Qt.ApplicationShortcut)
        self.act_reload_profile.triggered.connect(self.reload_profile)
        self.addAction(self.act_reload_profile)
        toolbar.addAction(self.act_reload_profile)
        # Recharger
        self.act_reload_profile.setToolTip("Recharger")
        self.act_reload_profile.setStatusTip("Recharger")

        # Barre de statut pour les messages utilisateur
        status = QtWidgets.QStatusBar()
        status.setObjectName("StatusBar")
        status.setSizeGripEnabled(False)
        self.setStatusBar(status)

        # Onglets
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setObjectName("ControlTabs")
        self.tabs.setTabBarAutoHide(False)
        self.tabs.setMovable(False)
        self.tabs.setDocumentMode(True)

        self.tab_camera = CameraTab()
        self.tab_geometry = GeometryTab()
        self.tab_appearance = AppearanceTab()
        self.tab_dynamics = DynamicsTab()
        self.tab_distribution = DistributionTab()
        self.tab_system = SystemTab()
        self.tab_controller = LinkControllerTab()

        for tab in [
            self.tab_camera,
            self.tab_geometry,
            self.tab_appearance,
            self.tab_dynamics,
            self.tab_distribution,
            self.tab_system,
            self.tab_controller,
        ]:
            tab.changed.connect(self.on_delta)

        self.tab_camera.attach_subprofile_manager(self.subprofile_mgr)
        self.tab_geometry.attach_subprofile_manager(self.subprofile_mgr)
        self.tab_appearance.attach_subprofile_manager(self.subprofile_mgr)
        self.tab_dynamics.attach_subprofile_manager(self.subprofile_mgr)
        self.tab_distribution.attach_subprofile_manager(self.subprofile_mgr)
        self.tab_system.attach_subprofile_manager(self.subprofile_mgr)
        self.tab_controller.attach_subprofile_manager(self.subprofile_mgr)

        self.tab_geometry.topologyChanged.connect(self.on_topology_changed)

        self.tabs.addTab(self.tab_camera, "Caméra")
        self.tabs.addTab(self.tab_geometry, "Géométrie")
        self.tabs.addTab(self.tab_appearance, "Apparence")
        self.tabs.addTab(self.tab_dynamics, "Dynamique")
        self.tabs.addTab(self.tab_distribution, "Distribution")
        self.tabs.addTab(self.tab_system, "Système")
        self.tabs.addTab(self.tab_controller, "Link to Controller")

        bar = self.tabs.tabBar()
        bar.setExpanding(True)                 # <— onglets étirés sur la largeur disponible
        bar.setElideMode(QtCore.Qt.ElideNone)

        self.tabs.setUsesScrollButtons(False)  # pas de flèches en mode expanding



        # Habillage principal
        shell = QtWidgets.QWidget()
        shell.setObjectName("CardContainer")
        shell_layout = QtWidgets.QVBoxLayout(shell)
        shell_layout.setContentsMargins(24, 24, 24, 24)
        shell_layout.setSpacing(18)

        banner = self._build_profile_banner()
        shell_layout.addWidget(banner)

        card = QtWidgets.QFrame()
        card.setObjectName("Card")
        card.setGraphicsEffect(self._make_shadow(blur=36, offset=12))
        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(12)
        card_layout.addWidget(self.tabs)
        shell_layout.addWidget(card, 1)

        self.setCentralWidget(shell)

        # Fenêtre
        self.resize(780, 920)
        geometry = screen.availableGeometry()
        self.move(
            geometry.x() + geometry.width() - self.width(),
            geometry.y() + (geometry.height() - self.height()) // 2,
        )
        self.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, True)
        self.show()

        # État initial
        self.refresh_profiles(select=self.current_profile)
        if self.current_profile:
            self.load_profile(self.current_profile)
        else:
            self._update_profile_banner()

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
                index = self.cb_profiles.findText(target)
                if index != -1:
                    self.cb_profiles.setCurrentIndex(index)
            else:
                self.cb_profiles.setCurrentIndex(0)
        finally:
            self._updating_profiles = False
        self._update_profile_banner()

    def on_profile_selected(self, name: str):
        if self._updating_profiles or self._loading_profile:
            return
        if name:
            self.load_profile(name)

    def load_profile(self, name: str):
        self._loading_profile = True
        try:
            profile = self.profile_mgr.get_profile(name)
            self.state = {
                key: (value.copy() if isinstance(value, dict) else value)
                for key, value in profile.items()
            }
            self._migrate_state(self.state)
            self.tab_camera.set_defaults(self.state.get("camera"))
            self.tab_geometry.set_defaults(self.state.get("geometry"))
            self.tab_appearance.set_defaults(self.state.get("appearance"))
            self.tab_dynamics.set_defaults(self.state.get("dynamics"))
            self.tab_distribution.set_defaults(
                self.state.get("distribution"),
                self.state.get("mask"),
            )
            self.tab_system.set_defaults(self.state.get("system"))
            self.tab_controller.set_defaults(self.state.get("controller"))
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
            distribution=self.tab_distribution.collect_distribution(),
            mask=self.tab_distribution.collect_mask(),
            system=self.tab_system.collect(),
            controller=self.tab_controller.collect(),
            donut=copy.deepcopy(self.state.get("donut", default_donut_config())),
        )

    def save_profile(self):
        if not self.current_profile:
            self.save_profile_as()
            return
        self.state = self.collect_state()
        try:
            self.profile_mgr.save_profile(self.current_profile, self.state)
        except Exception as exc:  # pragma: no cover - retour utilisateur
            QtWidgets.QMessageBox.warning(self, "Erreur", str(exc))
            return
        self.set_dirty(False)
        self.statusBar().showMessage(f"Profil '{self.current_profile}' enregistré", 3000)

    def save_profile_as(self):
        name, ok = QtWidgets.QInputDialog.getText(
            self,
            "Sauver le profil",
            "Nom du profil :",
            text=self.current_profile or "",
        )
        if not ok:
            return
        name = name.strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Nom invalide", "Veuillez saisir un nom de profil.")
            return
        if self.profile_mgr.has_profile(name) and name != self.current_profile:
            response = QtWidgets.QMessageBox.question(
                self,
                "Écraser le profil",
                f"Le profil '{name}' existe déjà. Voulez-vous l'écraser ?",
            )
            if response != QtWidgets.QMessageBox.Yes:
                return
        state = self.collect_state()
        try:
            self.profile_mgr.save_profile(name, state)
        except Exception as exc:  # pragma: no cover - retour utilisateur
            QtWidgets.QMessageBox.warning(self, "Erreur", str(exc))
            return
        self.state = state
        self.current_profile = name
        self.refresh_profiles(select=name)
        self.set_dirty(False)
        self.statusBar().showMessage(f"Profil '{name}' enregistré", 3000)

    def rename_profile(self):
        if self.current_profile == ProfileManager.DEFAULT_PROFILE:
            QtWidgets.QMessageBox.information(
                self,
                "Action impossible",
                "Le profil par défaut ne peut pas être renommé.",
            )
            return
        name, ok = QtWidgets.QInputDialog.getText(
            self,
            "Renommer le profil",
            "Nouveau nom :",
            text=self.current_profile,
        )
        if not ok:
            return
        name = name.strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Nom invalide", "Veuillez saisir un nom de profil.")
            return
        if self.profile_mgr.has_profile(name):
            QtWidgets.QMessageBox.warning(
                self,
                "Nom déjà utilisé",
                "Un profil avec ce nom existe déjà.",
            )
            return
        try:
            self.profile_mgr.rename_profile(self.current_profile, name)
        except Exception as exc:  # pragma: no cover - retour utilisateur
            QtWidgets.QMessageBox.warning(self, "Erreur", str(exc))
            return
        self.current_profile = name
        self.refresh_profiles(select=name)
        self.set_dirty(False)
        self.statusBar().showMessage(f"Profil renommé en '{name}'", 3000)

    def delete_profile(self):
        if self.current_profile == ProfileManager.DEFAULT_PROFILE:
            QtWidgets.QMessageBox.information(
                self,
                "Action impossible",
                "Le profil par défaut ne peut pas être supprimé.",
            )
            return
        response = QtWidgets.QMessageBox.question(
            self,
            "Supprimer le profil",
            f"Voulez-vous vraiment supprimer le profil '{self.current_profile}' ?",
        )
        if response != QtWidgets.QMessageBox.Yes:
            return
        try:
            self.profile_mgr.delete_profile(self.current_profile)
        except Exception as exc:  # pragma: no cover - retour utilisateur
            QtWidgets.QMessageBox.warning(self, "Erreur", str(exc))
            return
        self.statusBar().showMessage("Profil supprimé", 3000)
        self.current_profile = ProfileManager.DEFAULT_PROFILE
        self.refresh_profiles(select=self.current_profile)
        self.load_profile(self.current_profile)

    def set_dirty(self, dirty: bool):
        self._dirty = dirty
        self.update_window_title()
        self.act_rename_profile.setEnabled(
            self.current_profile != ProfileManager.DEFAULT_PROFILE
        )
        self.act_delete_profile.setEnabled(
            self.current_profile != ProfileManager.DEFAULT_PROFILE
        )
        self._update_profile_banner()

    def update_window_title(self):
        suffix = ""
        if self.current_profile:
            suffix = f" — {self.current_profile}{'*' if self._dirty else ''}"
        self.setWindowTitle("Dyxten — Control v2" + suffix)

    def _apply_transparency(self):
        try:
            self.view_win.set_transparent(
                bool(self.state.get("system", {}).get("transparent", True))
            )
        except Exception:  # pragma: no cover - garde-fou plateforme
            pass

    def on_delta(self, delta: dict):
        for key, value in delta.items():
            if key == "donut":
                self.state["donut"] = sanitize_donut_state(value)
                continue
            if isinstance(value, dict):
                self.state.setdefault(key, {}).update(value)
            else:
                self.state[key] = value
        self._apply_transparency()
        if not self._loading_profile:
            self.set_dirty(
                not self.profile_mgr.profile_equals(self.current_profile, self.state)
            )
        self.push_params()

    def on_topology_changed(self, topo: str):  # pragma: no cover - extension future
        if topo in FLAT_TOPOLOGIES:
            self.tab_camera.set_tilt_to_max()

    def push_params(self):
        view = getattr(self.view_win, "view", None)
        if view is None:
            return
        try:
            view.set_params(self.state)
        except Exception:
            return
        try:
            self.view_win.update_donut_buttons(view.current_donut())
        except Exception:
            pass

    def _on_view_ready(self, ok: bool):
        # Legacy method kept for compatibility with existing profiles. The view
        # is always ready in the Python renderer so we simply push parameters.
        if ok:
            self.push_params()

    def _migrate_state(self, state: dict):
        dynamics = state.setdefault("dynamics", {})
        distribution = state.get("distribution", {})
        for axis in ("X", "Y", "Z"):
            key = f"orient{axis}Deg"
            if key in distribution and key not in dynamics:
                dynamics[key] = distribution.pop(key)
        defaults = DEFAULTS["dynamics"]
        for axis in ("X", "Y", "Z"):
            max_key = f"rot{axis}Max"
            if max_key not in dynamics:
                dynamics[max_key] = defaults.get(max_key, 360.0)
        state["donut"] = sanitize_donut_state(state.get("donut"))

    # ----------------------------------------------------------------- thème & bannière
    def _apply_theme(self):
        accent = "#536dfe"
        accent_alt = "#7c4dff"
        accent_rgb = "83, 109, 254"
        parts = [
            "QMainWindow {",
            "    background-color: #15151f;",
            "    color: #f5f6ff;",
            "}",
            "QToolBar {",
            "    background: #1d1d29;",
            "    border: none;",
            "    border-bottom: 1px solid rgba(255, 255, 255, 0.08);",
            "    padding: 8px 8px;",
            "    spacing: 6px;",
            "}",
            "QToolButton {",
            "    color: #f5f6ff;",
            "    background: transparent;",
            "    border-radius: 8px;",
            "    padding: 6px 12px;",
            "    font-weight: 500;",
            "}",
            f"QToolButton:hover {{",
            f"    background: rgba({accent_rgb}, 0.14);",
            "}",
            f"QToolButton:pressed {{",
            f"    background: rgba({accent_rgb}, 0.22);",
            "}",
            "QLabel {",
            "    color: #f5f6ff;",
            "}",
            "QMenu {",
            "    background-color: #ffffff;",
            "    color: #15151f;",
            "    border: 1px solid rgba(0, 0, 0, 0.15);",
            "}",
            "QMenu::item:selected {",
            "    background-color: rgba(83, 109, 254, 0.18);",
            "    color: #15151f;",
            "}",
            "QComboBox {",
            "    background: #ffffff;",
            "    border: 1px solid rgba(0, 0, 0, 0.15);",
            "    border-radius: 8px;",
            "    padding: 4px 10px;",
            "    color: #15151f;",
            "    min-height: 28px;",
            "}",
            f"QComboBox:hover {{",
            f"    border: 1px solid {accent};",
            "}",
            "QComboBox::drop-down {",
            "    border: none;",
            "}",
            "QComboBox QAbstractItemView {",
            "    background: #ffffff;",
            "    border: 1px solid rgba(0, 0, 0, 0.15);",
            "    selection-background-color: rgba(83, 109, 254, 0.25);",
            "    selection-color: #15151f;",
            "    color: #15151f;",
            "}",
            "QLineEdit, QSpinBox, QDoubleSpinBox, QAbstractSpinBox, QTextEdit, QPlainTextEdit {",
            "    background: #1f1f2d;",
            "    border: 1px solid rgba(255, 255, 255, 0.08);",
            "    border-radius: 8px;",
            "    padding: 4px 8px;",
            "    color: #f5f6ff;",
            "}",
            f"QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QAbstractSpinBox:hover, QTextEdit:hover, QPlainTextEdit:hover {{",
            f"    border: 1px solid {accent};",
            "}",
            "QCheckBox, QRadioButton {",
            "    color: #f5f6ff;",
            "}",
            "QGroupBox {",
            "    border: 1px solid rgba(255, 255, 255, 0.08);",
            "    border-radius: 12px;",
            "    margin-top: 18px;",
            "    padding: 12px;",
            "}",
            "QGroupBox::title {",
            "    subcontrol-origin: margin;",
            "    left: 16px;",
            "    padding: 0 6px;",
            "}",
            "QStatusBar {",
            "    background: #1d1d29;",
            "    border-top: 1px solid rgba(255, 255, 255, 0.08);",
            "    color: #c8c9d1;",
            "}",
            "QStatusBar::item { border: none; }",
            "QWidget#CardContainer {",
            "    background: transparent;",
            "}",

            "QFrame#Card {",
            "    background: #1b1b28;",
            "    border-radius: 20px;",
            "    border-left: 1px solid rgba(255, 255, 255, 0.06);",
            "    border-right: 1px solid rgba(255, 255, 255, 0.06);",
            "    border-bottom: 1px solid rgba(255, 255, 255, 0.06);",
            "    border-top: none;",                      # <— plus de trait au-dessus des tabs
            "}",

            "QTabWidget#ControlTabs::pane {",
            "    border-top: none;",                         # supprime la ligne du haut
            "    border-bottom: 1px solid rgba(255,255,255,0.08);",  # ajoute la ligne sous les tabs
            "    margin-top: 0;",                            # supprime l’espace au-dessus
            "}",

            "QTabBar::tab {",
            "    background: transparent;",
            "    border: 1px solid #444;",
            "    padding: 6px 1px;",      # marges internes réduites
            "    margin-right: 4px;",      # espace entre onglets
            "    border-radius: 4px;",
            "    min-height: 28px;",       # évite coupe verticale
            "    min-width: 48px;",        # évite coupe horizontale
            "    color: #b4b7c9;",
            "    font-weight: 400;",
            "    margin-bottom: -1px;",   # chevauche la ligne du pane pour éviter double-trait

            "}",

            "QTabBar::tab:selected {",
            "    background: rgba(83,109,254,0.32);",
            "    color: #ffffff;",
            "    border-bottom: 1px solid transparent;",   # masque la jonction avec la ligne du pane
            "}",

            f"QTabBar::tab:hover {{",
            f"    background: rgba({accent_rgb}, 0.18);",
            "    color: #f5f6ff;",
            "}",
            "QScrollArea {",
            "    background: transparent;",
            "    border: none;",
            "}",
            "QScrollArea > QWidget > QWidget {",
            "    background: transparent;",
            "}",
            "QLabel#DirtyBadge {",
            "    background: #ff6b6b;",
            "    color: #ffffff;",
            "    padding: 4px 12px;",
            "    border-radius: 12px;",
            "    font-weight: 600;",
            "}",
            f"QFrame#ProfileBanner {{",
            f"    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {accent}, stop:1 {accent_alt});",
            "    border-radius: 22px;",
            "    color: #ffffff;",
            "}",
            "QLabel#BannerTitle {",
            "    font-size: 20px;",
            "    font-weight: 600;",
            "    color: #ffffff;",
            "}",
            "QLabel#BannerSubtitle {",
            "    color: rgba(255, 255, 255, 0.85);",
            "    font-size: 13px;",
            "}",
            "QPushButton {",
            "    background: rgba(255, 255, 255, 0.06);",
            "    color: #f5f6ff;",
            "    border: 1px solid transparent;",
            "    border-radius: 10px;",
            "    padding: 6px 14px;",
            "    font-weight: 500;",
            "}",
            f"QPushButton:hover {{",
            f"    border: 1px solid {accent};",
            "}",
            f"QPushButton:pressed {{",
            f"    background: rgba({accent_rgb}, 0.18);",
            "}",
        ]
        self.setStyleSheet("\n".join(parts))

    def _build_profile_banner(self) -> QtWidgets.QFrame:
        banner = QtWidgets.QFrame()
        banner.setObjectName("ProfileBanner")
        banner.setMinimumHeight(96)
        layout = QtWidgets.QHBoxLayout(banner)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(18)

        icon_label = QtWidgets.QLabel()
        icon_label.setAlignment(QtCore.Qt.AlignCenter)
        icon = self.style().standardIcon(QtWidgets.QStyle.SP_FileDialogDetailedView)
        icon_label.setPixmap(icon.pixmap(40, 40))
        layout.addWidget(icon_label)

        text_container = QtWidgets.QVBoxLayout()
        text_container.setSpacing(6)

        self.lbl_profile_title = QtWidgets.QLabel()
        self.lbl_profile_title.setObjectName("BannerTitle")
        text_container.addWidget(self.lbl_profile_title)

        self.lbl_profile_subtitle = QtWidgets.QLabel()
        self.lbl_profile_subtitle.setObjectName("BannerSubtitle")
        self.lbl_profile_subtitle.setWordWrap(True)
        text_container.addWidget(self.lbl_profile_subtitle)

        layout.addLayout(text_container, stretch=1)

        self.lbl_dirty_badge = QtWidgets.QLabel()
        self.lbl_dirty_badge.setObjectName("DirtyBadge")
        self.lbl_dirty_badge.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_dirty_badge.hide()
        layout.addWidget(
            self.lbl_dirty_badge,
            alignment=QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter,
        )

        banner.setGraphicsEffect(self._make_shadow(blur=40, offset=18))
        return banner

    def _make_shadow(self, blur: int, offset: int) -> QtWidgets.QGraphicsDropShadowEffect:
        effect = QtWidgets.QGraphicsDropShadowEffect(self)
        effect.setBlurRadius(blur)
        effect.setOffset(0, offset)
        effect.setColor(QtGui.QColor(0, 0, 0, 110))
        return effect

    def _update_profile_banner(self):
        if not hasattr(self, "lbl_profile_title"):
            return

        profile_name = self.current_profile or "—"
        if profile_name == ProfileManager.DEFAULT_PROFILE:
            title = "Profil actif : Défaut"
            subtitle = "Ce profil de base se charge automatiquement à chaque démarrage."
        elif profile_name in PROFILE_PRESET_DESCRIPTIONS:
            title = f"Profil prédéfini : {profile_name}"
            subtitle = PROFILE_PRESET_DESCRIPTIONS[profile_name]
        else:
            title = f"Profil actif : {profile_name}"
            subtitle = "Vos réglages personnalisés sont appliqués à la scène courante."

        if self._dirty:
            subtitle = "Des changements non sauvegardés sont prêts à être enregistrés."
            self.lbl_dirty_badge.setText("Modifications en cours")
            self.lbl_dirty_badge.show()
        else:
            self.lbl_dirty_badge.hide()

        self.lbl_profile_title.setText(title)
        self.lbl_profile_subtitle.setText(subtitle)
