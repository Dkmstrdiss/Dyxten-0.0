from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from PyQt5 import QtCore, QtWidgets

from ..donut_hub import DEFAULT_DONUT_BUTTON_COUNT
from .config import DEFAULTS, TOOLTIPS
from .link_registry import register_linkable_widget
from .widgets import SubProfilePanel


@dataclass
class _OrbitControl:
    container: QtWidgets.QWidget
    slider: QtWidgets.QSlider
    spin: QtWidgets.QDoubleSpinBox


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

        self.chk_orbital_enabled = QtWidgets.QCheckBox("Afficher les zones orbitales")
        self.chk_orbital_enabled.setChecked(True)
        self.chk_orbital_enabled.setToolTip(TOOLTIPS.get("indicator.orbitalZones.enabled", ""))
        orbital_layout.addRow(self.chk_orbital_enabled)

        self._orbit_controls: List[_OrbitControl] = []
        orbit_defaults = defaults.get("orbitalZones", {})
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
        for control in self._orbit_controls:
            control.slider.valueChanged.connect(self.emit_delta)
            control.spin.valueChanged.connect(self.emit_delta)

        self._system_tab: Optional[object] = None
        self.set_defaults(defaults)

    # ------------------------------------------------------------------ API
    def set_system_tab(self, system_tab: object) -> None:
        """Allow the indicator tab to update the system configuration."""

        self._system_tab = system_tab

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
        if isinstance(orbital_cfg, dict):
            enabled = bool(orbital_cfg.get("enabled", True))
            raw_diameters = orbital_cfg.get("diameters", [])
            if isinstance(raw_diameters, Sequence):
                diameters = list(raw_diameters)
        with QtCore.QSignalBlocker(self.chk_orbital_enabled):
            self.chk_orbital_enabled.setChecked(enabled)
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
        self.emit_delta()

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
        slider.valueChanged.connect(lambda val, s=spin: s.setValue(float(val)))
        spin.valueChanged.connect(lambda val, sl=slider: sl.setValue(int(round(val))))
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
