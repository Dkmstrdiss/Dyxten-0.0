import math
from functools import partial

from PyQt5 import QtWidgets, QtCore

from .widgets import row, SliderWithMax, SubProfilePanel
from .config import DEFAULTS, TOOLTIPS

POPULAR_ORIENTATION_ANGLES = [-180, -135, -120, -90, -60, -45, -30, -15, 0, 15, 30, 45, 60, 90, 120, 135, 180]

PHASE_MODE_CHOICES = [
    ("Aucun déphasage", "none"),
    ("Index linéaire", "by_index"),
    ("Rayon (distance au centre)", "by_radius"),
    ("Longitude (angle autour de Y)", "by_longitude"),
    ("Latitude (hauteur)", "by_latitude"),
    ("Damier pair/impair", "checkerboard"),
    ("Aléatoire reproductible", "random"),
]


class DynamicsTab(QtWidgets.QWidget):
    changed = QtCore.pyqtSignal(dict)
    def __init__(self):
        super().__init__()
        d = DEFAULTS["dynamics"]

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        self._subprofile_panel = SubProfilePanel("Sous-profil dynamique")
        outer.addWidget(self._subprofile_panel)

        form_container = QtWidgets.QWidget()
        fl = QtWidgets.QFormLayout(form_container)
        fl.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(form_container)

        self.rows = {}
        self._orientation_snap_angles = [
            int(v) for v in d.get("orientationSnapAngles", POPULAR_ORIENTATION_ANGLES)
        ] or list(POPULAR_ORIENTATION_ANGLES)

        self.rotX = SliderWithMax(d.get("rotX", 0.0), d.get("rotXMax", 360.0))
        self.rotY = SliderWithMax(d.get("rotY", 0.0), d.get("rotYMax", 360.0))
        self.rotZ = SliderWithMax(d.get("rotZ", 0.0), d.get("rotZMax", 360.0))
        self.sp_pulseA = QtWidgets.QDoubleSpinBox(); self.sp_pulseA.setRange(0.0,1.0); self.sp_pulseA.setSingleStep(0.01); self.sp_pulseA.setValue(d["pulseA"])
        self.sp_pulseW = QtWidgets.QDoubleSpinBox(); self.sp_pulseW.setRange(0.0,20.0); self.sp_pulseW.setValue(d["pulseW"])
        self.sp_pulsePhase = QtWidgets.QDoubleSpinBox(); self.sp_pulsePhase.setRange(0.0,360.0); self.sp_pulsePhase.setValue(d["pulsePhaseDeg"])
        self.cb_rotPhaseMode = QtWidgets.QComboBox()
        for label, value in PHASE_MODE_CHOICES:
            self.cb_rotPhaseMode.addItem(label, value)
        self._set_combo_value(self.cb_rotPhaseMode, d.get("rotPhaseMode", "none"))
        self.sp_rotPhaseDeg = QtWidgets.QDoubleSpinBox(); self.sp_rotPhaseDeg.setRange(0.0,360.0); self.sp_rotPhaseDeg.setValue(d["rotPhaseDeg"])
        self.rows["rotX"] = row(fl, "Rotation X (°/s)", self.rotX, TOOLTIPS["dynamics.rotX"], lambda: self._reset_rotation("X"))
        self.rows["rotY"] = row(fl, "Rotation Y (°/s)", self.rotY, TOOLTIPS["dynamics.rotY"], lambda: self._reset_rotation("Y"))
        self.rows["rotZ"] = row(fl, "Rotation Z (°/s)", self.rotZ, TOOLTIPS["dynamics.rotZ"], lambda: self._reset_rotation("Z"))
        row(fl, "Respiration (amplitude)", self.sp_pulseA, TOOLTIPS["dynamics.pulseA"], lambda: self.sp_pulseA.setValue(d["pulseA"]))
        row(fl, "Respiration (vitesse)", self.sp_pulseW, TOOLTIPS["dynamics.pulseW"], lambda: self.sp_pulseW.setValue(d["pulseW"]))
        row(fl, "Déphasage respiration (°)", self.sp_pulsePhase, TOOLTIPS["dynamics.pulsePhaseDeg"], lambda: self.sp_pulsePhase.setValue(d["pulsePhaseDeg"]))
        self.rows["rotPhaseMode"] = row(
            fl,
            "Déphasage (rotations & respiration)",
            self.cb_rotPhaseMode,
            TOOLTIPS["dynamics.rotPhaseMode"],
            lambda: self._set_combo_value(self.cb_rotPhaseMode, d.get("rotPhaseMode", "none")),
        )
        self.rows["rotPhaseDeg"] = row(fl, "Amplitude du déphasage (°)", self.sp_rotPhaseDeg, TOOLTIPS["dynamics.rotPhaseDeg"], lambda: self.sp_rotPhaseDeg.setValue(d["rotPhaseDeg"]))

        self._snap_targets = {}
        self._snap_timers = {}
        self._orient_labels = {}
        self.orient_dials = {}

        for axis in ("X", "Y", "Z"):
            dial = QtWidgets.QDial()
            dial.setRange(-180, 180)
            dial.setWrapping(True)
            dial.setNotchesVisible(True)
            dial.setSingleStep(1)
            value = d.get(f"orient{axis}Deg", 0.0)
            dial.setValue(int(value))
            self._install_angle_snap(dial, self._orientation_snap_angles)

            label = QtWidgets.QLabel(f"{int(value):+d}°")
            label.setAlignment(QtCore.Qt.AlignCenter)
            label.setMinimumWidth(48)
            label.setObjectName("DialValueLabel")

            snap_btn = QtWidgets.QToolButton()
            snap_btn.setText("⚙")
            snap_btn.setCursor(QtCore.Qt.PointingHandCursor)
            snap_btn.setToolTip(
                "Configurer les crans d’accroche en multiples de π dans une fenêtre dédiée."
            )
            snap_btn.setFixedSize(26, 26)
            snap_btn.setStyleSheet(
                "QToolButton{border:1px solid #7aa7c7;border-radius:13px;padding:0;"
                "background:#e6f2fb;color:#2b6ea8;font-weight:bold;}"
                "QToolButton:hover{background:#d8ecfa;}"
            )
            snap_btn.clicked.connect(
                lambda checked=False, ax=axis: self._configure_snap_targets(ax)
            )

            container = QtWidgets.QWidget()
            lay = QtWidgets.QHBoxLayout(container)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(6)
            lay.addWidget(dial, 1)
            side = QtWidgets.QVBoxLayout()
            side.setContentsMargins(0, 0, 0, 0)
            side.setSpacing(4)
            side.addWidget(label, alignment=QtCore.Qt.AlignCenter)
            side.addWidget(snap_btn, alignment=QtCore.Qt.AlignCenter)
            lay.addLayout(side, 0)

            key = f"orient{axis}Deg"
            tip_key = f"dynamics.orient{axis}Deg"
            self.rows[key] = row(
                fl,
                f"Orientation {axis} (°)",
                container,
                TOOLTIPS[tip_key],
                lambda ax=axis: self._reset_orientation(ax),
            )
            self.orient_dials[axis] = dial
            self._orient_labels[axis] = label
            dial.valueChanged.connect(lambda value, ax=axis: self._on_dial_changed(ax, value))

        for w in [self.sp_pulseA,self.sp_pulseW,self.sp_pulsePhase,self.cb_rotPhaseMode,self.sp_rotPhaseDeg]:
            if isinstance(w, QtWidgets.QComboBox):
                w.currentIndexChanged.connect(self.emit_delta)
            else:
                w.valueChanged.connect(self.emit_delta)

        for control in (self.rotX, self.rotY, self.rotZ):
            control.valueChanged.connect(self.emit_delta)
            control.maxChanged.connect(self.emit_delta)

        self.cb_rotPhaseMode.currentIndexChanged.connect(self._update_row_states)
        self._update_row_states()
        self._sync_subprofile_state()
    def collect(self):
        data = dict(
                    rotX=self.rotX.value(), rotY=self.rotY.value(), rotZ=self.rotZ.value(),
                    rotXMax=self.rotX.maximum(), rotYMax=self.rotY.maximum(), rotZMax=self.rotZ.maximum(),
                    pulseA=self.sp_pulseA.value(), pulseW=self.sp_pulseW.value(),
                    pulsePhaseDeg=self.sp_pulsePhase.value(),
                    rotPhaseMode=self.cb_rotPhaseMode.currentData() or "none", rotPhaseDeg=self.sp_rotPhaseDeg.value(),
                    orientXDeg=self.orient_dials["X"].value(),
                    orientYDeg=self.orient_dials["Y"].value(),
                    orientZDeg=self.orient_dials["Z"].value(),
                    orientationSnapAngles=list(self._orientation_snap_angles),
                )
        return data

    def collect_orientations(self):
        return dict(
            orientXDeg=self.orient_dials["X"].value(),
            orientYDeg=self.orient_dials["Y"].value(),
            orientZDeg=self.orient_dials["Z"].value(),
        )
    def set_defaults(self, cfg):
        cfg = cfg or {}
        d = DEFAULTS["dynamics"]
        def val(key):
            return cfg.get(key, d[key])

        snap_cfg = cfg.get("orientationSnapAngles", d.get("orientationSnapAngles", POPULAR_ORIENTATION_ANGLES))
        self._orientation_snap_angles = [int(v) for v in snap_cfg] or list(POPULAR_ORIENTATION_ANGLES)
        self._apply_snap_targets()

        self.rotX.setMaximum(float(cfg.get("rotXMax", d.get("rotXMax", 360.0))))
        self.rotY.setMaximum(float(cfg.get("rotYMax", d.get("rotYMax", 360.0))))
        self.rotZ.setMaximum(float(cfg.get("rotZMax", d.get("rotZMax", 360.0))))

        self.rotX.setValue(float(val("rotX")))
        self.rotY.setValue(float(val("rotY")))
        self.rotZ.setValue(float(val("rotZ")))
        with QtCore.QSignalBlocker(self.sp_pulseA):
            self.sp_pulseA.setValue(float(val("pulseA")))
        with QtCore.QSignalBlocker(self.sp_pulseW):
            self.sp_pulseW.setValue(float(val("pulseW")))
        with QtCore.QSignalBlocker(self.sp_pulsePhase):
            self.sp_pulsePhase.setValue(float(val("pulsePhaseDeg")))
        self._set_combo_value(self.cb_rotPhaseMode, str(val("rotPhaseMode")))
        with QtCore.QSignalBlocker(self.sp_rotPhaseDeg):
            self.sp_rotPhaseDeg.setValue(float(val("rotPhaseDeg")))
        for axis in ("X", "Y", "Z"):
            dial = self.orient_dials[axis]
            label = self._orient_labels[axis]
            target = cfg.get(f"orient{axis}Deg", d.get(f"orient{axis}Deg", 0.0))
            with QtCore.QSignalBlocker(dial):
                dial.setValue(int(target))
            label.setText(f"{int(target):+d}°")
        self._sync_subprofile_state()
    def set_enabled(self, context: dict): pass

    def emit_delta(self, *a):
        self._update_row_states()
        payload = {"dynamics": self.collect()}
        self._sync_subprofile_state()
        self.changed.emit(payload)

    # ------------------------------------------------------------------ utils
    def attach_subprofile_manager(self, manager):
        self._subprofile_panel.bind(
            manager=manager,
            section="dynamics",
            defaults=DEFAULTS["dynamics"],
            collect_cb=self.collect,
            apply_cb=self.set_defaults,
            on_change=self.emit_delta,
        )
        self._sync_subprofile_state()

    def _sync_subprofile_state(self):
        if hasattr(self, "_subprofile_panel") and self._subprofile_panel is not None:
            self._subprofile_panel.sync_from_data(self.collect())

    def _set_combo_value(self, combo: QtWidgets.QComboBox, value: str, fallback=None):
        if combo is None:
            return
        target = value
        if target is None and fallback is not None:
            target = fallback
        with QtCore.QSignalBlocker(combo):
            index = combo.findData(target)
            if index == -1 and fallback is not None:
                index = combo.findData(fallback)
            if index == -1:
                index = combo.findData(DEFAULTS["dynamics"].get("rotPhaseMode", "none"))
            if index == -1:
                index = 0
            combo.setCurrentIndex(max(0, index))

    def _set_row_visible(self, key: str, visible: bool):
        row_widget = self.rows.get(key)
        if row_widget is None:
            return
        row_widget.setVisible(visible)
        label = getattr(row_widget, "_form_label", None)
        if label is not None:
            label.setVisible(visible)

    def _update_row_states(self, *args):
        mode = self.cb_rotPhaseMode.currentData() or "none"
        show_phase = mode != "none"
        self._set_row_visible("rotPhaseDeg", show_phase)
        self.sp_rotPhaseDeg.setEnabled(show_phase)
    def _reset_rotation(self, axis: str):
        defaults = DEFAULTS["dynamics"]
        control = getattr(self, f"rot{axis}")
        max_key = f"rot{axis}Max"
        control.setMaximum(float(defaults.get(max_key, 360.0)))
        control.setValue(float(defaults.get(f"rot{axis}", 0.0)))
        self.emit_delta()

    def _install_angle_snap(self, slider: QtWidgets.QAbstractSlider, targets):
        if not targets:
            return
        self._snap_targets[slider] = sorted(set(int(v) for v in targets))
        slider.sliderReleased.connect(lambda: self._snap_slider(slider))
        timer = QtCore.QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(partial(self._snap_slider, slider))
        self._snap_timers[slider] = timer
        slider.installEventFilter(self)

    def _apply_snap_targets(self):
        if not self._orientation_snap_angles:
            self._orientation_snap_angles = list(POPULAR_ORIENTATION_ANGLES)
        targets = sorted(set(int(v) for v in self._orientation_snap_angles))
        for dial in self.orient_dials.values():
            self._snap_targets[dial] = targets
            self._schedule_snap(dial, cancel_only=True)

    def _snap_slider(self, slider: QtWidgets.QAbstractSlider):
        targets = self._snap_targets.get(slider)
        if not targets:
            return
        self._schedule_snap(slider, cancel_only=True)
        value = slider.value()
        snap = min(targets, key=lambda t: abs(t - value))
        if snap != value:
            with QtCore.QSignalBlocker(slider):
                slider.setValue(int(snap))
            for axis, dial in self.orient_dials.items():
                if dial is slider:
                    self._orient_labels[axis].setText(f"{int(snap):+d}°")
                    break
            self.emit_delta()

    def _schedule_snap(self, slider: QtWidgets.QAbstractSlider, delay: int = 180, cancel_only: bool = False):
        timer = self._snap_timers.get(slider)
        if timer is None:
            return
        if cancel_only:
            timer.stop()
            return
        timer.start(max(0, delay))

    def _on_dial_changed(self, axis: str, value: int):
        label = self._orient_labels.get(axis)
        if label is not None:
            label.setText(f"{int(value):+d}°")
        self.emit_delta()

    def _reset_orientation(self, axis: str):
        default = DEFAULTS["dynamics"].get(f"orient{axis}Deg", 0.0)
        dial = self.orient_dials[axis]
        with QtCore.QSignalBlocker(dial):
            dial.setValue(int(default))
        self._orient_labels[axis].setText(f"{int(default):+d}°")
        self.emit_delta()

    def _configure_snap_targets(self, axis: str):
        dlg = OrientationSnapDialog(axis, self._orientation_snap_angles, self)
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return
        dial = self.orient_dials[axis]
        label = self._orient_labels[axis]
        updated = False
        if dlg.values:
            self._orientation_snap_angles = dlg.values
            self._apply_snap_targets()
            updated = True
        if dlg.selected_deg is not None:
            angle = int(dlg.selected_deg)
            with QtCore.QSignalBlocker(dial):
                dial.setValue(angle)
            label.setText(f"{angle:+d}°")
            updated = True
        if updated:
            self.emit_delta()

    # ------------------------------------------------------------------ Qt
    def eventFilter(self, obj, event):
        if isinstance(obj, QtWidgets.QAbstractSlider) and obj in self._snap_targets:
            etype = event.type()
            if etype == QtCore.QEvent.Wheel:
                self._schedule_snap(obj, delay=220)
            elif etype == QtCore.QEvent.KeyPress:
                key = event.key()
                if key in (QtCore.Qt.Key_Left, QtCore.Qt.Key_Right, QtCore.Qt.Key_Up, QtCore.Qt.Key_Down):
                    auto_repeat = getattr(event, "isAutoRepeat", lambda: False)()
                    self._schedule_snap(obj, delay=220 if auto_repeat else 160)
            elif etype == QtCore.QEvent.KeyRelease:
                key = event.key()
                if key in (QtCore.Qt.Key_Left, QtCore.Qt.Key_Right, QtCore.Qt.Key_Up, QtCore.Qt.Key_Down):
                    self._schedule_snap(obj, delay=80)
        return super().eventFilter(obj, event)


class OrientationSnapDialog(QtWidgets.QDialog):
    def __init__(self, axis: str, angles, parent=None):
        super().__init__(parent)
        self.setObjectName("OrientationSnapDialog")
        self.setWindowTitle(f"Crans d’orientation — axe {axis}")
        self.setModal(True)
        self.resize(420, 360)

        self._default_angles = list(POPULAR_ORIENTATION_ANGLES)
        self._steps = {self._step_from_deg(int(round(a))) for a in angles}
        self.values = []
        self.selected_deg = None

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        msg = QtWidgets.QLabel(
            "Utilisez le curseur pour sélectionner un angle (multiples de π) puis ajoutez-le à la liste des crans."
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setRange(-48, 48)
        self.slider.setTickInterval(1)
        self.slider.setPageStep(1)
        self.slider.valueChanged.connect(self._update_preview)

        self.preview = QtWidgets.QLabel()
        self.preview.setAlignment(QtCore.Qt.AlignCenter)
        self.preview.setStyleSheet("font-weight:600;color:#1f3a52;")

        slider_box = QtWidgets.QVBoxLayout()
        slider_box.setSpacing(4)
        slider_box.addWidget(self.slider)
        slider_box.addWidget(self.preview)
        slider_widget = QtWidgets.QWidget()
        slider_widget.setLayout(slider_box)
        layout.addWidget(slider_widget)

        self.list = QtWidgets.QListWidget()
        self.list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.list.currentRowChanged.connect(self._on_select_row)
        layout.addWidget(self.list, 1)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(8)
        self.btn_add = QtWidgets.QPushButton("Ajouter")
        self.btn_add.clicked.connect(self._add_current)
        self.btn_replace = QtWidgets.QPushButton("Remplacer")
        self.btn_replace.clicked.connect(self._replace_current)
        self.btn_remove = QtWidgets.QPushButton("Supprimer")
        self.btn_remove.clicked.connect(self._remove_selected)
        self.btn_reset = QtWidgets.QPushButton("Réinitialiser")
        self.btn_reset.clicked.connect(self._reset_defaults)
        for btn in (self.btn_add, self.btn_replace, self.btn_remove, self.btn_reset):
            btn_row.addWidget(btn)
        layout.addLayout(btn_row)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setStyleSheet("""
            QDialog#OrientationSnapDialog, QDialog#OrientationSnapDialog QWidget {
                color: #15151f;
                background-color: #ffffff;
            }
            QPushButton {
                color: #15151f;
            }
            QListWidget {
                background-color: #f6f9ff;
                border: 1px solid #d3e0ef;
            }
        """)

        if not self._steps:
            self._steps = {self._step_from_deg(a) for a in self._default_angles}
        self._populate_list()
        self._update_preview(self.slider.value())

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _step_from_deg(deg: int) -> int:
        return max(-48, min(48, int(round(deg / 15))))

    @staticmethod
    def _deg_from_step(step: int) -> int:
        return int(step * 15)

    @staticmethod
    def _pi_str(step: int) -> str:
        if step == 0:
            return "0"
        num = abs(step)
        denom = 12
        gcd = math.gcd(num, denom)
        num //= gcd
        denom //= gcd
        sign = "-" if step < 0 else ""
        if num == 0:
            return "0"
        if denom == 1:
            return f"{sign}{num}π"
        coeff = "" if num == 1 else f"{num}"
        return f"{sign}{coeff}π/{denom}"

    def _format_step(self, step: int) -> str:
        deg = self._deg_from_step(step)
        return f"{deg:+d}° ({self._pi_str(step)})"

    def _populate_list(self):
        self.list.blockSignals(True)
        self.list.clear()
        for step in sorted(self._steps):
            item = QtWidgets.QListWidgetItem(self._format_step(step))
            item.setData(QtCore.Qt.UserRole, step)
            self.list.addItem(item)
        self.list.blockSignals(False)
        if self.list.count():
            self.list.setCurrentRow(0)

    # ---------------------------------------------------------------- actions
    def _update_preview(self, step: int):
        self.preview.setText(self._format_step(step))

    def _current_step(self) -> int:
        return int(self.slider.value())

    def _selected_step(self):
        item = self.list.currentItem()
        if item is None:
            return None
        return int(item.data(QtCore.Qt.UserRole))

    def _on_select_row(self, row: int):
        if row < 0:
            return
        step = self._selected_step()
        if step is None:
            return
        self.slider.blockSignals(True)
        self.slider.setValue(step)
        self.slider.blockSignals(False)
        self._update_preview(step)

    def _add_current(self):
        step = self._current_step()
        self._steps.add(step)
        self._populate_list()
        self._select_step(step)

    def _replace_current(self):
        step = self._current_step()
        selected = self._selected_step()
        if selected is None:
            self._add_current()
            return
        if selected in self._steps:
            self._steps.discard(selected)
        self._steps.add(step)
        self._populate_list()
        self._select_step(step)

    def _remove_selected(self):
        selected = self._selected_step()
        if selected is None:
            return
        self._steps.discard(selected)
        self._populate_list()

    def _reset_defaults(self):
        self._steps = {self._step_from_deg(a) for a in self._default_angles}
        self._populate_list()

    def _select_step(self, step: int):
        for row in range(self.list.count()):
            item = self.list.item(row)
            if item and int(item.data(QtCore.Qt.UserRole)) == step:
                self.list.setCurrentRow(row)
                break

    def _on_accept(self):
        if not self.list.count():
            QtWidgets.QMessageBox.warning(
                self,
                "Angles manquants",
                "Ajoutez au moins un angle avant de valider.",
            )
            return
        steps = [int(self.list.item(i).data(QtCore.Qt.UserRole)) for i in range(self.list.count())]
        degrees = sorted({self._deg_from_step(step) for step in steps})
        self.values = [deg for deg in degrees if -720 <= deg <= 720]
        if not self.values:
            QtWidgets.QMessageBox.warning(
                self,
                "Angles invalides",
                "Aucun angle valide détecté.",
            )
            return
        self.selected_deg = self._deg_from_step(self._current_step())
        self.accept()
