
from PyQt5 import QtWidgets, QtCore
from .widgets import row, SubProfilePanel
from .config import DEFAULTS, TOOLTIPS
from .link_registry import register_linkable_widget

class SystemTab(QtWidgets.QWidget):
    changed = QtCore.pyqtSignal(dict)
    def __init__(self):
        super().__init__()
        d = DEFAULTS["system"]

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        self._subprofile_panel = SubProfilePanel("Sous-profil système")
        outer.addWidget(self._subprofile_panel)

        container = QtWidgets.QWidget()
        fl = QtWidgets.QFormLayout(container)
        fl.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(container)
        self.sp_Nmax = QtWidgets.QSpinBox(); self.sp_Nmax.setRange(100,500000); self.sp_Nmax.setValue(d["Nmax"])
        self.sp_dpr  = QtWidgets.QDoubleSpinBox(); self.sp_dpr.setRange(1.0,2.0); self.sp_dpr.setSingleStep(0.1); self.sp_dpr.setValue(d["dprClamp"])
    # Sliders retirés: gravité/anneau/orbite (désactivés dans la vue)
        self._button_size_widget, self._button_size_slider, self._button_size_spin = self._create_button_size_controls(d.get("donutButtonSize", 80))
        self._radius_ratio_widget, self._radius_ratio_slider, self._radius_ratio_spin = self._create_radius_ratio_controls(d.get("donutRadiusRatio", 0.35))
        self._circle_controls = self._create_circle_controls(d.get("markerCircles", {}))
        self.chk_depthSort = QtWidgets.QCheckBox(); self.chk_depthSort.setChecked(d["depthSort"])
        self.chk_transparent = QtWidgets.QCheckBox(); self.chk_transparent.setChecked(d["transparent"])
        
        # Menu déroulant unique pour accrochage/décrochage
        self.combo_orbit_mode = QtWidgets.QComboBox()
        self.combo_orbit_mode.addItems(["default", "none"])
        # Si les deux modes sont identiques, on prend la valeur, sinon on prend 'default'
        snap_mode = d.get("orbiterSnapMode", "default")
        detach_mode = d.get("orbiterDetachMode", "default")
        if snap_mode == detach_mode:
            self.combo_orbit_mode.setCurrentText(snap_mode)
        else:
            self.combo_orbit_mode.setCurrentText("default")
        
        row(fl, "Particules max", self.sp_Nmax, TOOLTIPS["system.Nmax"], lambda: self.sp_Nmax.setValue(d["Nmax"]))
        row(fl, "Limite haute résolution", self.sp_dpr, TOOLTIPS["system.dprClamp"], lambda: self.sp_dpr.setValue(d["dprClamp"]))
    # Contrôles retirés de l'UI : Gravité donut (force/progression), Rayon orbital, Vitesse orbitale
        row(fl, "Taille des boutons", self._button_size_widget, TOOLTIPS["system.donutButtonSize"], lambda: self._set_button_size(d.get("donutButtonSize", 80)))
        row(fl, "Diamètre du donut hub", self._radius_ratio_widget, TOOLTIPS["system.donutRadiusRatio"], lambda: self._set_radius_ratio(d.get("donutRadiusRatio", 0.35)))
        row(fl, "Diamètre cercle rouge", self._circle_controls["red"][0], TOOLTIPS["system.markerCircles.red"], lambda: self._set_circle_value("red", d["markerCircles"]["red"]))
        row(fl, "Diamètre cercle jaune", self._circle_controls["yellow"][0], TOOLTIPS["system.markerCircles.yellow"], lambda: self._set_circle_value("yellow", d["markerCircles"]["yellow"]))
        row(fl, "Mode accrochage/décrochage orbite", self.combo_orbit_mode, TOOLTIPS["system.orbiterSnapMode"], lambda: self.combo_orbit_mode.setCurrentText(snap_mode))
        row(fl, "Tri par profondeur", self.chk_depthSort, TOOLTIPS["system.depthSort"], lambda: self.chk_depthSort.setChecked(d["depthSort"]))
        row(fl, "Fenêtre transparente", self.chk_transparent, TOOLTIPS["system.transparent"], lambda: self.chk_transparent.setChecked(d["transparent"]))
        for w in [
            self.sp_Nmax,
            self.sp_dpr,
            self._button_size_spin,
            self._radius_ratio_spin,
            self.chk_depthSort,
            self.chk_transparent,
            self.combo_orbit_mode,
        ]:
            if isinstance(w, QtWidgets.QCheckBox): w.stateChanged.connect(self.emit_delta)
            elif isinstance(w, QtWidgets.QComboBox): w.currentTextChanged.connect(self.emit_delta)
            else: w.valueChanged.connect(self.emit_delta)
        for _container, slider, spin in self._circle_controls.values():
            # Emit on both spin and slider changes. The slider updates the spin with
            # a QSignalBlocker, so spin.valueChanged won't fire when dragging the slider.
            # Hooking the slider ensures live updates in the view window.
            slider.valueChanged.connect(self.emit_delta)
            spin.valueChanged.connect(self.emit_delta)
        register_linkable_widget(self.sp_Nmax, section="system", key="Nmax", tab="Système")
        register_linkable_widget(self.sp_dpr, section="system", key="dprClamp", tab="Système")
        register_linkable_widget(self._button_size_spin, section="system", key="donutButtonSize", tab="Système")
        register_linkable_widget(self._radius_ratio_spin, section="system", key="donutRadiusRatio", tab="Système")
        register_linkable_widget(self.combo_orbit_mode, section="system", key="orbiterSnapMode", tab="Système")
        register_linkable_widget(self.combo_orbit_mode, section="system", key="orbiterDetachMode", tab="Système")
        self._sync_subprofile_state()
    def collect(self):
        # Un seul mode pour accrochage/décrochage
        orbit_mode = self.combo_orbit_mode.currentText()
        return dict(
            Nmax=self.sp_Nmax.value(),
            orbiterSnapMode=orbit_mode,
            orbiterDetachMode=orbit_mode,
            dprClamp=self.sp_dpr.value(),
            donutButtonSize=self._button_size_spin.value(),
            donutRadiusRatio=self._radius_ratio_spin.value(),
            markerCircles={
                "red": self._circle_controls["red"][2].value() / 200.0,
                "yellow": self._circle_controls["yellow"][2].value() / 200.0,
            },
            depthSort=self.chk_depthSort.isChecked(),
            transparent=self.chk_transparent.isChecked(),
        )
    def set_defaults(self, cfg):
        cfg = cfg or {}
        d = DEFAULTS["system"]
        with QtCore.QSignalBlocker(self.sp_Nmax):
            self.sp_Nmax.setValue(int(cfg.get("Nmax", d["Nmax"])))
        with QtCore.QSignalBlocker(self.sp_dpr):
            self.sp_dpr.setValue(float(cfg.get("dprClamp", d["dprClamp"])))
        try:
            button_size_value = float(cfg.get("donutButtonSize", d.get("donutButtonSize", 80)))
        except (TypeError, ValueError):
            button_size_value = d.get("donutButtonSize", 80)
        self._set_button_size(button_size_value)
        try:
            radius_ratio_value = float(cfg.get("donutRadiusRatio", d.get("donutRadiusRatio", 0.35)))
        except (TypeError, ValueError):
            radius_ratio_value = d.get("donutRadiusRatio", 0.35)
        self._set_radius_ratio(radius_ratio_value)
        marker_cfg = cfg.get("markerCircles", {})
        if not isinstance(marker_cfg, dict):
            marker_cfg = {}
        # Only set red and yellow; blue is controlled by donutRadiusRatio
        for color in ("red", "yellow"):
            default_value = d["markerCircles"].get(color, 0.0)
            raw = marker_cfg.get(color, default_value)
            try:
                value = float(raw)
            except (TypeError, ValueError):
                value = default_value
            self._set_circle_value(color, value)
        with QtCore.QSignalBlocker(self.chk_depthSort):
            self.chk_depthSort.setChecked(bool(cfg.get("depthSort", d["depthSort"])))
        with QtCore.QSignalBlocker(self.chk_transparent):
            self.chk_transparent.setChecked(bool(cfg.get("transparent", d["transparent"])))
        with QtCore.QSignalBlocker(self.combo_orbit_mode):
            # On prend le mode si les deux sont identiques, sinon 'default'
            snap_mode = str(cfg.get("orbiterSnapMode", d.get("orbiterSnapMode", "default")))
            detach_mode = str(cfg.get("orbiterDetachMode", d.get("orbiterDetachMode", "default")))
            if snap_mode == detach_mode:
                self.combo_orbit_mode.setCurrentText(snap_mode)
            else:
                self.combo_orbit_mode.setCurrentText("default")
        self._sync_subprofile_state()
    def set_enabled(self, context: dict): pass
    def emit_delta(self, *a):
        self._sync_subprofile_state()
        self.changed.emit({"system": self.collect()})

    def attach_subprofile_manager(self, manager):
        self._subprofile_panel.bind(
            manager=manager,
            section="system",
            defaults=DEFAULTS["system"],
            collect_cb=self.collect,
            apply_cb=self.set_defaults,
            on_change=self.emit_delta,
        )
        self._sync_subprofile_state()

    def _sync_subprofile_state(self):
        if hasattr(self, "_subprofile_panel") and self._subprofile_panel is not None:
            self._subprofile_panel.sync_from_data(self.collect())

    # ------------------------------------------------------------------ helpers
    # (Contrôle de vitesse orbitale retiré)

    def _create_button_size_controls(self, value: float):
        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        slider.setRange(20, 200)
        slider.setSingleStep(1)
        spin = QtWidgets.QSpinBox()
        spin.setRange(20, 200)
        spin.setSingleStep(1)
        spin.setSuffix(" px")
        spin.setValue(int(value))
        slider.setValue(spin.value())
        slider.valueChanged.connect(lambda val: spin.setValue(val))
        spin.valueChanged.connect(lambda val: slider.setValue(val))
        container = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(slider, 1)
        layout.addWidget(spin)
        container.setLayout(layout)
        return container, slider, spin

    def _create_radius_ratio_controls(self, value: float):
        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        slider.setRange(5, 90)
        slider.setSingleStep(1)
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(0.05, 0.90)
        spin.setDecimals(2)
        spin.setSingleStep(0.01)
        spin.setValue(float(value))
        slider.setValue(int(round(spin.value() * 100)))
        slider.valueChanged.connect(lambda val: spin.setValue(val / 100.0))
        spin.valueChanged.connect(lambda val: slider.setValue(int(round(val * 100))))
        container = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(slider, 1)
        layout.addWidget(spin)
        container.setLayout(layout)
        return container, slider, spin

    def _create_circle_controls(self, overrides: dict):
        controls = {}
        defaults = DEFAULTS["system"]["markerCircles"]
        # Only create controls for red and yellow; blue is controlled by donutRadiusRatio
        for color in ("red", "yellow"):
            default_value = float(defaults.get(color, 0.0))
            value = overrides.get(color, default_value)
            try:
                ratio = float(value)
            except (TypeError, ValueError):
                ratio = default_value
            ratio = max(0.0, min(0.5, ratio))
            slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            slider.setRange(0, 100)
            slider.setSingleStep(1)
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(0.0, 100.0)
            spin.setDecimals(0)
            spin.setSingleStep(1.0)
            spin.setSuffix(" %")
            spin.setValue(ratio * 200.0)
            slider.setValue(int(round(spin.value())))

            def _on_slider(val, target_spin=spin):
                with QtCore.QSignalBlocker(target_spin):
                    target_spin.setValue(float(val))

            def _on_spin(val, target_slider=slider):
                with QtCore.QSignalBlocker(target_slider):
                    target_slider.setValue(int(round(val)))

            slider.valueChanged.connect(_on_slider)
            spin.valueChanged.connect(_on_spin)
            container = QtWidgets.QWidget()
            layout = QtWidgets.QHBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(6)
            layout.addWidget(slider, 1)
            layout.addWidget(spin)
            container.setLayout(layout)
            controls[color] = (container, slider, spin)
        return controls

    # (Réglage de vitesse orbitale retiré)

    def _set_circle_value(self, color: str, ratio: float):
        if color not in self._circle_controls:
            return
        ratio = max(0.0, min(0.5, float(ratio)))
        _container, slider, spin = self._circle_controls[color]
        with QtCore.QSignalBlocker(spin):
            spin.setValue(ratio * 200.0)
        with QtCore.QSignalBlocker(slider):
            slider.setValue(int(round(spin.value())))

    def _set_button_size(self, value: float):
        value = max(20.0, min(200.0, float(value)))
        with QtCore.QSignalBlocker(self._button_size_spin):
            self._button_size_spin.setValue(int(value))
        with QtCore.QSignalBlocker(self._button_size_slider):
            self._button_size_slider.setValue(int(value))

    def _set_radius_ratio(self, value: float):
        value = max(0.05, min(0.90, float(value)))
        with QtCore.QSignalBlocker(self._radius_ratio_spin):
            self._radius_ratio_spin.setValue(value)
        with QtCore.QSignalBlocker(self._radius_ratio_slider):
            self._radius_ratio_slider.setValue(int(round(value * 100)))
