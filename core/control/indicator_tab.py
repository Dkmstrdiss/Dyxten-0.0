from __future__ import annotations

import math
import random
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


_ORBIT_MODE_OPTIONS: List[Tuple[str, str]] = [
    ("free", "Mode libre"),
    ("uniform", "Diamètre uniforme verrouillé"),
    ("ascending", "Progressif croissant"),
    ("descending", "Progressif décroissant"),
    ("random", "Compensation aléatoire"),
    ("alternating", "Alternance pair/impair"),
    ("mirrored", "Opposés symétriques"),
    ("wave", "Onde sinusoïdale"),
    ("focus", "Pic localisé"),
]


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
        for idx in range(DEFAULT_DONUT_BUTTON_COUNT):
            checkbox = QtWidgets.QCheckBox(f"Bouton {idx + 1}")
            checkbox.setToolTip(TOOLTIPS.get("indicator.centerLines.buttons", ""))
            self._line_checks[idx] = checkbox
            row = idx // 5
            col = idx % 5
            buttons_layout.addWidget(checkbox, row, col)
        center_layout.addRow(buttons_row)

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

        self.cb_orbit_mode = QtWidgets.QComboBox()
        for key, label in _ORBIT_MODE_OPTIONS:
            self.cb_orbit_mode.addItem(label, key)
        orbital_layout.addRow("Préréglage orbital", self.cb_orbit_mode)

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
        self._yellow_slider.valueChanged.connect(self._on_yellow_slider)
        self._yellow_spin.valueChanged.connect(self._on_yellow_spin)
        self.chk_orbital_enabled.stateChanged.connect(self.emit_delta)

        self._coverage_angle_slider.valueChanged.connect(lambda val: self._on_coverage_angle(float(val)))
        self._coverage_angle_spin.valueChanged.connect(lambda val: self._on_coverage_angle(float(val)))
        self._coverage_offset_slider.valueChanged.connect(lambda val: self._on_coverage_offset(float(val)))
        self._coverage_offset_spin.valueChanged.connect(lambda val: self._on_coverage_offset(float(val)))

        self._random = random.Random()
        self._updating_orbits = False
        self._orbital_spans: List[float] = []
        self._orbital_angles: List[float] = []
        self._coverage_angle_deg = 0.0
        self._coverage_offset_deg = 0.0
        self._orbit_mode = "free"
        self.cb_orbit_mode.currentIndexChanged.connect(self._on_orbit_mode_changed)

        for idx, control in enumerate(self._orbit_controls):
            control.slider.valueChanged.connect(lambda val, i=idx: self._on_orbit_slider(i, float(val)))
            control.spin.valueChanged.connect(lambda val, i=idx: self._on_orbit_spin(i, float(val)))

        self._last_diameters = [control.spin.value() for control in self._orbit_controls]

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
            ),
            yellowCircleRatio=self._yellow_spin.value() / 200.0,
            orbitalZones=dict(
                enabled=self.chk_orbital_enabled.isChecked(),
                diameters=[control.spin.value() for control in self._orbit_controls],
                mode=self._orbit_mode,
                coverageAngle=self._coverage_angle_deg,
                coverageOffset=self._coverage_offset_deg,
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
        mode = "free"
        coverage_angle = 0.0
        coverage_offset = 0.0
        if isinstance(orbital_cfg, dict):
            enabled = bool(orbital_cfg.get("enabled", True))
            raw_diameters = orbital_cfg.get("diameters", [])
            if isinstance(raw_diameters, Sequence):
                diameters = list(raw_diameters)
            raw_mode = orbital_cfg.get("mode")
            if isinstance(raw_mode, str):
                mode = raw_mode
            raw_cov_angle = orbital_cfg.get("coverageAngle")
            raw_cov_offset = orbital_cfg.get("coverageOffset")
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
        self._set_orbit_mode(mode)
        self._set_coverage_angle(coverage_angle)
        self._set_coverage_offset(coverage_offset)
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
        self._apply_orbit_adjustment(None, None, emit=False)
        self.emit_delta()

    def update_orbital_layout(self, centers, radii=None) -> None:  # noqa: ANN001 - Qt signal payload
        del radii
        if not isinstance(centers, (list, tuple)):
            return
        count = min(len(centers), len(self._orbit_controls))
        spans: List[float] = []
        points: List[Tuple[float, float]] = []
        for idx in range(count):
            try:
                x1, y1 = centers[idx]
                x2, y2 = centers[(idx + 1) % count]
                dist = math.hypot(float(x2) - float(x1), float(y2) - float(y1))
            except Exception:
                continue
            spans.append(dist)
            try:
                points.append((float(x1), float(y1)))
            except Exception:
                points.append((0.0, 0.0))
        if spans and len(spans) < count:
            spans.extend([spans[-1]] * (count - len(spans)))
        if points and len(points) < count:
            points.extend([points[-1]] * (count - len(points)))
        if points:
            avg_x = sum(x for x, _ in points) / len(points)
            avg_y = sum(y for _, y in points) / len(points)
            angles: List[float] = []
            for px, py in points:
                ang = math.degrees(math.atan2(py - avg_y, px - avg_x)) % 360.0
                angles.append(ang)
            self._orbital_angles = angles
        else:
            self._orbital_angles = []
        self._orbital_spans = spans
        if self._orbit_controls:
            self._apply_orbit_adjustment(None, None, emit=False)

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
    def _set_orbit_mode(self, mode: str) -> None:
        if mode not in {key for key, _ in _ORBIT_MODE_OPTIONS}:
            mode = "free"
        self._orbit_mode = mode
        index = self.cb_orbit_mode.findData(mode)
        if index >= 0:
            with QtCore.QSignalBlocker(self.cb_orbit_mode):
                self.cb_orbit_mode.setCurrentIndex(index)

    def _on_orbit_mode_changed(self, index: int) -> None:  # noqa: ANN001 - Qt slot signature
        del index
        data = self.cb_orbit_mode.currentData()
        if not isinstance(data, str):
            return
        if data == self._orbit_mode:
            return
        self._orbit_mode = data
        self._apply_orbit_adjustment(None, None)

    def _on_orbit_slider(self, idx: int, value: float) -> None:
        self._apply_orbit_adjustment(idx, value)

    def _on_orbit_spin(self, idx: int, value: float) -> None:
        self._apply_orbit_adjustment(idx, value)

    def _on_coverage_angle(self, value: float) -> None:
        clamped = _clamp(float(value), 0.0, 360.0)
        if abs(clamped - self._coverage_angle_deg) <= 1e-3:
            self._set_coverage_angle(clamped)
            return
        self._set_coverage_angle(clamped)
        self._apply_orbit_adjustment(None, None)

    def _on_coverage_offset(self, value: float) -> None:
        normalized = float(value) % 360.0
        if abs(((normalized - self._coverage_offset_deg + 180.0) % 360.0) - 180.0) <= 1e-3:
            self._set_coverage_offset(normalized)
            return
        self._set_coverage_offset(normalized)
        self._apply_orbit_adjustment(None, None)

    def _apply_orbit_adjustment(
        self,
        source_index: Optional[int],
        value: Optional[float],
        *,
        emit: bool = True,
    ) -> None:
        if self._updating_orbits:
            return
        self._updating_orbits = True
        try:
            diameters = [control.spin.value() for control in self._orbit_controls]
            if (
                source_index is not None
                and value is not None
                and 0 <= source_index < len(diameters)
            ):
                diameters[source_index] = _clamp(value, 0.0, 400.0)
            adjusted = self._apply_mode_transform(diameters, source_index, value)
            baseline = list(adjusted)
            adjusted = self._enforce_orbital_coverage(adjusted, baseline)
            self._update_orbit_controls(adjusted)
            self._last_diameters = list(adjusted)
            self._push_orbital_layout(adjusted)
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

    def _apply_mode_transform(
        self,
        diameters: List[float],
        source_index: Optional[int],
        value: Optional[float],
    ) -> List[float]:
        values = [_clamp(v, 0.0, 400.0) for v in diameters]
        count = len(values)
        if count == 0:
            return values
        previous = self._last_diameters if len(self._last_diameters) == count else values
        mode = self._orbit_mode
        if mode == "free":
            return values
        if mode == "uniform":
            if source_index is not None and value is not None:
                target = _clamp(value, 0.0, 400.0)
            else:
                target = sum(values) / count if count else 0.0
            return [target for _ in range(count)]
        if mode == "ascending":
            return sorted(values)
        if mode == "descending":
            return sorted(values, reverse=True)
        if mode == "random":
            if (
                source_index is None
                or value is None
                or count <= 1
                or not previous
            ):
                return values
            base_previous = previous[min(source_index, len(previous) - 1)]
            diff = _clamp(value, 0.0, 400.0) - base_previous
            if abs(diff) > 1e-3:
                candidates = [i for i in range(count) if i != source_index]
                if candidates:
                    target_idx = self._random.choice(candidates)
                    values[target_idx] = _clamp(values[target_idx] - diff, 0.0, 400.0)
            return values
        if mode == "alternating":
            high = max(values)
            low = min(values)
            if source_index is not None and value is not None:
                if source_index % 2 == 0:
                    high = _clamp(value, 0.0, 400.0)
                else:
                    low = _clamp(value, 0.0, 400.0)
            if high < low:
                high, low = low, high
            for idx in range(count):
                values[idx] = high if idx % 2 == 0 else low
            return values
        if mode == "mirrored":
            half = count // 2 if count else 0
            for idx in range(count):
                pair_idx = (idx + half) % count if count else idx
                if pair_idx == idx:
                    continue
                pair_avg = (values[idx] + values[pair_idx]) / 2.0
                values[idx] = values[pair_idx] = pair_avg
            if source_index is not None and value is not None and count:
                pair_idx = (source_index + half) % count
                mirrored = _clamp(value, 0.0, 400.0)
                values[source_index] = values[pair_idx] = mirrored
            return values
        if mode == "wave":
            avg = sum(values) / count
            if source_index is not None and value is not None:
                amplitude = _clamp(abs(value - avg), 5.0, 120.0)
                phase_offset = (2.0 * math.pi * source_index) / count
            else:
                amplitude = max(20.0, (max(values) - min(values)) * 0.5 if max(values) != min(values) else 20.0)
                phase_offset = 0.0
            for idx in range(count):
                phase = (2.0 * math.pi * idx) / count
                values[idx] = _clamp(avg + amplitude * math.sin(phase - phase_offset), 0.0, 400.0)
            if source_index is not None and value is not None:
                values[source_index] = _clamp(value, 0.0, 400.0)
            return values
        if mode == "focus":
            avg = sum(values) / count
            if source_index is None:
                peak_idx = max(range(count), key=lambda i: values[i]) if values else 0
                peak_value = values[peak_idx] if values else avg
            else:
                peak_idx = source_index
                peak_value = _clamp(value if value is not None else values[peak_idx], 0.0, 400.0)
            spread = max(1.0, count / 3.0)
            for idx in range(count):
                forward = (idx - peak_idx) % count
                backward = (peak_idx - idx) % count
                dist = min(forward, backward)
                attenuation = math.exp(-(dist ** 2) / (2.0 * spread))
                values[idx] = _clamp(avg + (peak_value - avg) * attenuation, 0.0, 400.0)
            return values
        return values

    def _enforce_orbital_coverage(
        self,
        diameters: Sequence[float],
        baseline: Optional[Sequence[float]] = None,
    ) -> List[float]:
        if self._orbit_mode == "free":
            return list(diameters)
        values = [_clamp(float(v), 0.0, 400.0) for v in diameters]
        count = len(values)
        if count <= 1:
            return values
        baseline_values: List[float]
        if baseline is None:
            baseline_values = list(values)
        else:
            baseline_values = [_clamp(float(v), 0.0, 400.0) for v in baseline]
            if len(baseline_values) < count:
                baseline_values.extend(values[len(baseline_values) :])
            elif len(baseline_values) > count:
                baseline_values = baseline_values[:count]
        spans = self._effective_spans(count, values)
        if not spans:
            return values
        mask = self._active_span_mask(count)
        if not any(mask):
            return values
        # Iteratively push neighbouring circles outwards until every span is
        # covered or all controls have reached their maximum range.
        for _ in range(count * 3):
            adjusted = False
            for idx in range(count):
                if not mask[idx]:
                    continue
                next_idx = (idx + 1) % count
                span = max(0.0, float(spans[idx])) * 2.0
                current = values[idx] + values[next_idx]
                if current + 1e-3 >= span:
                    continue
                deficit = span - current
                head_current = 400.0 - values[idx]
                head_next = 400.0 - values[next_idx]
                if head_current <= 1e-3 and head_next <= 1e-3:
                    continue
                order = [
                    (baseline_values[idx], head_current, idx),
                    (baseline_values[next_idx], head_next, next_idx),
                ]
                order.sort(key=lambda item: (item[0], item[1]))
                remaining = deficit
                for _base, headroom, target_idx in reversed(order):
                    if remaining <= 1e-3:
                        break
                    if headroom <= 1e-3:
                        continue
                    delta = min(headroom, remaining)
                    values[target_idx] += delta
                    remaining -= delta
                    adjusted = True
            if not adjusted:
                break
        return values

    def _effective_spans(self, count: int, diameters: Sequence[float]) -> List[float]:
        spans = list(self._orbital_spans[:count])
        if len(spans) < count:
            avg_radius = sum(max(0.0, d * 0.5) for d in diameters) / max(1, count)
            default_span = max(20.0, avg_radius * 2.2)
            while len(spans) < count:
                spans.append(default_span)
        return spans

    def _active_span_mask(self, count: int) -> List[bool]:
        if count <= 0:
            return []
        if not self._orbital_angles or len(self._orbital_angles) < count:
            return [True] * count
        gap = _clamp(self._coverage_angle_deg, 0.0, 360.0)
        if gap <= 1e-3:
            return [True] * count
        if gap >= 360.0 - 1e-3:
            return [False] * count
        offset = self._coverage_offset_deg % 360.0
        mask: List[bool] = []
        for idx in range(count):
            a = self._orbital_angles[idx % len(self._orbital_angles)]
            b = self._orbital_angles[(idx + 1) % len(self._orbital_angles)]
            mid = self._mid_angle(a, b)
            mask.append(not self._angle_in_gap(mid, offset, gap))
        return mask

    def _mid_angle(self, a_deg: float, b_deg: float) -> float:
        a_rad = math.radians(a_deg)
        b_rad = math.radians(b_deg)
        x = math.cos(a_rad) + math.cos(b_rad)
        y = math.sin(a_rad) + math.sin(b_rad)
        if abs(x) < 1e-6 and abs(y) < 1e-6:
            return (a_deg + b_deg) * 0.5 % 360.0
        return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0

    def _angle_in_gap(self, angle: float, offset: float, gap: float) -> bool:
        angle = angle % 360.0
        start = offset % 360.0
        end = (start + gap) % 360.0
        if gap >= 360.0 - 1e-3:
            return True
        if start <= end:
            return start <= angle <= end
        return angle >= start or angle <= end

    def _update_orbit_controls(self, diameters: Sequence[float]) -> None:
        for control, value in zip(self._orbit_controls, diameters):
            clamped = _clamp(float(value), 0.0, 400.0)
            with QtCore.QSignalBlocker(control.spin):
                control.spin.setValue(clamped)
            with QtCore.QSignalBlocker(control.slider):
                control.slider.setValue(int(round(clamped)))

    def _push_orbital_layout(self, diameters: Sequence[float]) -> None:
        hub = getattr(self, "_donut_hub", None)
        if hub is None or not hasattr(hub, "configure_orbital_layout"):
            return
        try:
            hub.configure_orbital_layout(
                diameters,
                coverage_angle=self._coverage_angle_deg,
                coverage_offset=self._coverage_offset_deg,
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
