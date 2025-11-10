from __future__ import annotations

from typing import Dict

from PyQt5 import QtCore, QtWidgets

from .widgets import SubProfilePanel, row
from .config import DEFAULTS, TOOLTIPS
from .link_registry import register_linkable_widget


class OrbitTab(QtWidgets.QWidget):
    """Controls dedicated to orbital trajectories (accrochage & orbite)."""

    changed = QtCore.pyqtSignal(dict)

    _TAB_LABEL = "Trajet orbitale"

    def __init__(self) -> None:
        super().__init__()
        defaults = DEFAULTS.get("orbit", {})

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        self._subprofile_panel = SubProfilePanel("Sous-profil trajectoire")
        outer.addWidget(self._subprofile_panel)

        container = QtWidgets.QWidget()
        form_layout = QtWidgets.QFormLayout(container)
        form_layout.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(container)

        # --- Gravité et orbite -------------------------------------------------
        gravity_group = QtWidgets.QGroupBox("Influence gravitationnelle")
        gravity_group.setStyleSheet("QGroupBox { color: white; }")
        gravity_layout = QtWidgets.QFormLayout(gravity_group)
        gravity_layout.setContentsMargins(8, 8, 8, 8)

        self.spin_gravity_strength = QtWidgets.QDoubleSpinBox()
        self.spin_gravity_strength.setRange(0.0, 1.0)
        self.spin_gravity_strength.setDecimals(2)
        self.spin_gravity_strength.setSingleStep(0.05)
        self.spin_gravity_strength.setValue(float(defaults.get("donutGravityStrength", 1.0)))

        self.spin_gravity_falloff = QtWidgets.QDoubleSpinBox()
        self.spin_gravity_falloff.setRange(0.2, 5.0)
        self.spin_gravity_falloff.setDecimals(2)
        self.spin_gravity_falloff.setSingleStep(0.1)
        self.spin_gravity_falloff.setValue(float(defaults.get("donutGravityFalloff", 1.0)))

        (
            self._ring_offset_container,
            self._ring_offset_slider,
            self.spin_ring_offset,
        ) = self._create_ring_offset_controls(defaults.get("donutGravityRingOffset", 12.0))

        row(
            gravity_layout,
            "Force d'attraction",
            self.spin_gravity_strength,
            TOOLTIPS["orbit.donutGravityStrength"],
            lambda: self.spin_gravity_strength.setValue(float(defaults.get("donutGravityStrength", 1.0))),
        )
        row(
            gravity_layout,
            "Atténuation",
            self.spin_gravity_falloff,
            TOOLTIPS["orbit.donutGravityFalloff"],
            lambda: self.spin_gravity_falloff.setValue(float(defaults.get("donutGravityFalloff", 1.0))),
        )
        row(
            gravity_layout,
            "Décalage orbite (px)",
            self._ring_offset_container,
            TOOLTIPS["orbit.donutGravityRingOffset"],
            lambda: self._set_ring_offset(float(defaults.get("donutGravityRingOffset", 12.0))),
        )

        form_layout.addRow(gravity_group)

        # --- Phases transition & orbite ---------------------------------------
        transition_group = QtWidgets.QGroupBox("Accrochage & décrochage")
        transition_group.setStyleSheet("QGroupBox { color: white; }")
        transition_layout = QtWidgets.QFormLayout(transition_group)
        transition_layout.setContentsMargins(8, 8, 8, 8)

        self.combo_transition_mode = self._build_easing_combo()
        self._set_combo_value(
            self.combo_transition_mode,
            defaults.get("orbiterTransitionMode", defaults.get("orbiterSnapMode", "default")),
            "default",
        )

        self.combo_trajectory = self._build_trajectory_combo()
        self._set_combo_value(
            self.combo_trajectory,
            defaults.get("orbiterTrajectory", defaults.get("orbiterApproachTrajectory", "line")),
            "line",
        )

        self.spin_transition_duration = QtWidgets.QSpinBox()
        self.spin_transition_duration.setRange(50, 10000)
        self.spin_transition_duration.setSingleStep(25)
        self.spin_transition_duration.setSuffix(" ms")
        self.spin_transition_duration.setValue(
            int(
                float(
                    defaults.get(
                        "orbiterTransitionDuration",
                        defaults.get("orbiterApproachDuration", 700.0),
                    )
                )
            )
        )

        row(
            transition_layout,
            "Mode d'easing",
            self.combo_transition_mode,
            TOOLTIPS["orbit.orbiterTransitionMode"],
            lambda: self._set_combo_value(
                self.combo_transition_mode,
                defaults.get("orbiterTransitionMode", defaults.get("orbiterSnapMode", "default")),
                "default",
            ),
        )
        row(
            transition_layout,
            "Trajectoire",
            self.combo_trajectory,
            TOOLTIPS["orbit.orbiterTrajectory"],
            lambda: self._set_combo_value(
                self.combo_trajectory,
                defaults.get("orbiterTrajectory", defaults.get("orbiterApproachTrajectory", "line")),
                "line",
            ),
        )
        row(
            transition_layout,
            "Durée (accrochage & décrochage)",
            self.spin_transition_duration,
            TOOLTIPS["orbit.orbiterTransitionDuration"],
            lambda: self.spin_transition_duration.setValue(
                int(
                    float(
                        defaults.get(
                            "orbiterTransitionDuration",
                            defaults.get("orbiterApproachDuration", 700.0),
                        )
                    )
                )
            ),
        )

        # -- Paramètres par trajectoire ----------------------------------------
        self._bezier_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self._bezier_slider.setRange(-200, 200)
        self._bezier_slider.setSingleStep(5)
        self.spin_bezier_bend = QtWidgets.QDoubleSpinBox()
        self.spin_bezier_bend.setRange(-2.0, 2.0)
        self.spin_bezier_bend.setDecimals(2)
        self.spin_bezier_bend.setSingleStep(0.05)
        self.spin_bezier_bend.setValue(
            float(defaults.get("orbiterTrajectoryBend", 0.35))
        )
        self._set_bezier_bend(self.spin_bezier_bend.value())

        bezier_widget = QtWidgets.QWidget()
        bezier_layout = QtWidgets.QHBoxLayout(bezier_widget)
        bezier_layout.setContentsMargins(0, 0, 0, 0)
        bezier_layout.setSpacing(6)
        bezier_layout.addWidget(self._bezier_slider, 1)
        bezier_layout.addWidget(self.spin_bezier_bend)

        self.combo_arc_direction = QtWidgets.QComboBox()
        self.combo_arc_direction.addItem("Auto (chemin le plus court)", "auto")
        self.combo_arc_direction.addItem("Horaire", "cw")
        self.combo_arc_direction.addItem("Antihoraire", "ccw")
        self._set_combo_value(
            self.combo_arc_direction,
            defaults.get("orbiterTrajectoryArcDirection", "auto"),
            "auto",
        )

        self._bezier_param_row = row(
            transition_layout,
            "Courbure Bézier",
            bezier_widget,
            TOOLTIPS["orbit.orbiterTrajectoryBend"],
            lambda: self._set_bezier_bend(float(defaults.get("orbiterTrajectoryBend", 0.35))),
        )
        self._arc_param_row = row(
            transition_layout,
            "Direction de l'arc",
            self.combo_arc_direction,
            TOOLTIPS["orbit.orbiterTrajectoryArcDirection"],
            lambda: self._set_combo_value(
                self.combo_arc_direction,
                defaults.get("orbiterTrajectoryArcDirection", "auto"),
                "auto",
            ),
        )

        self.spin_spiral_turns = QtWidgets.QDoubleSpinBox()
        self.spin_spiral_turns.setRange(0.25, 12.0)
        self.spin_spiral_turns.setDecimals(2)
        self.spin_spiral_turns.setSingleStep(0.1)
        self.spin_spiral_turns.setValue(float(defaults.get("orbiterSpiralTurns", 1.5)))

        self.spin_spiral_tightness = QtWidgets.QDoubleSpinBox()
        self.spin_spiral_tightness.setRange(-2.0, 2.0)
        self.spin_spiral_tightness.setDecimals(2)
        self.spin_spiral_tightness.setSingleStep(0.05)
        self.spin_spiral_tightness.setValue(float(defaults.get("orbiterSpiralTightness", 0.35)))

        self._spiral_turns_row = row(
            transition_layout,
            "Tours spirale",
            self.spin_spiral_turns,
            TOOLTIPS["orbit.orbiterSpiralTurns"],
            lambda: self.spin_spiral_turns.setValue(float(defaults.get("orbiterSpiralTurns", 1.5))),
        )
        self._spiral_tightness_row = row(
            transition_layout,
            "Tension spirale",
            self.spin_spiral_tightness,
            TOOLTIPS["orbit.orbiterSpiralTightness"],
            lambda: self.spin_spiral_tightness.setValue(float(defaults.get("orbiterSpiralTightness", 0.35))),
        )

        self.spin_wave_amplitude = QtWidgets.QDoubleSpinBox()
        self.spin_wave_amplitude.setRange(0.0, 5.0)
        self.spin_wave_amplitude.setDecimals(2)
        self.spin_wave_amplitude.setSingleStep(0.05)
        self.spin_wave_amplitude.setValue(float(defaults.get("orbiterWaveAmplitude", 0.3)))

        self.spin_wave_frequency = QtWidgets.QDoubleSpinBox()
        self.spin_wave_frequency.setRange(0.0, 20.0)
        self.spin_wave_frequency.setDecimals(2)
        self.spin_wave_frequency.setSingleStep(0.1)
        self.spin_wave_frequency.setValue(float(defaults.get("orbiterWaveFrequency", 3.0)))

        self._wave_amplitude_row = row(
            transition_layout,
            "Amplitude onde",
            self.spin_wave_amplitude,
            TOOLTIPS["orbit.orbiterWaveAmplitude"],
            lambda: self.spin_wave_amplitude.setValue(float(defaults.get("orbiterWaveAmplitude", 0.3))),
        )
        self._wave_frequency_row = row(
            transition_layout,
            "Fréquence onde",
            self.spin_wave_frequency,
            TOOLTIPS["orbit.orbiterWaveFrequency"],
            lambda: self.spin_wave_frequency.setValue(float(defaults.get("orbiterWaveFrequency", 3.0))),
        )

        self.spin_trail_blend = QtWidgets.QDoubleSpinBox()
        self.spin_trail_blend.setRange(0.0, 1.0)
        self.spin_trail_blend.setDecimals(2)
        self.spin_trail_blend.setSingleStep(0.05)
        self.spin_trail_blend.setValue(float(defaults.get("orbiterTrailBlend", 0.7)))

        self.spin_trail_smoothing = QtWidgets.QDoubleSpinBox()
        self.spin_trail_smoothing.setRange(0.0, 1.0)
        self.spin_trail_smoothing.setDecimals(2)
        self.spin_trail_smoothing.setSingleStep(0.05)
        self.spin_trail_smoothing.setValue(float(defaults.get("orbiterTrailSmoothing", 0.4)))

        self.spin_trail_memory = QtWidgets.QDoubleSpinBox()
        self.spin_trail_memory.setRange(0.25, 12.0)
        self.spin_trail_memory.setDecimals(2)
        self.spin_trail_memory.setSingleStep(0.25)
        self.spin_trail_memory.setSuffix(" s")
        self.spin_trail_memory.setValue(float(defaults.get("orbiterTrailMemorySeconds", 2.0)))

        self._trail_blend_row = row(
            transition_layout,
            "Fusion trajectoire initiale",
            self.spin_trail_blend,
            TOOLTIPS["orbit.orbiterTrailBlend"],
            lambda: self.spin_trail_blend.setValue(float(defaults.get("orbiterTrailBlend", 0.7))),
        )
        self._trail_smoothing_row = row(
            transition_layout,
            "Lissage trajectoire",
            self.spin_trail_smoothing,
            TOOLTIPS["orbit.orbiterTrailSmoothing"],
            lambda: self.spin_trail_smoothing.setValue(float(defaults.get("orbiterTrailSmoothing", 0.4))),
        )
        self._trail_memory_row = row(
            transition_layout,
            "Mémoire trajectoire",
            self.spin_trail_memory,
            TOOLTIPS["orbit.orbiterTrailMemorySeconds"],
            lambda: self.spin_trail_memory.setValue(float(defaults.get("orbiterTrailMemorySeconds", 2.0))),
        )

        form_layout.addRow(transition_group)

        # --- Orbite ------------------------------------------------------------
        orbit_group = QtWidgets.QGroupBox("Phase d'orbite")
        orbit_group.setStyleSheet("QGroupBox { color: white; }")
        orbit_layout = QtWidgets.QFormLayout(orbit_group)
        orbit_layout.setContentsMargins(8, 8, 8, 8)

        self.spin_orbit_speed = QtWidgets.QDoubleSpinBox()
        self.spin_orbit_speed.setRange(0.0, 5.0)
        self.spin_orbit_speed.setDecimals(2)
        self.spin_orbit_speed.setSingleStep(0.05)
        self.spin_orbit_speed.setValue(float(defaults.get("orbitSpeed", 1.0)))

        self.spin_required_turns = QtWidgets.QDoubleSpinBox()
        self.spin_required_turns.setRange(0.0, 6.0)
        self.spin_required_turns.setDecimals(2)
        self.spin_required_turns.setSingleStep(0.1)
        self.spin_required_turns.setValue(float(defaults.get("orbiterRequiredTurns", 1.0)))

        self.spin_max_orbit = QtWidgets.QSpinBox()
        self.spin_max_orbit.setRange(250, 30000)
        self.spin_max_orbit.setSingleStep(100)
        self.spin_max_orbit.setSuffix(" ms")
        self.spin_max_orbit.setValue(int(float(defaults.get("orbiterMaxOrbitMs", 4000.0))))

        row(
            orbit_layout,
            "Vitesse orbitale",
            self.spin_orbit_speed,
            TOOLTIPS["orbit.orbitSpeed"],
            lambda: self.spin_orbit_speed.setValue(float(defaults.get("orbitSpeed", 1.0))),
        )
        row(
            orbit_layout,
            "Tours minimum",
            self.spin_required_turns,
            TOOLTIPS["orbit.orbiterRequiredTurns"],
            lambda: self.spin_required_turns.setValue(float(defaults.get("orbiterRequiredTurns", 1.0))),
        )
        row(
            orbit_layout,
            "Temps max en orbite",
            self.spin_max_orbit,
            TOOLTIPS["orbit.orbiterMaxOrbitMs"],
            lambda: self.spin_max_orbit.setValue(int(float(defaults.get("orbiterMaxOrbitMs", 4000.0)))),
        )

        form_layout.addRow(orbit_group)

        # --- Signals -----------------------------------------------------------
        for widget in [
            self.spin_gravity_strength,
            self.spin_gravity_falloff,
            self.spin_ring_offset,
            self.spin_orbit_speed,
            self.spin_required_turns,
            self.spin_max_orbit,
            self.spin_transition_duration,
            self.spin_spiral_turns,
            self.spin_spiral_tightness,
            self.spin_wave_amplitude,
            self.spin_wave_frequency,
            self.spin_trail_blend,
            self.spin_trail_smoothing,
            self.spin_trail_memory,
        ]:
            widget.valueChanged.connect(self.emit_delta)

        self._ring_offset_slider.valueChanged.connect(self.emit_delta)

        for combo in [
            self.combo_transition_mode,
            self.combo_trajectory,
            self.combo_arc_direction,
        ]:
            combo.currentIndexChanged.connect(self.emit_delta)

        self._bezier_slider.valueChanged.connect(self._on_bezier_slider_changed)
        self.spin_bezier_bend.valueChanged.connect(self._on_bezier_spin_changed)
        self.combo_trajectory.currentIndexChanged.connect(self._on_trajectory_changed)

        self._sync_trajectory_params()

        # Register linkable widgets for numeric controls
        register_linkable_widget(
            self.spin_gravity_strength,
            section="orbit",
            key="donutGravityStrength",
            tab=self._TAB_LABEL,
        )
        register_linkable_widget(
            self.spin_gravity_falloff,
            section="orbit",
            key="donutGravityFalloff",
            tab=self._TAB_LABEL,
        )
        register_linkable_widget(
            self.spin_ring_offset,
            section="orbit",
            key="donutGravityRingOffset",
            tab=self._TAB_LABEL,
        )
        register_linkable_widget(
            self.spin_orbit_speed,
            section="orbit",
            key="orbitSpeed",
            tab=self._TAB_LABEL,
        )
        register_linkable_widget(
            self.spin_required_turns,
            section="orbit",
            key="orbiterRequiredTurns",
            tab=self._TAB_LABEL,
        )
        register_linkable_widget(
            self.spin_max_orbit,
            section="orbit",
            key="orbiterMaxOrbitMs",
            tab=self._TAB_LABEL,
        )
        register_linkable_widget(
            self.spin_transition_duration,
            section="orbit",
            key="orbiterTransitionDuration",
            tab=self._TAB_LABEL,
        )
        register_linkable_widget(
            self.spin_bezier_bend,
            section="orbit",
            key="orbiterTrajectoryBend",
            tab=self._TAB_LABEL,
        )
        register_linkable_widget(
            self.spin_spiral_turns,
            section="orbit",
            key="orbiterSpiralTurns",
            tab=self._TAB_LABEL,
        )
        register_linkable_widget(
            self.spin_spiral_tightness,
            section="orbit",
            key="orbiterSpiralTightness",
            tab=self._TAB_LABEL,
        )
        register_linkable_widget(
            self.spin_wave_amplitude,
            section="orbit",
            key="orbiterWaveAmplitude",
            tab=self._TAB_LABEL,
        )
        register_linkable_widget(
            self.spin_wave_frequency,
            section="orbit",
            key="orbiterWaveFrequency",
            tab=self._TAB_LABEL,
        )
        register_linkable_widget(
            self.spin_trail_blend,
            section="orbit",
            key="orbiterTrailBlend",
            tab=self._TAB_LABEL,
        )
        register_linkable_widget(
            self.spin_trail_smoothing,
            section="orbit",
            key="orbiterTrailSmoothing",
            tab=self._TAB_LABEL,
        )
        register_linkable_widget(
            self.spin_trail_memory,
            section="orbit",
            key="orbiterTrailMemorySeconds",
            tab=self._TAB_LABEL,
        )

        self._sync_subprofile_state()

    # ------------------------------------------------------------------ helpers
    def _build_easing_combo(self) -> QtWidgets.QComboBox:
        combo = QtWidgets.QComboBox()
        combo.addItem("Progressif (cubique)", "default")
        combo.addItem("Linéaire", "linear")
        combo.addItem("Démarrage progressif", "ease_in")
        combo.addItem("Aller-retour doux", "ease_in_out")
        combo.addItem("Instantané", "none")
        combo.addItem("Désactivé", "off")
        return combo

    def _build_trajectory_combo(self) -> QtWidgets.QComboBox:
        combo = QtWidgets.QComboBox()
        combo.addItem("Ligne directe", "line")
        combo.addItem("Courbe fluide", "bezier")
        combo.addItem("Arc circulaire", "arc")
        combo.addItem("Spirale vers orbite", "spiral")
        combo.addItem("Ondulation sinusoïdale", "wave")
        combo.addItem("Trajectoire initiale", "initial_path")
        return combo

    def _set_combo_value(
        self, combo: QtWidgets.QComboBox, value: object, fallback: object
    ) -> None:
        target = combo.findData(value)
        if target < 0:
            target = combo.findData(fallback)
        if target < 0:
            target = 0
        with QtCore.QSignalBlocker(combo):
            combo.setCurrentIndex(target)

    def _create_ring_offset_controls(self, value: object):
        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        slider.setRange(0, 150)
        slider.setSingleStep(1)
        spin = QtWidgets.QSpinBox()
        spin.setRange(0, 150)
        spin.setSingleStep(1)
        spin.setSuffix(" px")
        try:
            numeric_value = int(float(value))
        except (TypeError, ValueError):
            numeric_value = 12
        spin.setValue(numeric_value)
        slider.setValue(numeric_value)
        slider.valueChanged.connect(spin.setValue)
        spin.valueChanged.connect(slider.setValue)
        container = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(slider, 1)
        layout.addWidget(spin)
        container.setLayout(layout)
        return container, slider, spin

    def _set_ring_offset(self, value: float) -> None:
        with QtCore.QSignalBlocker(self.spin_ring_offset):
            self.spin_ring_offset.setValue(int(round(value)))
        with QtCore.QSignalBlocker(self._ring_offset_slider):
            self._ring_offset_slider.setValue(int(round(value)))

    def _set_bezier_bend(self, value: float) -> None:
        value = max(-2.0, min(2.0, float(value)))
        with QtCore.QSignalBlocker(self.spin_bezier_bend):
            self.spin_bezier_bend.setValue(value)
        with QtCore.QSignalBlocker(self._bezier_slider):
            self._bezier_slider.setValue(int(round(value * 100)))

    def _set_row_visible(self, widget: QtWidgets.QWidget | None, visible: bool) -> None:
        if widget is None:
            return
        widget.setVisible(visible)
        label = getattr(widget, "_form_label", None)
        if label is not None:
            label.setVisible(visible)

    def _sync_trajectory_params(self) -> None:
        mode = str(self.combo_trajectory.currentData())
        self._set_row_visible(self._bezier_param_row, mode == "bezier")
        self._set_row_visible(self._arc_param_row, mode == "arc")
        self._set_row_visible(self._spiral_turns_row, mode == "spiral")
        self._set_row_visible(self._spiral_tightness_row, mode == "spiral")
        self._set_row_visible(self._wave_amplitude_row, mode == "wave")
        self._set_row_visible(self._wave_frequency_row, mode == "wave")
        show_trail = mode == "initial_path"
        self._set_row_visible(self._trail_blend_row, show_trail)
        self._set_row_visible(self._trail_smoothing_row, show_trail)
        self._set_row_visible(self._trail_memory_row, show_trail)

    def _on_bezier_slider_changed(self, raw: int) -> None:
        self._set_bezier_bend(raw / 100.0)
        self.emit_delta()

    def _on_bezier_spin_changed(self, value: float) -> None:
        self._set_bezier_bend(value)
        self.emit_delta()

    def _on_trajectory_changed(self, *args) -> None:
        del args
        self._sync_trajectory_params()

    # ------------------------------------------------------------------ API
    def collect(self) -> Dict[str, object]:
        transition_mode = str(self.combo_transition_mode.currentData())
        trajectory_mode = str(self.combo_trajectory.currentData())
        transition_duration = int(self.spin_transition_duration.value())
        bezier_bend = float(self.spin_bezier_bend.value())
        arc_direction = str(self.combo_arc_direction.currentData())
        return dict(
            donutGravityStrength=float(self.spin_gravity_strength.value()),
            donutGravityFalloff=float(self.spin_gravity_falloff.value()),
            donutGravityRingOffset=float(self.spin_ring_offset.value()),
            orbitSpeed=float(self.spin_orbit_speed.value()),
            orbiterTransitionMode=transition_mode,
            orbiterSnapMode=transition_mode,
            orbiterDetachMode=transition_mode,
            orbiterTrajectory=trajectory_mode,
            orbiterApproachTrajectory=trajectory_mode,
            orbiterReturnTrajectory=trajectory_mode,
            orbiterTransitionDuration=transition_duration,
            orbiterApproachDuration=transition_duration,
            orbiterReturnDuration=transition_duration,
            orbiterTrajectoryBend=bezier_bend,
            orbiterTrajectoryArcDirection=arc_direction,
            orbiterSpiralTurns=float(self.spin_spiral_turns.value()),
            orbiterSpiralTightness=float(self.spin_spiral_tightness.value()),
            orbiterWaveAmplitude=float(self.spin_wave_amplitude.value()),
            orbiterWaveFrequency=float(self.spin_wave_frequency.value()),
            orbiterTrailBlend=float(self.spin_trail_blend.value()),
            orbiterTrailSmoothing=float(self.spin_trail_smoothing.value()),
            orbiterTrailMemorySeconds=float(self.spin_trail_memory.value()),
            orbiterRequiredTurns=float(self.spin_required_turns.value()),
            orbiterMaxOrbitMs=int(self.spin_max_orbit.value()),
        )

    def set_defaults(self, cfg: Dict | None) -> None:
        defaults = DEFAULTS.get("orbit", {})
        cfg = cfg or {}
        def _get_value(key: str, fallback: object) -> object:
            return cfg.get(key, defaults.get(key, fallback))

        with QtCore.QSignalBlocker(self.spin_gravity_strength):
            self.spin_gravity_strength.setValue(float(_get_value("donutGravityStrength", 1.0)))
        with QtCore.QSignalBlocker(self.spin_gravity_falloff):
            self.spin_gravity_falloff.setValue(float(_get_value("donutGravityFalloff", 1.0)))
        self._set_ring_offset(float(_get_value("donutGravityRingOffset", 12.0)))
        with QtCore.QSignalBlocker(self.spin_orbit_speed):
            self.spin_orbit_speed.setValue(float(_get_value("orbitSpeed", 1.0)))
        with QtCore.QSignalBlocker(self.spin_required_turns):
            self.spin_required_turns.setValue(float(_get_value("orbiterRequiredTurns", 1.0)))
        with QtCore.QSignalBlocker(self.spin_max_orbit):
            self.spin_max_orbit.setValue(int(float(_get_value("orbiterMaxOrbitMs", 4000.0))))
        duration_value = int(
            float(
                _get_value(
                    "orbiterTransitionDuration",
                    _get_value("orbiterApproachDuration", 700.0),
                )
            )
        )
        with QtCore.QSignalBlocker(self.spin_transition_duration):
            self.spin_transition_duration.setValue(duration_value)

        transition_mode = _get_value(
            "orbiterTransitionMode", _get_value("orbiterSnapMode", "default")
        )
        self._set_combo_value(
            self.combo_transition_mode,
            transition_mode,
            "default",
        )
        trajectory_mode = _get_value(
            "orbiterTrajectory", _get_value("orbiterApproachTrajectory", "line")
        )
        self._set_combo_value(
            self.combo_trajectory,
            trajectory_mode,
            "line",
        )
        self._set_combo_value(
            self.combo_arc_direction,
            _get_value("orbiterTrajectoryArcDirection", "auto"),
            "auto",
        )

        self._set_bezier_bend(float(_get_value("orbiterTrajectoryBend", 0.35)))

        with QtCore.QSignalBlocker(self.spin_spiral_turns):
            self.spin_spiral_turns.setValue(float(_get_value("orbiterSpiralTurns", 1.5)))
        with QtCore.QSignalBlocker(self.spin_spiral_tightness):
            self.spin_spiral_tightness.setValue(float(_get_value("orbiterSpiralTightness", 0.35)))
        with QtCore.QSignalBlocker(self.spin_wave_amplitude):
            self.spin_wave_amplitude.setValue(float(_get_value("orbiterWaveAmplitude", 0.3)))
        with QtCore.QSignalBlocker(self.spin_wave_frequency):
            self.spin_wave_frequency.setValue(float(_get_value("orbiterWaveFrequency", 3.0)))
        with QtCore.QSignalBlocker(self.spin_trail_blend):
            self.spin_trail_blend.setValue(float(_get_value("orbiterTrailBlend", 0.7)))
        with QtCore.QSignalBlocker(self.spin_trail_smoothing):
            self.spin_trail_smoothing.setValue(float(_get_value("orbiterTrailSmoothing", 0.4)))
        with QtCore.QSignalBlocker(self.spin_trail_memory):
            self.spin_trail_memory.setValue(float(_get_value("orbiterTrailMemorySeconds", 2.0)))

        self._sync_trajectory_params()

        self._sync_subprofile_state()

    def set_enabled(self, context: dict) -> None:  # pragma: no cover - UI hook
        del context

    def emit_delta(self, *args) -> None:
        del args
        self._sync_subprofile_state()
        self.changed.emit({"orbit": self.collect()})

    def attach_subprofile_manager(self, manager) -> None:
        self._subprofile_panel.bind(
            manager=manager,
            section="orbit",
            defaults=DEFAULTS.get("orbit", {}),
            collect_cb=self.collect,
            apply_cb=self.set_defaults,
            on_change=self.emit_delta,
        )
        self._sync_subprofile_state()

    def _sync_subprofile_state(self) -> None:
        if getattr(self, "_subprofile_panel", None) is not None:
            self._subprofile_panel.sync_from_data(self.collect())
