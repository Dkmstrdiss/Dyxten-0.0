
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
        self.sp_gravity_strength = QtWidgets.QDoubleSpinBox(); self.sp_gravity_strength.setRange(0.0,1.0); self.sp_gravity_strength.setSingleStep(0.05); self.sp_gravity_strength.setDecimals(3); self.sp_gravity_strength.setValue(d["donutGravityStrength"])
        self.sp_gravity_falloff = QtWidgets.QDoubleSpinBox(); self.sp_gravity_falloff.setRange(0.2,5.0); self.sp_gravity_falloff.setSingleStep(0.1); self.sp_gravity_falloff.setDecimals(3); self.sp_gravity_falloff.setValue(d["donutGravityFalloff"])
        self.sp_ring_offset = QtWidgets.QDoubleSpinBox(); self.sp_ring_offset.setRange(-48.0,120.0); self.sp_ring_offset.setSingleStep(1.0); self.sp_ring_offset.setDecimals(1); self.sp_ring_offset.setValue(d["donutGravityRingOffset"])
        self._orbit_widget, self._orbit_slider, self._orbit_spin = self._create_orbit_speed_controls(d["orbitSpeed"])
        self._button_size_widget, self._button_size_slider, self._button_size_spin = self._create_button_size_controls(d.get("donutButtonSize", 80))
        self._radius_ratio_widget, self._radius_ratio_slider, self._radius_ratio_spin = self._create_radius_ratio_controls(d.get("donutRadiusRatio", 0.35))
        self._circle_controls = self._create_circle_controls(d.get("markerCircles", {}))
        self.chk_depthSort = QtWidgets.QCheckBox(); self.chk_depthSort.setChecked(d["depthSort"])
        self.chk_transparent = QtWidgets.QCheckBox(); self.chk_transparent.setChecked(d["transparent"])
        row(fl, "Particules max", self.sp_Nmax, TOOLTIPS["system.Nmax"], lambda: self.sp_Nmax.setValue(d["Nmax"]))
        row(fl, "Limite haute résolution", self.sp_dpr, TOOLTIPS["system.dprClamp"], lambda: self.sp_dpr.setValue(d["dprClamp"]))
        row(fl, "Gravité donut (force)", self.sp_gravity_strength, TOOLTIPS["system.donutGravityStrength"], lambda: self.sp_gravity_strength.setValue(d["donutGravityStrength"]))
        row(fl, "Gravité donut (progression)", self.sp_gravity_falloff, TOOLTIPS["system.donutGravityFalloff"], lambda: self.sp_gravity_falloff.setValue(d["donutGravityFalloff"]))
        row(fl, "Anneau donut (offset px)", self.sp_ring_offset, TOOLTIPS["system.donutGravityRingOffset"], lambda: self.sp_ring_offset.setValue(d["donutGravityRingOffset"]))
        row(fl, "Vitesse orbitale", self._orbit_widget, TOOLTIPS["system.orbitSpeed"], lambda: self._set_orbit_speed(d["orbitSpeed"]))
        row(fl, "Taille des boutons", self._button_size_widget, TOOLTIPS["system.donutButtonSize"], lambda: self._set_button_size(d.get("donutButtonSize", 80)))
        row(fl, "Diamètre du donut hub", self._radius_ratio_widget, TOOLTIPS["system.donutRadiusRatio"], lambda: self._set_radius_ratio(d.get("donutRadiusRatio", 0.35)))
        row(fl, "Diamètre cercle rouge", self._circle_controls["red"][0], TOOLTIPS["system.markerCircles.red"], lambda: self._set_circle_value("red", d["markerCircles"]["red"]))
        row(fl, "Diamètre cercle jaune", self._circle_controls["yellow"][0], TOOLTIPS["system.markerCircles.yellow"], lambda: self._set_circle_value("yellow", d["markerCircles"]["yellow"]))
        row(fl, "Tri par profondeur", self.chk_depthSort, TOOLTIPS["system.depthSort"], lambda: self.chk_depthSort.setChecked(d["depthSort"]))
        row(fl, "Fenêtre transparente", self.chk_transparent, TOOLTIPS["system.transparent"], lambda: self.chk_transparent.setChecked(d["transparent"]))
        for w in [
            self.sp_Nmax,
            self.sp_dpr,
            self.sp_gravity_strength,
            self.sp_gravity_falloff,
            self.sp_ring_offset,
            self._orbit_spin,
            self._button_size_spin,
            self._radius_ratio_spin,
            self.chk_depthSort,
            self.chk_transparent,
        ]:
            if isinstance(w, QtWidgets.QCheckBox): w.stateChanged.connect(self.emit_delta)
            else: w.valueChanged.connect(self.emit_delta)
        for _container, slider, spin in self._circle_controls.values():
            # Emit on both spin and slider changes. The slider updates the spin with
            # a QSignalBlocker, so spin.valueChanged won't fire when dragging the slider.
            # Hooking the slider ensures live updates in the view window.
            slider.valueChanged.connect(self.emit_delta)
            spin.valueChanged.connect(self.emit_delta)
        register_linkable_widget(self.sp_Nmax, section="system", key="Nmax", tab="Système")
        register_linkable_widget(self.sp_dpr, section="system", key="dprClamp", tab="Système")
        register_linkable_widget(self.sp_gravity_strength, section="system", key="donutGravityStrength", tab="Système")
        register_linkable_widget(self.sp_gravity_falloff, section="system", key="donutGravityFalloff", tab="Système")
        register_linkable_widget(self.sp_ring_offset, section="system", key="donutGravityRingOffset", tab="Système")
        register_linkable_widget(self._orbit_spin, section="system", key="orbitSpeed", tab="Système")
        register_linkable_widget(self._button_size_spin, section="system", key="donutButtonSize", tab="Système")
        register_linkable_widget(self._radius_ratio_spin, section="system", key="donutRadiusRatio", tab="Système")
        self._sync_subprofile_state()
    def collect(self):
        return dict(
            Nmax=self.sp_Nmax.value(),
            dprClamp=self.sp_dpr.value(),
            donutGravityStrength=self.sp_gravity_strength.value(),
            donutGravityFalloff=self.sp_gravity_falloff.value(),
            donutGravityRingOffset=self.sp_ring_offset.value(),
            orbitSpeed=self._orbit_spin.value(),
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
        with QtCore.QSignalBlocker(self.sp_gravity_strength):
            self.sp_gravity_strength.setValue(float(cfg.get("donutGravityStrength", d["donutGravityStrength"])))
        with QtCore.QSignalBlocker(self.sp_gravity_falloff):
            self.sp_gravity_falloff.setValue(float(cfg.get("donutGravityFalloff", d["donutGravityFalloff"])))
        with QtCore.QSignalBlocker(self.sp_ring_offset):
            self.sp_ring_offset.setValue(float(cfg.get("donutGravityRingOffset", d["donutGravityRingOffset"])))
        try:
            orbit_value = float(cfg.get("orbitSpeed", d["orbitSpeed"]))
        except (TypeError, ValueError):
            orbit_value = d["orbitSpeed"]
        self._set_orbit_speed(orbit_value)
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
    def _create_orbit_speed_controls(self, value: float):
        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        slider.setRange(0, 400)
        slider.setSingleStep(1)
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(0.0, 4.0)
        spin.setDecimals(2)
        spin.setSingleStep(0.05)
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

    def _set_orbit_speed(self, value: float):
        value = max(0.0, min(4.0, float(value)))
        with QtCore.QSignalBlocker(self._orbit_spin):
            self._orbit_spin.setValue(value)
        with QtCore.QSignalBlocker(self._orbit_slider):
            self._orbit_slider.setValue(int(round(value * 100)))

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
