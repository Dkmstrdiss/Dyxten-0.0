from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from PyQt5 import QtCore, QtWidgets

from ..donut_hub import DEFAULT_DONUT_BUTTON_COUNT
from ..orbital_utils import solve_tangent_radii
from .config import DEFAULTS, TOOLTIPS
from .link_registry import register_linkable_widget
from .widgets import SubProfilePanel


@dataclass
class _OrbitControl:
    container: QtWidgets.QWidget
    slider: QtWidgets.QSlider
    spin: QtWidgets.QDoubleSpinBox


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


class IndicatorTab(QtWidgets.QWidget):
    """Controls dedicated to visual indicators drawn in the view widget."""

    changed = QtCore.pyqtSignal(dict)

    _TAB_LABEL = "Indicateur"

    def __init__(self) -> None:
        super().__init__()
        defaults = DEFAULTS.get("indicator", {})

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        self._subprofile_panel = SubProfilePanel("Sous-profil indicateur")
        outer.addWidget(self._subprofile_panel)

        self._center_group = QtWidgets.QGroupBox("Lignes centre → bouton")
        self._center_group.setStyleSheet("QGroupBox { color: white; }")
        center_layout = QtWidgets.QFormLayout(self._center_group)
        center_layout.setContentsMargins(8, 8, 8, 8)
        outer.addWidget(self._center_group)

        self.chk_all_lines = QtWidgets.QCheckBox("Activer pour tous les boutons")
        self.chk_all_lines.setToolTip(TOOLTIPS.get("indicator.centerLines.all", ""))
        center_layout.addRow(self.chk_all_lines)

        buttons_row = QtWidgets.QWidget()
        buttons_layout = QtWidgets.QGridLayout(buttons_row)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setHorizontalSpacing(6)
        buttons_layout.setVerticalSpacing(4)
        self._line_checks: Dict[int, QtWidgets.QCheckBox] = {}
        self._angle_spins: Dict[int, QtWidgets.QDoubleSpinBox] = {}
        self._angle_fixed_checks: Dict[int, QtWidgets.QCheckBox] = {}
        for idx in range(DEFAULT_DONUT_BUTTON_COUNT):
            checkbox = QtWidgets.QCheckBox(f"Bouton {idx + 1}")
            checkbox.setToolTip(TOOLTIPS.get("indicator.centerLines.buttons", ""))
            angle_spin = QtWidgets.QDoubleSpinBox()
            angle_spin.setRange(0.0, 360.0)
            angle_spin.setDecimals(0)
            angle_spin.setSingleStep(1.0)
            angle_spin.setSuffix(" °")
            angle_spin.setWrapping(True)
            base_angle = (360.0 / DEFAULT_DONUT_BUTTON_COUNT) * idx
            angle_spin.setValue(base_angle % 360.0)
            fix_checkbox = QtWidgets.QCheckBox("Fixe")
            self._line_checks[idx] = checkbox
            self._angle_spins[idx] = angle_spin
            self._angle_fixed_checks[idx] = fix_checkbox
            widget = QtWidgets.QWidget()
            widget_layout = QtWidgets.QHBoxLayout(widget)
            widget_layout.setContentsMargins(0, 0, 0, 0)
            widget_layout.setSpacing(4)
            widget_layout.addWidget(checkbox)
            widget_layout.addWidget(angle_spin)
            widget_layout.addWidget(fix_checkbox)
            widget_layout.addStretch(1)
            row = idx // 5
            col = idx % 5
            buttons_layout.addWidget(widget, row, col)
        center_layout.addRow(buttons_row)

        for idx, spin in self._angle_spins.items():
            register_linkable_widget(
                spin,
                section="indicator",
                key=f"centerLines.angles[{idx}]",
                tab=self._TAB_LABEL,
            )
        for idx, checkbox in self._angle_fixed_checks.items():
            register_linkable_widget(
                checkbox,
                section="indicator",
                key=f"centerLines.fixed[{idx}]",
                tab=self._TAB_LABEL,
            )

        yellow_defaults = defaults.get("yellowCircleRatio", 0.19)
        (
            self._yellow_container,
            self._yellow_slider,
            self._yellow_spin,
        ) = self._create_ratio_controls(float(yellow_defaults))
        center_layout.addRow("Diamètre cercle jaune", self._yellow_container)

        register_linkable_widget(
            self._yellow_spin,
            section="indicator",
            key="yellowCircleRatio",
            tab=self._TAB_LABEL,
        )

        self._orbital_group = QtWidgets.QGroupBox("Zones orbitales")
        self._orbital_group.setStyleSheet("QGroupBox { color: white; }")
        orbital_layout = QtWidgets.QFormLayout(self._orbital_group)
        orbital_layout.setContentsMargins(8, 8, 8, 8)
        outer.addWidget(self._orbital_group)

        orbit_defaults = defaults.get("orbitalZones", {})

        self.chk_orbital_enabled = QtWidgets.QCheckBox("Afficher les zones orbitales")
        self.chk_orbital_enabled.setChecked(True)
        self.chk_orbital_enabled.setToolTip(TOOLTIPS.get("indicator.orbitalZones.enabled", ""))
        orbital_layout.addRow(self.chk_orbital_enabled)

        coverage_angle_default = float(orbit_defaults.get("coverageAngle", 0.0)) if isinstance(orbit_defaults, dict) else 0.0
        (
            self._coverage_angle_container,
            self._coverage_angle_slider,
            self._coverage_angle_spin,
        ) = self._create_degree_controls(coverage_angle_default)
        orbital_layout.addRow("Angle à exclure", self._coverage_angle_container)
        register_linkable_widget(
            self._coverage_angle_spin,
            section="indicator",
            key="orbitalZones.coverageAngle",
            tab=self._TAB_LABEL,
        )

        coverage_offset_default = float(orbit_defaults.get("coverageOffset", 0.0)) if isinstance(orbit_defaults, dict) else 0.0
        (
            self._coverage_offset_container,
            self._coverage_offset_slider,
            self._coverage_offset_spin,
        ) = self._create_degree_controls(coverage_offset_default)
        orbital_layout.addRow("Angle de départ", self._coverage_offset_container)
        register_linkable_widget(
            self._coverage_offset_spin,
            section="indicator",
            key="orbitalZones.coverageOffset",
            tab=self._TAB_LABEL,
        )

        equidistant_default = bool(orbit_defaults.get("equidistant", False)) if isinstance(orbit_defaults, dict) else False
        self.chk_orbit_equidistant = QtWidgets.QCheckBox("Répartition équidistante")
        self.chk_orbit_equidistant.setChecked(equidistant_default)
        orbital_layout.addRow(self.chk_orbit_equidistant)
        register_linkable_widget(
            self.chk_orbit_equidistant,
            section="indicator",
            key="orbitalZones.equidistant",
            tab=self._TAB_LABEL,
        )

        self._orbit_controls: List[_OrbitControl] = []
        diameters: Sequence[float] = orbit_defaults.get("diameters", []) if isinstance(orbit_defaults, dict) else []

        grid_widget = QtWidgets.QWidget()
        grid_layout = QtWidgets.QGridLayout(grid_widget)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setHorizontalSpacing(8)
        grid_layout.setVerticalSpacing(6)

        for idx in range(DEFAULT_DONUT_BUTTON_COUNT):
            raw_value: float
            if idx < len(diameters):
                try:
                    raw_value = float(diameters[idx])
                except (TypeError, ValueError):
                    raw_value = 120.0
            else:
                raw_value = 120.0
            control = self._create_orbit_control(idx, raw_value)
            self._orbit_controls.append(control)
            grid_layout.addWidget(QtWidgets.QLabel(f"Bouton {idx + 1}"), idx, 0)
            grid_layout.addWidget(control.container, idx, 1)

        orbital_layout.addRow(grid_widget)

        self.chk_all_lines.stateChanged.connect(self.emit_delta)
        for checkbox in self._line_checks.values():
            checkbox.stateChanged.connect(self.emit_delta)
        for idx, spin in self._angle_spins.items():
            spin.valueChanged.connect(lambda val, i=idx: self._on_button_angle_spin(i, float(val)))
        for idx, checkbox in self._angle_fixed_checks.items():
            checkbox.stateChanged.connect(
                lambda state, i=idx: self._on_button_fixed_changed(i, state == QtCore.Qt.Checked)
            )
        self._yellow_slider.valueChanged.connect(self._on_yellow_slider)
        self._yellow_spin.valueChanged.connect(self._on_yellow_spin)
        self.chk_orbital_enabled.stateChanged.connect(self.emit_delta)

        self._coverage_angle_slider.valueChanged.connect(lambda val: self._on_coverage_angle(float(val)))
        self._coverage_angle_spin.valueChanged.connect(lambda val: self._on_coverage_angle(float(val)))
        self._coverage_offset_slider.valueChanged.connect(lambda val: self._on_coverage_offset(float(val)))
        self._coverage_offset_spin.valueChanged.connect(lambda val: self._on_coverage_offset(float(val)))
        self.chk_orbit_equidistant.stateChanged.connect(self._on_equidistant_changed)

        self._updating_orbits = False
        self._orbital_angles: List[float] = []
        self._coverage_angle_deg = 0.0
        self._coverage_offset_deg = 0.0
        self._equidistant = equidistant_default

        for idx, control in enumerate(self._orbit_controls):
            control.slider.valueChanged.connect(lambda val, i=idx: self._on_orbit_slider(i, float(val)))
            control.spin.valueChanged.connect(lambda val, i=idx: self._on_orbit_spin(i, float(val)))

        self._last_diameters = [control.spin.value() for control in self._orbit_controls]
        self._button_angles = [
            self._angle_spins[idx].value() if idx in self._angle_spins else 0.0
            for idx in range(DEFAULT_DONUT_BUTTON_COUNT)
        ]
        self._button_fixed = [
            self._angle_fixed_checks[idx].isChecked() if idx in self._angle_fixed_checks else False
            for idx in range(DEFAULT_DONUT_BUTTON_COUNT)
        ]
        self._orbital_radius = 0.0

        self._system_tab: Optional[object] = None
        self._donut_hub: Optional[object] = None
        self.set_defaults(defaults)

    # ------------------------------------------------------------------ API
    def set_system_tab(self, system_tab: object) -> None:
        """Allow the indicator tab to update the system configuration."""

        self._system_tab = system_tab

    def set_donut_hub(self, hub: Optional[object]) -> None:
        """Provide a reference to the donut hub so we can steer its layout."""

        self._donut_hub = hub
        if hub is not None and self._last_diameters:
            self._push_orbital_layout(self._last_diameters)

    def collect(self) -> dict:
        return dict(
            centerLines=dict(
                all=self.chk_all_lines.isChecked(),
                buttons={str(idx + 1): checkbox.isChecked() for idx, checkbox in self._line_checks.items()},
                angles={
                    str(idx + 1): self._button_angles[idx] if idx < len(self._button_angles) else 0.0
                    for idx in range(DEFAULT_DONUT_BUTTON_COUNT)
                },
                fixed={
                    str(idx + 1): self._button_fixed[idx] if idx < len(self._button_fixed) else False
                    for idx in range(DEFAULT_DONUT_BUTTON_COUNT)
                },
            ),
            yellowCircleRatio=self._yellow_spin.value() / 200.0,
            orbitalZones=dict(
                enabled=self.chk_orbital_enabled.isChecked(),
                diameters=[control.spin.value() for control in self._orbit_controls],
                coverageAngle=self._coverage_angle_deg,
                coverageOffset=self._coverage_offset_deg,
                equidistant=self._equidistant,
            ),
        )

    def set_defaults(self, cfg: Optional[dict]) -> None:
        cfg = cfg or {}
        center_cfg = cfg.get("centerLines", {}) if isinstance(cfg, dict) else {}
        if isinstance(center_cfg, dict):
            with QtCore.QSignalBlocker(self.chk_all_lines):
                self.chk_all_lines.setChecked(bool(center_cfg.get("all", False)))
            buttons_cfg = center_cfg.get("buttons", {})
            if isinstance(buttons_cfg, dict):
                for idx, checkbox in self._line_checks.items():
                    raw = buttons_cfg.get(str(idx + 1), buttons_cfg.get(idx + 1))
                    with QtCore.QSignalBlocker(checkbox):
                        checkbox.setChecked(bool(raw))
            angles_cfg = center_cfg.get("angles", {})
            if isinstance(angles_cfg, dict):
                for idx, spin in self._angle_spins.items():
                    raw = angles_cfg.get(str(idx + 1), angles_cfg.get(idx + 1))
                    try:
                        value = float(raw)
                    except (TypeError, ValueError):
                        value = spin.value()
                    self._set_button_angle(idx, value)
            else:
                for idx, spin in self._angle_spins.items():
                    self._set_button_angle(idx, spin.value())
            fixed_cfg = center_cfg.get("fixed", {})
            if isinstance(fixed_cfg, dict):
                for idx in range(DEFAULT_DONUT_BUTTON_COUNT):
                    raw = fixed_cfg.get(str(idx + 1), fixed_cfg.get(idx + 1))
                    self._set_button_fixed(idx, bool(raw))
            else:
                for idx in range(DEFAULT_DONUT_BUTTON_COUNT):
                    self._set_button_fixed(idx, False)
        yellow_ratio = cfg.get("yellowCircleRatio") if isinstance(cfg, dict) else None
        if yellow_ratio is None:
            yellow_ratio = DEFAULTS.get("indicator", {}).get("yellowCircleRatio", 0.19)
        try:
            yellow_ratio = float(yellow_ratio)
        except (TypeError, ValueError):
            yellow_ratio = 0.19
        yellow_ratio = max(0.0, min(0.5, yellow_ratio))
        self._set_yellow_ratio(yellow_ratio)
        orbital_cfg = cfg.get("orbitalZones", {}) if isinstance(cfg, dict) else {}
        enabled = True
        diameters: Sequence[float] = []
        coverage_angle = 0.0
        coverage_offset = 0.0
        equidistant = False
        if isinstance(orbital_cfg, dict):
            enabled = bool(orbital_cfg.get("enabled", True))
            raw_diameters = orbital_cfg.get("diameters", [])
            if isinstance(raw_diameters, Sequence):
                diameters = list(raw_diameters)
            raw_cov_angle = orbital_cfg.get("coverageAngle")
            raw_cov_offset = orbital_cfg.get("coverageOffset")
            equidistant = bool(orbital_cfg.get("equidistant", False))
            try:
                coverage_angle = float(raw_cov_angle)
            except (TypeError, ValueError):
                coverage_angle = 0.0
            try:
                coverage_offset = float(raw_cov_offset)
            except (TypeError, ValueError):
                coverage_offset = 0.0
        with QtCore.QSignalBlocker(self.chk_orbital_enabled):
            self.chk_orbital_enabled.setChecked(enabled)
        self._set_coverage_angle(coverage_angle)
        self._set_coverage_offset(coverage_offset)
        self._set_equidistant(equidistant)
        for idx, control in enumerate(self._orbit_controls):
            value = diameters[idx] if idx < len(diameters) else control.spin.value()
            try:
                value = float(value)
            except (TypeError, ValueError):
                value = control.spin.value()
            value = max(0.0, min(400.0, value))
            with QtCore.QSignalBlocker(control.spin):
                control.spin.setValue(value)
            with QtCore.QSignalBlocker(control.slider):
                control.slider.setValue(int(round(value)))
        self._last_diameters = [control.spin.value() for control in self._orbit_controls]
        self._refresh_orbital_layout(emit=False)
        self.emit_delta()

    def update_orbital_layout(self, centers, radii=None) -> None:  # noqa: ANN001 - Qt signal payload
        del radii
        if not isinstance(centers, (list, tuple)):
            return
        count = min(len(centers), len(self._orbit_controls))
        points: List[Tuple[float, float]] = []
        for idx in range(count):
            try:
                x1, y1 = centers[idx]
            except Exception:
                continue
            try:
                points.append((float(x1), float(y1)))
            except Exception:
                points.append((0.0, 0.0))
        if points and len(points) < count:
            points.extend([points[-1]] * (count - len(points)))
        if points:
            avg_x = sum(x for x, _ in points) / len(points)
            avg_y = sum(y for _, y in points) / len(points)
            angles: List[float] = []
            radii_samples: List[float] = []
            for px, py in points:
                ang = math.degrees(math.atan2(py - avg_y, px - avg_x)) % 360.0
                angles.append(ang)
                radii_samples.append(math.hypot(px - avg_x, py - avg_y))
            self._orbital_angles = angles
            if radii_samples:
                self._orbital_radius = sum(radii_samples) / len(radii_samples)
        else:
            self._orbital_angles = []
        if self._orbital_angles:
            for idx, angle in enumerate(self._orbital_angles[: DEFAULT_DONUT_BUTTON_COUNT]):
                self._set_button_angle(idx, angle)
        if self._orbit_controls:
            self._refresh_orbital_layout(emit=False)

    def attach_subprofile_manager(self, manager) -> None:
        self._subprofile_panel.bind(
            manager=manager,
            section="indicator",
            defaults=DEFAULTS.get("indicator", {}),
            collect_cb=self.collect,
            apply_cb=self.set_defaults,
            on_change=self.emit_delta,
        )
        self._subprofile_panel.sync_from_data(self.collect())

    # ----------------------------------------------------------------- helpers
    def _set_equidistant(self, enabled: bool) -> None:
        self._equidistant = bool(enabled)
        with QtCore.QSignalBlocker(self.chk_orbit_equidistant):
            self.chk_orbit_equidistant.setChecked(self._equidistant)

    def _on_equidistant_changed(self, state: int) -> None:  # noqa: ANN001 - Qt slot signature
        self._equidistant = state == QtCore.Qt.Checked
        self._refresh_orbital_layout()

    def _on_orbit_slider(self, idx: int, value: float) -> None:
        if 0 <= idx < len(self._orbit_controls):
            control = self._orbit_controls[idx]
            with QtCore.QSignalBlocker(control.spin):
                control.spin.setValue(_clamp(value, 0.0, 400.0))
        self._refresh_orbital_layout()

    def _on_orbit_spin(self, idx: int, value: float) -> None:
        if 0 <= idx < len(self._orbit_controls):
            control = self._orbit_controls[idx]
            with QtCore.QSignalBlocker(control.slider):
                control.slider.setValue(int(round(_clamp(value, 0.0, 400.0))))
        self._refresh_orbital_layout()

    def _on_button_angle_spin(self, idx: int, value: float) -> None:
        self._set_button_angle(idx, value, from_spin=True)
        if self._last_diameters:
            self._push_orbital_layout(self._last_diameters)
        self.emit_delta()

    def _on_button_fixed_changed(self, idx: int, checked: bool) -> None:
        self._set_button_fixed(idx, checked, from_ui=True)
        if checked:
            if self._last_diameters:
                self._push_orbital_layout(self._last_diameters)
            self.emit_delta()
        else:
            self._refresh_orbital_layout()

    def _on_coverage_angle(self, value: float) -> None:
        clamped = _clamp(float(value), 0.0, 360.0)
        if abs(clamped - self._coverage_angle_deg) <= 1e-3:
            self._set_coverage_angle(clamped)
            return
        self._set_coverage_angle(clamped)
        self._refresh_orbital_layout()

    def _on_coverage_offset(self, value: float) -> None:
        normalized = float(value) % 360.0
        if abs(((normalized - self._coverage_offset_deg + 180.0) % 360.0) - 180.0) <= 1e-3:
            self._set_coverage_offset(normalized)
            return
        self._set_coverage_offset(normalized)
        self._refresh_orbital_layout()

    def _refresh_orbital_layout(
        self,
        diameters: Optional[Sequence[float]] = None,
        *,
        emit: bool = True,
    ) -> None:
        if self._updating_orbits:
            return
        self._updating_orbits = True
        try:
            if diameters is None:
                current = [control.spin.value() for control in self._orbit_controls]
            else:
                current = [_clamp(float(value), 0.0, 400.0) for value in diameters]
            self._last_diameters = list(current)
            # Do NOT recompute or apply auto angles here: changing diameters
            # must not reposition the donut buttons. We only push the orbital
            # diameters so the renderer draws the green circles at the sizes
            # specified by the user while preserving the current button angles.
            self._push_orbital_layout(current)
        finally:
            self._updating_orbits = False
        if emit:
            self.emit_delta()

    def _set_coverage_angle(self, value: float) -> None:
        clamped = _clamp(float(value), 0.0, 360.0)
        rounded = float(int(round(clamped)))
        self._coverage_angle_deg = rounded
        with QtCore.QSignalBlocker(self._coverage_angle_spin):
            self._coverage_angle_spin.setValue(rounded)
        with QtCore.QSignalBlocker(self._coverage_angle_slider):
            self._coverage_angle_slider.setValue(int(rounded))

    def _set_coverage_offset(self, value: float) -> None:
        normalized = float(value) % 360.0
        rounded = float(int(round(normalized)) % 360)
        self._coverage_offset_deg = rounded
        with QtCore.QSignalBlocker(self._coverage_offset_spin):
            self._coverage_offset_spin.setValue(rounded)
        with QtCore.QSignalBlocker(self._coverage_offset_slider):
            self._coverage_offset_slider.setValue(int(rounded))

    def _set_button_angle(self, idx: int, value: float, *, from_spin: bool = False) -> None:
        if idx < 0:
            return
        while len(self._button_angles) <= idx:
            self._button_angles.append(0.0)
        normalized = float(value) % 360.0
        self._button_angles[idx] = normalized
        spin = self._angle_spins.get(idx)
        if spin is not None and not from_spin:
            with QtCore.QSignalBlocker(spin):
                spin.setValue(normalized)

    def _set_button_fixed(self, idx: int, value: bool, *, from_ui: bool = False) -> None:
        if idx < 0:
            return
        while len(self._button_fixed) <= idx:
            self._button_fixed.append(False)
        flag = bool(value)
        self._button_fixed[idx] = flag
        checkbox = self._angle_fixed_checks.get(idx)
        if checkbox is not None and not from_ui:
            with QtCore.QSignalBlocker(checkbox):
                checkbox.setChecked(flag)

    def _infer_radius(self, diameters: Sequence[float]) -> float:
        if not diameters:
            return 120.0
        total = 0.0
        count = 0
        for value in diameters:
            try:
                total += max(0.0, float(value))
                count += 1
            except (TypeError, ValueError):
                continue
        avg = total / count if count else 120.0
        return max(60.0, avg)

    def _compute_auto_angles(self, diameters: Sequence[float]) -> List[float]:
        count = len(diameters)
        if count <= 0:
            return []
        radius = float(getattr(self, "_orbital_radius", 0.0) or 0.0)
        if radius <= 1e-3:
            radius = self._infer_radius(diameters)
        radius = max(1.0, radius)
        gap = _clamp(self._coverage_angle_deg, 0.0, 360.0)
        available = max(0.0, 360.0 - gap)
        central: List[float] = []
        for idx in range(count):
            try:
                current = max(0.0, float(diameters[idx]))
            except (TypeError, ValueError):
                current = 0.0
            try:
                nxt = max(0.0, float(diameters[(idx + 1) % count]))
            except (TypeError, ValueError):
                nxt = 0.0
            chord = (current + nxt) * 0.5
            if chord <= 1e-6:
                central.append(0.0)
                continue
            ratio = chord / (2.0 * radius)
            ratio = max(0.0, min(0.999999, ratio))
            try:
                angle = math.degrees(2.0 * math.asin(ratio))
            except ValueError:
                angle = 180.0
            central.append(angle)
        total = sum(central)
        if total <= 1e-6:
            step = available / count if count else 0.0
            central = [step for _ in range(count)]
        else:
            scale = available / total if total > 1e-6 else 0.0
            central = [angle * scale for angle in central]
        start = (-90.0 + self._coverage_offset_deg + gap) % 360.0
        angles: List[float] = []
        current_angle = start
        for idx in range(count):
            angles.append(current_angle % 360.0)
            current_angle += central[idx % count]
        return angles

    def _apply_auto_angles(self, auto_angles: Sequence[float]) -> None:
        if not auto_angles:
            return
        count = min(len(auto_angles), DEFAULT_DONUT_BUTTON_COUNT)
        for idx in range(count):
            if idx < len(self._button_fixed) and self._button_fixed[idx]:
                # keep user-defined angle for fixed buttons
                spin = self._angle_spins.get(idx)
                value = spin.value() if spin is not None else self._button_angles[idx]
                self._set_button_angle(idx, value)
            else:
                self._set_button_angle(idx, float(auto_angles[idx]))

    def _push_orbital_layout(self, diameters: Sequence[float]) -> None:
        hub = getattr(self, "_donut_hub", None)
        if hub is None or not hasattr(hub, "configure_orbital_layout"):
            return
        try:
            count = len(diameters)
            angles_payload = []
            for idx in range(count):
                if idx < len(self._button_angles):
                    angles_payload.append(float(self._button_angles[idx]) % 360.0)
                else:
                    angles_payload.append(0.0)
            hub.configure_orbital_layout(
                diameters,
                coverage_angle=self._coverage_angle_deg,
                coverage_offset=self._coverage_offset_deg,
                equidistant=self._equidistant,
                angles=angles_payload,
            )
        except Exception:
            pass

    def _create_degree_controls(self, value: float):
        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        slider.setRange(0, 360)
        slider.setSingleStep(1)
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(0.0, 360.0)
        spin.setDecimals(0)
        spin.setSingleStep(1.0)
        spin.setSuffix(" °")
        slider.valueChanged.connect(lambda val: spin.setValue(float(val)))
        spin.valueChanged.connect(lambda val: slider.setValue(int(round(val))))
        container = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(slider, 1)
        layout.addWidget(spin)
        container.setLayout(layout)
        clamped = float(int(round(max(0.0, min(360.0, float(value))))))
        spin.setValue(clamped)
        slider.setValue(int(clamped))
        return container, slider, spin

    def _create_ratio_controls(self, ratio: float):
        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        slider.setRange(0, 100)
        slider.setSingleStep(1)
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(0.0, 100.0)
        spin.setDecimals(0)
        spin.setSingleStep(1.0)
        spin.setSuffix(" %")
        slider.valueChanged.connect(lambda val: spin.setValue(float(val)))
        spin.valueChanged.connect(lambda val: slider.setValue(int(round(val))))
        container = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(slider, 1)
        layout.addWidget(spin)
        container.setLayout(layout)
        ratio = max(0.0, min(0.5, ratio))
        spin.setValue(ratio * 200.0)
        slider.setValue(int(round(spin.value())))
        return container, slider, spin

    def _create_orbit_control(self, idx: int, diameter: float) -> _OrbitControl:
        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        slider.setRange(0, 400)
        slider.setSingleStep(1)
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(0.0, 400.0)
        spin.setDecimals(0)
        spin.setSingleStep(1.0)
        spin.setSuffix(" px")
        container = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(slider, 1)
        layout.addWidget(spin)
        container.setLayout(layout)
        value = max(0.0, min(400.0, float(diameter)))
        spin.setValue(value)
        slider.setValue(int(round(value)))
        register_linkable_widget(
            spin,
            section="indicator",
            key=f"orbitalZones.diameters[{idx}]",
            tab=self._TAB_LABEL,
        )
        return _OrbitControl(container, slider, spin)

    def _set_yellow_ratio(self, ratio: float) -> None:
        ratio = max(0.0, min(0.5, float(ratio)))
        with QtCore.QSignalBlocker(self._yellow_spin):
            self._yellow_spin.setValue(ratio * 200.0)
        with QtCore.QSignalBlocker(self._yellow_slider):
            self._yellow_slider.setValue(int(round(self._yellow_spin.value())))
        if self._system_tab is not None and hasattr(self._system_tab, "set_yellow_ratio"):
            try:
                self._system_tab.set_yellow_ratio(ratio)
            except Exception:
                pass

    def _on_yellow_slider(self, value: int) -> None:
        ratio = max(0.0, min(0.5, float(value) / 200.0))
        with QtCore.QSignalBlocker(self._yellow_spin):
            self._yellow_spin.setValue(float(value))
        if self._system_tab is not None and hasattr(self._system_tab, "set_yellow_ratio"):
            try:
                self._system_tab.set_yellow_ratio(ratio)
            except Exception:
                pass
        self.emit_delta()

    def _on_yellow_spin(self, value: float) -> None:
        ratio = max(0.0, min(0.5, float(value) / 200.0))
        with QtCore.QSignalBlocker(self._yellow_slider):
            self._yellow_slider.setValue(int(round(value)))
        if self._system_tab is not None and hasattr(self._system_tab, "set_yellow_ratio"):
            try:
                self._system_tab.set_yellow_ratio(ratio)
            except Exception:
                pass
        self.emit_delta()

    def emit_delta(self, *args) -> None:  # noqa: ANN001
        del args
        payload = dict(indicator=self.collect())
        # Keep backwards compatibility for profiles expecting yellow in system section.
        payload.setdefault("system", {}).setdefault(
            "markerCircles", {}
        )["yellow"] = self._yellow_spin.value() / 200.0
        self.changed.emit(payload)
        if self._subprofile_panel is not None:
            self._subprofile_panel.sync_from_data(self.collect())
