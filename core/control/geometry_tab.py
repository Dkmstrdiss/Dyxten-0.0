from PyQt5 import QtWidgets, QtCore, QtGui
from typing import Tuple

from .widgets import row, SubProfilePanel
from .config import DEFAULTS, TOOLTIPS
from .link_registry import register_linkable_widget

try:
    from ..topology_registry import get_topology_library
except ImportError:  # pragma: no cover - compat exécution directe
    from core.topology_registry import get_topology_library  # type: ignore


_JSON_LIBRARY = get_topology_library()

try:
    from ..topology_registry import TopologyDefinition, get_topology_library
except ImportError:  # pragma: no cover - compat exécution directe
    from core.topology_registry import TopologyDefinition, get_topology_library  # type: ignore


_JSON_LIBRARY = get_topology_library()

def _all_topologies() -> list[str]:
    names = list(_JSON_LIBRARY.names())
    if names:
        return names
    defaults = DEFAULTS.get("geometry", {})
    fallback = defaults.get("topology")
    if isinstance(fallback, str) and fallback:
        return [fallback]
    return []


def _grouped_topologies() -> Tuple[Tuple[str, Tuple[TopologyDefinition, ...]], ...]:
    groups = _JSON_LIBRARY.grouped_definitions()
    if groups:
        return groups
    names = _all_topologies()
    if names:
        definition = _JSON_LIBRARY.get(names[0])
        if definition is not None:
            return ((definition.category or "Bibliothèque JSON", (definition,)),)
    return tuple()


def _param_group(name: str) -> str:
    global_params = {
        "R",
        "lat",
        "lon",
        "N",
        "phi_g",
        "R_major",
        "R_major2",
        "r_minor",
        "eps1",
        "eps2",
        "ax",
        "ay",
        "az",
        "geo_level",
        "mobius_w",
        "trunc_ratio",
        "stellated_scale",
        "arch_a",
        "arch_b",
        "theta_max",
        "log_a",
        "log_b",
        "rose_k",
        "vogel_k",
        "se_n1",
        "se_n2",
        "half_height",
    }
    if name in global_params:
        return "Paramètres globaux"
    if name.startswith("sf2_") or name.startswith("sf3_") or name == "sf3_scale":
        return "Superformules"
    if name in {"density_pdf", "poisson_dmin", "lissajous_a", "lissajous_b", "lissajous_phase", "weight_map"}:
        return "Répartitions paramétriques"
    if name in {
        "helix_r",
        "helix_pitch",
        "helix_turns",
        "lissajous3d_Ax",
        "lissajous3d_Ay",
        "lissajous3d_Az",
        "lissajous3d_wx",
        "lissajous3d_wy",
        "lissajous3d_wz",
        "lissajous3d_phi",
        "viviani_a",
        "stream_N",
        "stream_steps",
        "lic_N",
        "lic_steps",
        "lic_h",
        "torus_knot_p",
        "torus_knot_q",
        "strip_w",
        "strip_n",
    }:
        return "Courbes & flux"
    if name.startswith("noisy_") or name.startswith("blob_") or name.startswith("gyroid_") or name.startswith("schwarz_") or name.startswith("metaballs_") or name in {"heart_scale", "df_ops"}:
        return "Surfaces implicites & bruit"
    if name.startswith("poly") or name.startswith("geo_") or name in {
        "poly_layers",
        "poly_link_steps",
        "polyhedron_data",
        "rings_count",
        "ring_points",
        "hex_step",
        "hex_nx",
        "hex_ny",
        "voronoi_N",
        "voronoi_bbox",
        "rgg_nodes",
        "rgg_radius",
    }:
        return "Polyèdres & graphes"
    return "Autres paramètres"


PARAM_SPECS = {
    "R": dict(type="double", label="Taille générale", tip="geometry.R", min=0.05, max=10.0, step=0.05, decimals=3),
    "lat": dict(type="int", label="Anneaux horizontaux", tip="geometry.lat", min=3, max=1024),
    "lon": dict(type="int", label="Colonnes verticales", tip="geometry.lon", min=3, max=1024),
    "N": dict(type="int", label="Nombre de points", tip="geometry.N", min=10, max=500000),
    "phi_g": dict(type="double", label="Rotation progressive", tip="geometry.phi_g", min=0.0, max=6.283185, step=0.0001, decimals=5),
    "R_major": dict(type="double", label="Rayon externe (tore)", tip="geometry.R_major", min=0.05, max=10.0, step=0.05, decimals=3),
    "R_major2": dict(type="double", label="Rayon externe 2 (tore)", tip="geometry.R_major2", min=0.05, max=10.0, step=0.05, decimals=3),
    "r_minor": dict(type="double", label="Épaisseur du tore", tip="geometry.r_minor", min=0.01, max=5.0, step=0.05, decimals=3),
    "eps1": dict(type="double", label="Arrondi horizontal", tip="geometry.eps1", min=0.2, max=6.0, step=0.05, decimals=3),
    "eps2": dict(type="double", label="Arrondi vertical", tip="geometry.eps2", min=0.2, max=6.0, step=0.05, decimals=3),
    "ax": dict(type="double", label="Étirer X", tip="geometry.ax", min=0.1, max=5.0, step=0.05, decimals=3),
    "ay": dict(type="double", label="Étirer Y", tip="geometry.ay", min=0.1, max=5.0, step=0.05, decimals=3),
    "az": dict(type="double", label="Étirer Z", tip="geometry.az", min=0.1, max=5.0, step=0.05, decimals=3),
    "geo_level": dict(type="int", label="Niveau géodésique", tip="geometry.geo_level", min=0, max=6),
    "mobius_w": dict(type="double", label="Largeur du ruban", tip="geometry.mobius_w", min=0.05, max=2.0, step=0.01, decimals=3),
    "trunc_ratio": dict(type="double", label="Facteur de tronquage", tip="geometry.trunc_ratio", min=0.05, max=0.45, step=0.01, decimals=3),
    "stellated_scale": dict(type="double", label="Allongement des pointes", tip="geometry.stellated_scale", min=0.8, max=2.5, step=0.01, decimals=3),

    "arch_a": dict(type="double", label="Archimède a", tip="geometry.arch_a", min=0.0, max=5.0, step=0.05, decimals=3),
    "arch_b": dict(type="double", label="Archimède b", tip="geometry.arch_b", min=0.0, max=5.0, step=0.05, decimals=3),
    "theta_max": dict(type="double", label="Angle maximum", tip="geometry.theta_max", min=0.1, max=50.0, step=0.1, decimals=3),
    "log_a": dict(type="double", label="Log a", tip="geometry.log_a", min=0.01, max=5.0, step=0.01, decimals=3),
    "log_b": dict(type="double", label="Log b", tip="geometry.log_b", min=-2.0, max=2.0, step=0.01, decimals=3),
    "rose_k": dict(type="double", label="Rosace k", tip="geometry.rose_k", min=1.0, max=24.0, step=0.1, decimals=3),
    "sf2_m": dict(type="double", label="Superformule m", tip="geometry.sf2_m", min=0.0, max=64.0, step=0.5, decimals=3),
    "sf2_a": dict(type="double", label="Superformule a", tip="geometry.sf2_a", min=0.01, max=10.0, step=0.01, decimals=3),
    "sf2_b": dict(type="double", label="Superformule b", tip="geometry.sf2_b", min=0.01, max=10.0, step=0.01, decimals=3),
    "sf2_n1": dict(type="double", label="Superformule n1", tip="geometry.sf2_n1", min=0.01, max=10.0, step=0.01, decimals=3),
    "sf2_n2": dict(type="double", label="Superformule n2", tip="geometry.sf2_n2", min=0.01, max=10.0, step=0.01, decimals=3),
    "sf2_n3": dict(type="double", label="Superformule n3", tip="geometry.sf2_n3", min=0.01, max=10.0, step=0.01, decimals=3),
    "density_pdf": dict(type="text", label="Densité radiale", tip="geometry.density_pdf"),
    "poisson_dmin": dict(type="double", label="Distance min", tip="geometry.poisson_dmin", min=0.0, max=2.0, step=0.01, decimals=3),
    "lissajous_a": dict(type="int", label="Lissajous a", tip="geometry.lissajous_a", min=1, max=64),
    "lissajous_b": dict(type="int", label="Lissajous b", tip="geometry.lissajous_b", min=1, max=64),
    "lissajous_phase": dict(type="double", label="Phase (rad)", tip="geometry.lissajous_phase", min=-6.283185, max=6.283185, step=0.01, decimals=3),

    "vogel_k": dict(type="double", label="Spirale k", tip="geometry.vogel_k", min=0.1, max=4.5, step=0.001, decimals=6),
    "se_n1": dict(type="double", label="Superellipsoïde n1", tip="geometry.se_n1", min=0.1, max=10.0, step=0.05, decimals=3),
    "se_n2": dict(type="double", label="Superellipsoïde n2", tip="geometry.se_n2", min=0.1, max=10.0, step=0.05, decimals=3),
    "half_height": dict(type="double", label="Écrasement vertical", tip="geometry.half_height", min=0.1, max=2.0, step=0.05, decimals=3),
    "noisy_amp": dict(type="double", label="Bruit amplitude", tip="geometry.noisy_amp", min=0.0, max=2.0, step=0.01, decimals=3),
    "noisy_freq": dict(type="double", label="Bruit fréquence", tip="geometry.noisy_freq", min=0.1, max=32.0, step=0.1, decimals=3),
    "noisy_gain": dict(type="double", label="Bruit gain", tip="geometry.noisy_gain", min=0.0, max=10.0, step=0.1, decimals=3),
    "noisy_omega": dict(type="double", label="Bruit phase", tip="geometry.noisy_omega", min=0.0, max=6.283185, step=0.01, decimals=3),
    "sph_terms": dict(type="text", label="Harmoniques (l,m,a)", tip="geometry.sph_terms"),
    "weight_map": dict(type="text", label="Carte pondérée", tip="geometry.weight_map"),

    "torus_knot_p": dict(type="int", label="Nœud p", tip="geometry.torus_knot_p", min=1, max=64),
    "torus_knot_q": dict(type="int", label="Nœud q", tip="geometry.torus_knot_q", min=1, max=64),
    "strip_w": dict(type="double", label="Largeur ruban", tip="geometry.strip_w", min=0.05, max=2.0, step=0.01, decimals=3),
    "strip_n": dict(type="int", label="Nombre de torsions", tip="geometry.strip_n", min=1, max=20),

    "blob_noise_amp": dict(type="double", label="Blob amplitude", tip="geometry.blob_noise_amp", min=0.0, max=3.0, step=0.05, decimals=3),
    "blob_noise_scale": dict(type="double", label="Blob échelle", tip="geometry.blob_noise_scale", min=0.1, max=10.0, step=0.05, decimals=3),
    "gyroid_scale": dict(type="double", label="Gyroid échelle", tip="geometry.gyroid_scale", min=0.1, max=5.0, step=0.05, decimals=3),
    "gyroid_thickness": dict(type="double", label="Gyroid épaisseur", tip="geometry.gyroid_thickness", min=0.005, max=1.0, step=0.005, decimals=3),
    "gyroid_c": dict(type="double", label="Gyroid décalage", tip="geometry.gyroid_c", min=-2.0, max=2.0, step=0.01, decimals=3),
    "schwarz_scale": dict(type="double", label="Schwarz échelle", tip="geometry.schwarz_scale", min=0.1, max=5.0, step=0.05, decimals=3),
    "schwarz_iso": dict(type="double", label="Schwarz iso", tip="geometry.schwarz_iso", min=-2.0, max=2.0, step=0.01, decimals=3),
    "heart_scale": dict(type="double", label="Échelle cœur", tip="geometry.heart_scale", min=0.1, max=5.0, step=0.05, decimals=3),
    "polyhedron_data": dict(type="text", label="Polyèdre JSON", tip="geometry.polyhedron_data"),
    "poly_layers": dict(type="int", label="Couches radiales", tip="geometry.poly_layers", min=1, max=16),
    "poly_link_steps": dict(type="int", label="Segments de liaison", tip="geometry.poly_link_steps", min=0, max=64),
    "metaballs_centers": dict(type="text", label="Centres métaballes", tip="geometry.metaballs_centers"),
    "metaballs_radii": dict(type="text", label="Rayons métaballes", tip="geometry.metaballs_radii"),
    "metaballs_iso": dict(type="double", label="Iso métaballes", tip="geometry.metaballs_iso", min=0.0, max=5.0, step=0.05, decimals=3),
    "df_ops": dict(type="text", label="Opérations SDF", tip="geometry.df_ops"),
    "sf3_m1": dict(type="double", label="Superformule m1", tip="geometry.sf3_m1", min=0.0, max=64.0, step=0.5, decimals=3),
    "sf3_m2": dict(type="double", label="Superformule m2", tip="geometry.sf3_m2", min=0.0, max=64.0, step=0.5, decimals=3),
    "sf3_m3": dict(type="double", label="Superformule m3", tip="geometry.sf3_m3", min=0.0, max=64.0, step=0.5, decimals=3),
    "sf3_n1": dict(type="double", label="Superformule n1", tip="geometry.sf3_n1", min=0.01, max=10.0, step=0.01, decimals=3),
    "sf3_n2": dict(type="double", label="Superformule n2", tip="geometry.sf3_n2", min=0.01, max=10.0, step=0.01, decimals=3),
    "sf3_n3": dict(type="double", label="Superformule n3", tip="geometry.sf3_n3", min=0.01, max=10.0, step=0.01, decimals=3),
    "sf3_a": dict(type="double", label="Superformule a", tip="geometry.sf3_a", min=0.01, max=10.0, step=0.01, decimals=3),
    "sf3_b": dict(type="double", label="Superformule b", tip="geometry.sf3_b", min=0.01, max=10.0, step=0.01, decimals=3),
    "sf3_scale": dict(type="double", label="Superformule échelle", tip="geometry.sf3_scale", min=0.1, max=5.0, step=0.05, decimals=3),

    "helix_r": dict(type="double", label="Rayon hélice", tip="geometry.helix_r", min=0.05, max=5.0, step=0.05, decimals=3),
    "helix_pitch": dict(type="double", label="Pas hélice", tip="geometry.helix_pitch", min=0.01, max=2.0, step=0.01, decimals=3),
    "helix_turns": dict(type="double", label="Tours hélice", tip="geometry.helix_turns", min=1.0, max=64.0, step=0.1, decimals=3),
    "lissajous3d_Ax": dict(type="double", label="Amplitude X", tip="geometry.lissajous3d_Ax", min=0.1, max=5.0, step=0.05, decimals=3),
    "lissajous3d_Ay": dict(type="double", label="Amplitude Y", tip="geometry.lissajous3d_Ay", min=0.1, max=5.0, step=0.05, decimals=3),
    "lissajous3d_Az": dict(type="double", label="Amplitude Z", tip="geometry.lissajous3d_Az", min=0.1, max=5.0, step=0.05, decimals=3),
    "lissajous3d_wx": dict(type="int", label="Fréquence X", tip="geometry.lissajous3d_wx", min=1, max=64),
    "lissajous3d_wy": dict(type="int", label="Fréquence Y", tip="geometry.lissajous3d_wy", min=1, max=64),
    "lissajous3d_wz": dict(type="int", label="Fréquence Z", tip="geometry.lissajous3d_wz", min=1, max=64),
    "lissajous3d_phi": dict(type="double", label="Phase globale", tip="geometry.lissajous3d_phi", min=0.0, max=6.283185, step=0.01, decimals=3),
    "viviani_a": dict(type="double", label="Paramètre a", tip="geometry.viviani_a", min=0.1, max=5.0, step=0.05, decimals=3),
    "lic_N": dict(type="int", label="Lignes LIC", tip="geometry.lic_N", min=1, max=256),
    "lic_steps": dict(type="int", label="Étapes LIC", tip="geometry.lic_steps", min=1, max=5000),
    "lic_h": dict(type="double", label="Pas LIC", tip="geometry.lic_h", min=0.001, max=1.0, step=0.001, decimals=4),
    "stream_N": dict(type="int", label="Lignes tore", tip="geometry.stream_N", min=1, max=256),
    "stream_steps": dict(type="int", label="Étapes tore", tip="geometry.stream_steps", min=1, max=5000),
    "geo_graph_level": dict(type="int", label="Niveau graphe", tip="geometry.geo_graph_level", min=0, max=6),
    "rgg_nodes": dict(type="int", label="Noeuds graphe", tip="geometry.rgg_nodes", min=10, max=200000),
    "rgg_radius": dict(type="double", label="Rayon graphe", tip="geometry.rgg_radius", min=0.01, max=5.0, step=0.01, decimals=3),
    "rings_count": dict(type="int", label="Nombre d’anneaux", tip="geometry.rings_count", min=1, max=128),
    "ring_points": dict(type="int", label="Points par anneau", tip="geometry.ring_points", min=3, max=4096),
    "hex_step": dict(type="double", label="Pas hexagonal", tip="geometry.hex_step", min=0.01, max=5.0, step=0.01, decimals=3),
    "hex_nx": dict(type="int", label="Colonnes hex", tip="geometry.hex_nx", min=1, max=256),
    "hex_ny": dict(type="int", label="Lignes hex", tip="geometry.hex_ny", min=1, max=256),
    "voronoi_N": dict(type="int", label="Graines Voronoï", tip="geometry.voronoi_N", min=2, max=5000),
    "voronoi_bbox": dict(type="text", label="Boîte Voronoï", tip="geometry.voronoi_bbox"),
}


class GeometryTab(QtWidgets.QWidget):
    changed = QtCore.pyqtSignal(dict)
    topologyChanged = QtCore.pyqtSignal(str)

    def __init__(self):
        super().__init__()
        defaults = DEFAULTS["geometry"]

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        self._subprofile_panel = SubProfilePanel("Sous-profil géométrie")
        outer.addWidget(self._subprofile_panel)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
            }
            QScrollBar:vertical {
                width: 0px;
                background: transparent;
            }
            QScrollBar::handle:vertical,
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                background: transparent;
                border: none;
                height: 0px;
                margin: 0;
            }
        """)

        container = QtWidgets.QWidget()
        # Ensure the container doesn't force the scroll area to expand the
        # parent window vertically. Give it a minimum vertical size policy
        # so the QScrollArea will provide scrollbars instead of growing the
        # main window to fit all parameter widgets.
        container.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Minimum)
        container.setMinimumHeight(0)
        layout = QtWidgets.QFormLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll.setWidget(container)
        outer.addWidget(scroll, 1)

        desc_frame = QtWidgets.QFrame()
        desc_frame.setObjectName("TopologyDescriptionFrame")
        desc_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        desc_layout = QtWidgets.QVBoxLayout(desc_frame)
        desc_layout.setContentsMargins(12, 8, 12, 8)
        desc_layout.setSpacing(4)
        desc_title = QtWidgets.QLabel("Description")
        desc_title.setObjectName("TopologyDescriptionTitle")
        desc_title.setStyleSheet("font-weight:600;color:#1f3a52;")
        self._desc_label = QtWidgets.QLabel("")
        self._desc_label.setWordWrap(True)
        self._desc_label.setObjectName("TopologyDescriptionLabel")
        desc_layout.addWidget(desc_title)
        desc_layout.addWidget(self._desc_label)
        outer.addWidget(desc_frame)

        desc_frame.setStyleSheet("""
            QFrame#TopologyDescriptionFrame {
                border:1px solid #d6e2ed;
                border-radius:6px;
                background:#ffffff;
            }
            QLabel#TopologyDescriptionLabel {
                color:#2b3f55;
            }
        """)

        self._scroll = scroll
        self._form_layout = layout

        self.param_widgets = {}
        self.param_rows = {}
        self._group_widgets = {}
        self._param_groups = {}

        self.cb_topology = QtWidgets.QComboBox()
        self.cb_topology.setModel(QtGui.QStandardItemModel(self.cb_topology))
        self.cb_topology.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.cb_topology.setView(QtWidgets.QListView())
        self.cb_topology.view().setSpacing(2)
        self._populate_topology_combo()
        all_topos = _all_topologies()
        default_topology = defaults.get("topology", all_topos[0])
        self._select_topology(default_topology)
        row(layout, "Forme de base", self.cb_topology, TOOLTIPS["geometry.topology"],
            lambda: self._reset_topology_choice(default_topology))

        for name, spec in PARAM_SPECS.items():
            group = _param_group(name)
            self._ensure_group_header(group)
            widget = self._create_widget(name, spec, defaults)
            tip_key = spec.get("tip") or f"geometry.{name}"
            tip = TOOLTIPS.get(tip_key, spec.get("tip_text", ""))
            reset_cb = self._reset_factory(name)
            row_widget = row(layout, spec["label"], widget, tip, reset_cb)
            self.param_widgets[name] = widget
            self.param_rows[name] = row_widget
            self._param_groups[name] = group
            self._connect_widget(name, widget, spec)
            if spec.get("type") in {"double", "int"}:
                register_linkable_widget(widget, section="geometry", key=name, tab="Géométrie")

        self.cb_topology.currentIndexChanged.connect(self.on_topology_changed)
        self._apply_topology_state(emit=False)
        self._sync_subprofile_state()

    # ------------------------------------------------------------------ utils
    def _populate_topology_combo(self):
        model: QtGui.QStandardItemModel = self.cb_topology.model()  # type: ignore[assignment]
        model.clear()
        header_font = QtGui.QFont(self.font())
        header_font.setBold(True)
        groups = _grouped_topologies()
        if not groups:
            header = QtGui.QStandardItem("Topologies disponibles")
            header.setFlags(QtCore.Qt.NoItemFlags)
            header.setFont(header_font)
            header.setForeground(QtGui.QBrush(QtGui.QColor(76, 94, 111)))
            header.setBackground(QtGui.QBrush(QtGui.QColor(238, 242, 247)))
            model.appendRow(header)
            for name in _all_topologies():
                item = QtGui.QStandardItem(name)
                item.setEditable(False)
                item.setData(name, QtCore.Qt.UserRole)
                model.appendRow(item)
            return

        for category, definitions in groups:
            header_label = category or "Bibliothèque JSON"
            header = QtGui.QStandardItem(header_label)
            header.setFlags(QtCore.Qt.NoItemFlags)
            header.setFont(header_font)
            header.setForeground(QtGui.QBrush(QtGui.QColor(76, 94, 111)))
            header.setBackground(QtGui.QBrush(QtGui.QColor(238, 242, 247)))
            model.appendRow(header)
            for definition in definitions:
                item = QtGui.QStandardItem(definition.label or definition.name)
                item.setEditable(False)
                item.setData(definition.name, QtCore.Qt.UserRole)
                model.appendRow(item)
    def _first_selectable_index(self) -> int:
        model: QtGui.QStandardItemModel = self.cb_topology.model()  # type: ignore[assignment]
        for row in range(model.rowCount()):
            item = model.item(row)
            if not item:
                continue
            data = item.data(QtCore.Qt.UserRole)
            if data:
                return row
        return -1

    def _select_topology(self, name: str):
        model: QtGui.QStandardItemModel = self.cb_topology.model()  # type: ignore[assignment]
        target = -1
        for row in range(model.rowCount()):
            item = model.item(row)
            if not item:
                continue
            data = item.data(QtCore.Qt.UserRole)
            if data == name:
                target = row
                break
        if target == -1:
            target = self._first_selectable_index()
        if target != -1:
            with QtCore.QSignalBlocker(self.cb_topology):
                self.cb_topology.setCurrentIndex(target)

    def _current_topology(self) -> str:
        data = self.cb_topology.currentData(QtCore.Qt.UserRole)
        all_names = _all_topologies()
        if not all_names:
            return ""
        if isinstance(data, str) and data in all_names:
            return data
        text = self.cb_topology.currentText()
        if text in all_names:
            return text
        defaults = DEFAULTS.get("geometry", {})
        candidate = defaults.get("topology")
        if isinstance(candidate, str) and candidate in all_names:
            return candidate
        return all_names[0]

    def _reset_topology_choice(self, name: str):
        self._select_topology(name)
        self.emit_delta()

    def _create_widget(self, name, spec, defaults):
        if spec["type"] == "double":
            w = QtWidgets.QDoubleSpinBox()
            w.setRange(spec.get("min", -1e9), spec.get("max", 1e9))
            w.setDecimals(spec.get("decimals", 3))
            w.setSingleStep(spec.get("step", 0.1))
            w.setValue(float(defaults.get(name, spec.get("default", 0.0))))
            return w
        if spec["type"] == "int":
            w = QtWidgets.QSpinBox()
            w.setRange(spec.get("min", -1000000), spec.get("max", 1000000))
            w.setValue(int(defaults.get(name, spec.get("default", 0))))
            return w
        if spec["type"] == "text":
            w = QtWidgets.QLineEdit()
            w.setText(str(defaults.get(name, spec.get("default", ""))))
            w.setClearButtonEnabled(True)
            return w
        raise ValueError(f"Type de paramètre inconnu: {spec['type']}")

    def _reset_factory(self, name):
        def _reset():
            defaults = DEFAULTS["geometry"]
            widget = self.param_widgets[name]
            value = defaults.get(name)
            if isinstance(widget, QtWidgets.QDoubleSpinBox):
                widget.setValue(float(value))
            elif isinstance(widget, QtWidgets.QSpinBox):
                widget.setValue(int(value))
            else:
                widget.setText(str(value or ""))
            self.emit_delta()
        return _reset

    def _connect_widget(self, name, widget, spec):
        if isinstance(widget, QtWidgets.QDoubleSpinBox) or isinstance(widget, QtWidgets.QSpinBox):
            widget.valueChanged.connect(self.emit_delta)
        elif isinstance(widget, QtWidgets.QLineEdit):
            widget.editingFinished.connect(self.emit_delta)

    def _ensure_group_header(self, group: str):
        if not group:
            return
        if group in self._group_widgets:
            return
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(0, 12, 0, 6)
        layout.setSpacing(4)
        label = QtWidgets.QLabel(group)
        label.setObjectName("ParamGroupLabel")
        label.setStyleSheet("font-weight:600;color:#1f3a52;")
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        line.setStyleSheet("color:#d6e2ed;")
        layout.addWidget(label)
        layout.addWidget(line)
        self._form_layout.addRow(container)
        self._group_widgets[group] = container

    def _apply_definition_defaults(self, topology: str) -> None:
        definition = _JSON_LIBRARY.get(topology)
        if definition is None:
            return
        defaults = DEFAULTS.get("geometry", {})
        for name in definition.parameters:
            widget = self.param_widgets.get(name)
            if widget is None:
                continue
            value = definition.defaults.get(name, defaults.get(name))
            if value is None:
                continue
            with QtCore.QSignalBlocker(widget):
                if isinstance(widget, QtWidgets.QDoubleSpinBox):
                    widget.setValue(float(value))
                elif isinstance(widget, QtWidgets.QSpinBox):
                    widget.setValue(int(value))
                else:
                    widget.setText(str(value))


    # ---------------------------------------------------------------- interface
    def _apply_topology_state(self, emit=True):
        topology = self._current_topology()
        active = set(self._active_param_names(topology))
        for name, row_widget in self.param_rows.items():
            visible = name in active
            row_widget.setVisible(visible)
            label = getattr(row_widget, "_form_label", None)
            if label is not None:
                label.setVisible(visible)
            widget = self.param_widgets[name]
            widget.setEnabled(visible)
        for group, widget in self._group_widgets.items():
            visible = any(
                self.param_rows[param].isVisible()
                for param, grp in self._param_groups.items()
                if grp == group
            )
            widget.setVisible(visible)
        if emit:
            self.topologyChanged.emit(topology)
            self.emit_delta()
        self._update_description(topology)

    def on_topology_changed(self, *args):
        topology = self._current_topology()
        self._apply_definition_defaults(topology)
        self._apply_topology_state(True)
        self._sync_subprofile_state()

    def collect(self):
        data = {"topology": self._current_topology()}
        for name, widget in self.param_widgets.items():
            if isinstance(widget, QtWidgets.QDoubleSpinBox):
                data[name] = widget.value()
            elif isinstance(widget, QtWidgets.QSpinBox):
                data[name] = widget.value()
            else:
                data[name] = widget.text()
        return data

    def attach_subprofile_manager(self, manager):
        self._subprofile_panel.bind(
            manager=manager,
            section="geometry",
            defaults=DEFAULTS["geometry"],
            collect_cb=self.collect,
            apply_cb=self.set_defaults,
            on_change=self.emit_delta,
        )
        self._sync_subprofile_state()

    def _active_param_names(self, topology=None):
        if topology is None:
            topology = self._current_topology()
        definition = _JSON_LIBRARY.get(topology)
        if definition is None:
            return []
        return [name for name in definition.parameters if name in self.param_widgets]

    def set_defaults(self, cfg):
        cfg = cfg or {}
        defaults = DEFAULTS["geometry"]
        all_topos = _all_topologies()
        if not all_topos:
            return
        target = cfg.get("topology", defaults.get("topology", all_topos[0]))
        self._select_topology(target)
        for name, widget in self.param_widgets.items():
            val = cfg.get(name, defaults.get(name))
            with QtCore.QSignalBlocker(widget):
                if isinstance(widget, QtWidgets.QDoubleSpinBox):
                    widget.setValue(float(val))
                elif isinstance(widget, QtWidgets.QSpinBox):
                    widget.setValue(int(val))
                else:
                    widget.setText(str(val or ""))
        self._apply_topology_state(emit=False)
        self._sync_subprofile_state()

    def set_enabled(self, context: dict):
        pass

    def emit_delta(self, *args):
        self._sync_subprofile_state()
        self.changed.emit({"geometry": self.collect()})

    def _update_description(self, topology: str):
        definition = _JSON_LIBRARY.get(topology)
        if definition is not None:
            text = definition.description or f"Topologie chargée depuis {definition.path.name}."
        else:
            text = "Sélectionnez une topologie pour afficher son descriptif."
        self._desc_label.setText(text)

    def _sync_subprofile_state(self):
        if hasattr(self, "_subprofile_panel") and self._subprofile_panel is not None:
            self._subprofile_panel.sync_from_data(self.collect())
