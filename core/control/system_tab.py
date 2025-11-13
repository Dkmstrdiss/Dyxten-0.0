
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
        self.chk_depthSort = QtWidgets.QCheckBox(); self.chk_depthSort.setChecked(d["depthSort"])
        self.chk_transparent = QtWidgets.QCheckBox(); self.chk_transparent.setChecked(d["transparent"])
        self.chk_orbiter_color = QtWidgets.QCheckBox(); self.chk_orbiter_color.setChecked(d.get("orbiterColorFromButton", False))
        self._orbiter_opacity_widget, self._orbiter_opacity_slider, self._orbiter_opacity_spin = self._create_orbiter_opacity_controls(
            d.get("orbiterOpacity", 0.9)
        )
        self._orbiter_size_widget, self._orbiter_size_slider, self._orbiter_size_spin = self._create_orbiter_size_controls(
            d.get("orbiterSizePx", 2.5)
        )
        self.chk_orbiter_size_match = QtWidgets.QCheckBox("Same as model")
        self.chk_orbiter_size_match.setChecked(d.get("orbiterSizeSameAsModel", True))
        self.chk_orbiter_size_match.setToolTip(TOOLTIPS["system.orbiterSizeSameAsModel"])
        self.chk_red_halo = QtWidgets.QCheckBox(); self.chk_red_halo.setChecked(d.get("redCircleHalo", False))
        self.chk_show_imprints = QtWidgets.QCheckBox(); self.chk_show_imprints.setChecked(d.get("showImprints", True))
        
        row(fl, "Particules max", self.sp_Nmax, TOOLTIPS["system.Nmax"], lambda: self.sp_Nmax.setValue(d["Nmax"]))
        row(fl, "Limite haute résolution", self.sp_dpr, TOOLTIPS["system.dprClamp"], lambda: self.sp_dpr.setValue(d["dprClamp"]))
        row(fl, "Tri par profondeur", self.chk_depthSort, TOOLTIPS["system.depthSort"], lambda: self.chk_depthSort.setChecked(d["depthSort"]))
        row(fl, "Fenêtre transparente", self.chk_transparent, TOOLTIPS["system.transparent"], lambda: self.chk_transparent.setChecked(d["transparent"]))
        row(fl, "Couleur orbiters = bouton", self.chk_orbiter_color, TOOLTIPS["system.orbiterColorFromButton"], lambda: self.chk_orbiter_color.setChecked(d.get("orbiterColorFromButton", False)))
        row(fl, "Opacité particules orbit.", self._orbiter_opacity_widget, TOOLTIPS["system.orbiterOpacity"], lambda: self._set_orbiter_opacity(d.get("orbiterOpacity", 0.9)))
        orbiter_size_row = QtWidgets.QWidget()
        orbiter_size_layout = QtWidgets.QHBoxLayout(orbiter_size_row)
        orbiter_size_layout.setContentsMargins(0, 0, 0, 0)
        orbiter_size_layout.setSpacing(6)
        orbiter_size_layout.addWidget(self._orbiter_size_widget, 1)
        orbiter_size_layout.addWidget(self.chk_orbiter_size_match)
        row(fl, "Taille particules orbit.", orbiter_size_row, TOOLTIPS["system.orbiterSizePx"], lambda: self._reset_orbiter_size_defaults(d))
        row(fl, "Halo cercle rouge", self.chk_red_halo, TOOLTIPS["system.redCircleHalo"], lambda: self.chk_red_halo.setChecked(d.get("redCircleHalo", False)))
        row(fl, "Afficher les empreintes", self.chk_show_imprints, TOOLTIPS["system.showImprints"], lambda: self.chk_show_imprints.setChecked(d.get("showImprints", True)))

        # Encadré pour les contrôles du donut hub
        groupbox = QtWidgets.QGroupBox("Paramètres du donut hub")
        groupbox.setStyleSheet("QGroupBox { color: white; }")
        groupbox_layout = QtWidgets.QFormLayout(groupbox)
        groupbox_layout.setContentsMargins(8, 8, 8, 8)
        outer.addWidget(groupbox)

        self._button_size_widget, self._button_size_slider, self._button_size_spin = self._create_button_size_controls(d.get("donutButtonSize", 80))
        self._radius_ratio_widget, self._radius_ratio_slider, self._radius_ratio_spin = self._create_radius_ratio_controls(d.get("donutRadiusRatio", 0.35))
        marker_defaults = d.get("markerCircles", {})
        self._circle_controls = self._create_circle_controls(marker_defaults)
        self._yellow_ratio = float(marker_defaults.get("yellow", 0.19))

        row(groupbox_layout, "Taille des boutons", self._button_size_widget, TOOLTIPS["system.donutButtonSize"], lambda: self._set_button_size(d.get("donutButtonSize", 80)))
        row(groupbox_layout, "Diamètre du donut hub", self._radius_ratio_widget, TOOLTIPS["system.donutRadiusRatio"], lambda: self._set_radius_ratio(d.get("donutRadiusRatio", 0.35)))
        row(groupbox_layout, "Diamètre cercle rouge", self._circle_controls["red"][0], TOOLTIPS["system.markerCircles.red"], lambda: self._set_circle_value("red", d["markerCircles"]["red"]))
        self._update_orbiter_size_enabled()

        for w in [
            self.sp_Nmax,
            self.sp_dpr,
            self._button_size_spin,
            self._radius_ratio_spin,
            self._orbiter_opacity_spin,
            self._orbiter_size_spin,
            self.chk_depthSort,
            self.chk_transparent,
            self.chk_orbiter_color,
            self.chk_red_halo,
            self.chk_show_imprints,
            self.chk_orbiter_size_match,
        ]:
            if isinstance(w, QtWidgets.QCheckBox): w.stateChanged.connect(self.emit_delta)
            elif isinstance(w, QtWidgets.QComboBox): w.currentTextChanged.connect(self.emit_delta)
            else: w.valueChanged.connect(self.emit_delta)
        self._orbiter_opacity_slider.valueChanged.connect(self.emit_delta)
        self._orbiter_size_slider.valueChanged.connect(self.emit_delta)
        self.chk_orbiter_size_match.toggled.connect(self._on_orbiter_size_match_toggled)
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
        register_linkable_widget(self._orbiter_opacity_spin, section="system", key="orbiterOpacity", tab="Système")
        register_linkable_widget(self._orbiter_size_spin, section="system", key="orbiterSizePx", tab="Système")
        register_linkable_widget(self.chk_orbiter_size_match, section="system", key="orbiterSizeSameAsModel", tab="Système")
        register_linkable_widget(self.chk_orbiter_color, section="system", key="orbiterColorFromButton", tab="Système")
        register_linkable_widget(self.chk_red_halo, section="system", key="redCircleHalo", tab="Système")
        register_linkable_widget(self.chk_show_imprints, section="system", key="showImprints", tab="Système")
        self._sync_subprofile_state()
    def collect(self):
        return dict(
            Nmax=self.sp_Nmax.value(),
            dprClamp=self.sp_dpr.value(),
            donutButtonSize=self._button_size_spin.value(),
            donutRadiusRatio=self._radius_ratio_spin.value(),
            markerCircles={
                "red": self._circle_controls["red"][2].value() / 200.0,
                "yellow": float(self._yellow_ratio),
            },
            depthSort=self.chk_depthSort.isChecked(),
            transparent=self.chk_transparent.isChecked(),
            orbiterColorFromButton=self.chk_orbiter_color.isChecked(),
            redCircleHalo=self.chk_red_halo.isChecked(),
            showImprints=self.chk_show_imprints.isChecked(),
            orbiterOpacity=float(self._orbiter_opacity_spin.value()) / 100.0,
            orbiterSizePx=float(self._orbiter_size_spin.value()),
            orbiterSizeSameAsModel=self.chk_orbiter_size_match.isChecked(),
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
        default_red = d["markerCircles"].get("red", 0.0)
        raw_red = marker_cfg.get("red", default_red)
        try:
            red_value = float(raw_red)
        except (TypeError, ValueError):
            red_value = default_red
        self._set_circle_value("red", red_value)

        default_yellow = d["markerCircles"].get("yellow", 0.19)
        raw_yellow = marker_cfg.get("yellow", default_yellow)
        try:
            self._yellow_ratio = max(0.0, min(0.5, float(raw_yellow)))
        except (TypeError, ValueError):
            self._yellow_ratio = max(0.0, min(0.5, float(default_yellow)))
        with QtCore.QSignalBlocker(self.chk_depthSort):
            self.chk_depthSort.setChecked(bool(cfg.get("depthSort", d["depthSort"])))
        with QtCore.QSignalBlocker(self.chk_transparent):
            self.chk_transparent.setChecked(bool(cfg.get("transparent", d["transparent"])))
        with QtCore.QSignalBlocker(self.chk_orbiter_color):
            self.chk_orbiter_color.setChecked(bool(cfg.get("orbiterColorFromButton", d.get("orbiterColorFromButton", False))))
        with QtCore.QSignalBlocker(self.chk_red_halo):
            self.chk_red_halo.setChecked(bool(cfg.get("redCircleHalo", d.get("redCircleHalo", False))))
        with QtCore.QSignalBlocker(self.chk_show_imprints):
            self.chk_show_imprints.setChecked(bool(cfg.get("showImprints", d.get("showImprints", True))))
        opacity_value = cfg.get("orbiterOpacity", d.get("orbiterOpacity", 0.9))
        try:
            opacity_float = float(opacity_value)
        except (TypeError, ValueError):
            opacity_float = d.get("orbiterOpacity", 0.9)
        self._set_orbiter_opacity(opacity_float)
        size_value = cfg.get("orbiterSizePx", d.get("orbiterSizePx", 2.5))
        try:
            size_float = float(size_value)
        except (TypeError, ValueError):
            size_float = d.get("orbiterSizePx", 2.5)
        self._set_orbiter_size(size_float)
        with QtCore.QSignalBlocker(self.chk_orbiter_size_match):
            self.chk_orbiter_size_match.setChecked(bool(cfg.get("orbiterSizeSameAsModel", d.get("orbiterSizeSameAsModel", True))))
        self._update_orbiter_size_enabled()
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
        # Only create controls for red; blue is controlled by donutRadiusRatio
        for color in ("red",):
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

    def set_yellow_ratio(self, value: float) -> None:
        self._yellow_ratio = max(0.0, min(0.5, float(value)))
        self._sync_subprofile_state()

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

    def _create_orbiter_opacity_controls(self, value: float):
        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        slider.setRange(0, 100)
        slider.setSingleStep(1)
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(0.0, 100.0)
        spin.setDecimals(1)
        spin.setSingleStep(0.5)
        spin.setSuffix(" %")
        percent = 0.0
        try:
            raw = float(value)
        except (TypeError, ValueError):
            raw = 0.9
        if raw > 1.0 + 1e-6:
            percent = max(0.0, min(100.0, raw))
        else:
            percent = max(0.0, min(100.0, raw * 100.0))
        spin.setValue(percent)
        slider.setValue(int(round(percent)))
        slider.valueChanged.connect(lambda val: spin.setValue(float(val)))
        spin.valueChanged.connect(lambda val: slider.setValue(int(round(val))))
        container = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(slider, 1)
        layout.addWidget(spin)
        container.setLayout(layout)
        return container, slider, spin

    def _create_orbiter_size_controls(self, value: float):
        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        slider.setRange(5, 200)
        slider.setSingleStep(1)
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(0.5, 20.0)
        spin.setDecimals(1)
        spin.setSingleStep(0.1)
        spin.setSuffix(" px")
        try:
            px_value = float(value)
        except (TypeError, ValueError):
            px_value = 2.5
        px_value = max(0.5, min(20.0, px_value))
        spin.setValue(px_value)
        slider.setValue(int(round(px_value * 10.0)))
        slider.valueChanged.connect(lambda val: spin.setValue(val / 10.0))
        spin.valueChanged.connect(lambda val: slider.setValue(int(round(val * 10.0))))
        container = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(slider, 1)
        layout.addWidget(spin)
        container.setLayout(layout)
        return container, slider, spin

    def _set_orbiter_opacity(self, value: float) -> None:
        try:
            raw = float(value)
        except (TypeError, ValueError):
            raw = 0.9
        if raw > 1.0 + 1e-6:
            percent = max(0.0, min(100.0, raw))
        else:
            percent = max(0.0, min(100.0, raw * 100.0))
        with QtCore.QSignalBlocker(self._orbiter_opacity_spin):
            self._orbiter_opacity_spin.setValue(percent)
        with QtCore.QSignalBlocker(self._orbiter_opacity_slider):
            self._orbiter_opacity_slider.setValue(int(round(percent)))

    def _set_orbiter_size(self, value: float) -> None:
        try:
            px_value = float(value)
        except (TypeError, ValueError):
            px_value = 2.5
        px_value = max(0.5, min(20.0, px_value))
        with QtCore.QSignalBlocker(self._orbiter_size_spin):
            self._orbiter_size_spin.setValue(px_value)
        with QtCore.QSignalBlocker(self._orbiter_size_slider):
            self._orbiter_size_slider.setValue(int(round(px_value * 10.0)))

    def _reset_orbiter_size_defaults(self, defaults: dict) -> None:
        self._set_orbiter_size(defaults.get("orbiterSizePx", 2.5))
        with QtCore.QSignalBlocker(self.chk_orbiter_size_match):
            self.chk_orbiter_size_match.setChecked(bool(defaults.get("orbiterSizeSameAsModel", True)))
        self._update_orbiter_size_enabled()

    def _update_orbiter_size_enabled(self) -> None:
        enabled = not self.chk_orbiter_size_match.isChecked()
        self._orbiter_size_widget.setEnabled(enabled)

    def _on_orbiter_size_match_toggled(self, checked: bool) -> None:
        del checked
        self._update_orbiter_size_enabled()
