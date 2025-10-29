"""Tab used to link parameters to automated controllers."""

from __future__ import annotations

import math
import struct
import time
from typing import Dict, List, Optional

from PyQt5 import QtCore, QtWidgets

try:  # pragma: no cover - optional multimedia support
    from PyQt5 import QtMultimedia
except Exception:  # pragma: no cover - fallback when QtMultimedia unavailable
    QtMultimedia = None  # type: ignore

try:
    from .link_registry import LINK_REGISTRY, LinkableControl
except ImportError:  # pragma: no cover - package aliasing
    from core.control.link_registry import LINK_REGISTRY, LinkableControl  # type: ignore


class AudioLevelMonitor(QtCore.QObject):
    """Monitor microphone audio level if QtMultimedia is available."""

    levelChanged = QtCore.pyqtSignal(float)
    availabilityChanged = QtCore.pyqtSignal(bool, str)

    def __init__(self, parent: Optional[QtCore.QObject] = None):
        super().__init__(parent)
        self._available = False
        self._audio_input = None
        self._device = None
        self._format = None
        self._status_message = "Audio inactif"
        if QtMultimedia is None:  # pragma: no cover - environment dependent
            self._status_message = "QtMultimedia indisponible"
            self.availabilityChanged.emit(False, self._status_message)
            return
        try:
            self._init_audio()
        except Exception as exc:  # pragma: no cover - hardware dependent
            self._status_message = str(exc)
            self.availabilityChanged.emit(False, self._status_message)

    def _init_audio(self):  # pragma: no cover - depends on system audio
        info = QtMultimedia.QAudioDeviceInfo.defaultInputDevice()
        if info is None or info.isNull():
            raise RuntimeError("Aucun périphérique audio d’entrée détecté")
        format_ = QtMultimedia.QAudioFormat()
        format_.setSampleRate(16000)
        format_.setChannelCount(1)
        format_.setSampleSize(16)
        format_.setCodec("audio/pcm")
        format_.setByteOrder(QtMultimedia.QAudioFormat.LittleEndian)
        format_.setSampleType(QtMultimedia.QAudioFormat.SignedInt)
        if not info.isFormatSupported(format_):
            format_ = info.nearestFormat(format_)
        self._format = format_
        self._audio_input = QtMultimedia.QAudioInput(info, format_, self)
        self._audio_input.setBufferSize(4096)
        device = self._audio_input.start()
        if device is None:
            raise RuntimeError("Impossible de démarrer la capture audio")
        self._device = device
        device.readyRead.connect(self._on_ready_read)
        self._available = True
        self._status_message = "Capture audio active"
        self.availabilityChanged.emit(True, self._status_message)

    def _on_ready_read(self):  # pragma: no cover - depends on system audio
        if QtMultimedia is None:
            return
        if self._device is None or self._format is None:
            return
        buffer = self._device.readAll()
        if not buffer:
            return
        data = bytes(buffer)
        if not data:
            return
        sample_size = self._format.sampleSize()
        sample_type = self._format.sampleType()
        channel_count = max(1, self._format.channelCount())
        stride = max(1, sample_size // 8 * channel_count)
        if stride <= 0:
            return
        peak = 0.0
        if sample_type == QtMultimedia.QAudioFormat.Float:
            step = 4 * channel_count
            if step <= 0:
                return
            for index in range(0, len(data) - step + 1, step):
                chunk = data[index : index + 4]
                value = struct.unpack("<f", chunk)[0]
                peak = max(peak, abs(float(value)))
        elif sample_type == QtMultimedia.QAudioFormat.UnSignedInt:
            max_value = float(2 ** sample_size - 1)
            if max_value <= 0:
                return
            half = max_value / 2.0
            for index in range(0, len(data) - stride + 1, stride):
                chunk = data[index : index + sample_size // 8]
                value = int.from_bytes(chunk, byteorder="little", signed=False)
                normalized = abs(value - half) / half
                peak = max(peak, normalized)
        else:
            max_value = float(2 ** (sample_size - 1))
            if max_value <= 0:
                return
            for index in range(0, len(data) - stride + 1, stride):
                chunk = data[index : index + sample_size // 8]
                value = int.from_bytes(chunk, byteorder="little", signed=True)
                peak = max(peak, abs(value) / max_value)
        peak = max(0.0, min(1.0, peak))
        self.levelChanged.emit(peak)

    @property
    def available(self) -> bool:
        return self._available

    @property
    def status(self) -> str:
        return self._status_message


class LinkControllerTab(QtWidgets.QWidget):
    """Tab providing waveform-driven control over registered widgets."""

    changed = QtCore.pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.registry = LINK_REGISTRY
        self._applying = False
        self._last_values: Dict[str, float] = {}
        self._pending_identifiers: List[str] = []
        self._start_time = time.monotonic()
        self._push_active = False
        self._audio_level = 0.0

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        instructions = QtWidgets.QLabel(
            "Clic droit sur un slider, un dial ou une boîte numérique pour les lier au contrôleur."
        )
        instructions.setWordWrap(True)
        instructions.setObjectName("LinkControllerInstructions")
        outer.addWidget(instructions)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["Onglet", "Contrôle", "Paramètre", "Type"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        outer.addWidget(self.tree, 1)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(6)
        self.btn_remove = QtWidgets.QPushButton("Retirer la sélection")
        self.btn_clear = QtWidgets.QPushButton("Tout retirer")
        btn_row.addWidget(self.btn_remove)
        btn_row.addWidget(self.btn_clear)
        btn_row.addStretch(1)
        outer.addLayout(btn_row)

        waveform_box = QtWidgets.QGroupBox("Signal de modulation")
        waveform_layout = QtWidgets.QFormLayout(waveform_box)
        waveform_layout.setContentsMargins(12, 12, 12, 12)
        waveform_layout.setSpacing(8)

        self.cb_waveform = QtWidgets.QComboBox()
        self.cb_waveform.addItem("Sinusoïde classique", "sine")
        self.cb_waveform.addItem("Triangle symétrique", "triangle")
        self.cb_waveform.addItem("Onde carrée", "square")
        self.cb_waveform.addItem("Dent de scie", "saw")
        self.cb_waveform.addItem("Mouvement harmonique mixte", "lissajous")
        self.cb_waveform.addItem("Sortie audio du PC", "audio")
        waveform_layout.addRow("Forme d’onde", self.cb_waveform)

        self.sp_amplitude = QtWidgets.QDoubleSpinBox()
        self.sp_amplitude.setRange(0.0, 1.0)
        self.sp_amplitude.setSingleStep(0.05)
        self.sp_amplitude.setValue(0.5)
        waveform_layout.addRow("Amplitude", self.sp_amplitude)

        self.sp_frequency = QtWidgets.QDoubleSpinBox()
        self.sp_frequency.setRange(0.0, 10.0)
        self.sp_frequency.setDecimals(3)
        self.sp_frequency.setSingleStep(0.1)
        self.sp_frequency.setValue(0.5)
        waveform_layout.addRow("Fréquence (Hz)", self.sp_frequency)

        self.sp_phase = QtWidgets.QDoubleSpinBox()
        self.sp_phase.setRange(0.0, 360.0)
        self.sp_phase.setSingleStep(5.0)
        waveform_layout.addRow("Phase (°)", self.sp_phase)

        self.sp_offset = QtWidgets.QDoubleSpinBox()
        self.sp_offset.setRange(-1.0, 1.0)
        self.sp_offset.setSingleStep(0.05)
        waveform_layout.addRow("Décalage", self.sp_offset)

        self.sp_smoothing = QtWidgets.QDoubleSpinBox()
        self.sp_smoothing.setRange(0.0, 1.0)
        self.sp_smoothing.setSingleStep(0.05)
        self.sp_smoothing.setValue(0.5)
        waveform_layout.addRow("Lissage", self.sp_smoothing)

        self.sp_audio_gain = QtWidgets.QDoubleSpinBox()
        self.sp_audio_gain.setRange(0.1, 5.0)
        self.sp_audio_gain.setSingleStep(0.1)
        self.sp_audio_gain.setValue(1.0)
        waveform_layout.addRow("Gain audio", self.sp_audio_gain)

        outer.addWidget(waveform_box)

        control_box = QtWidgets.QGroupBox("Contrôle de liaison")
        control_layout = QtWidgets.QVBoxLayout(control_box)
        control_layout.setContentsMargins(12, 12, 12, 12)
        control_layout.setSpacing(8)

        toggle_row = QtWidgets.QHBoxLayout()
        toggle_row.setContentsMargins(0, 0, 0, 0)
        toggle_row.setSpacing(6)
        self.btn_enable = QtWidgets.QPushButton("Activer la modulation")
        self.btn_enable.setCheckable(True)
        toggle_row.addWidget(self.btn_enable, 0)
        toggle_row.addStretch(1)
        control_layout.addLayout(toggle_row)

        self.chk_push_to_talk = QtWidgets.QCheckBox("Activer le push-to-talk")
        control_layout.addWidget(self.chk_push_to_talk)

        ptt_row = QtWidgets.QHBoxLayout()
        ptt_row.setContentsMargins(0, 0, 0, 0)
        ptt_row.setSpacing(6)
        self.btn_push = QtWidgets.QPushButton("Maintenir pour agir")
        self.btn_push.setCheckable(True)
        self.btn_push.setEnabled(False)
        ptt_row.addWidget(self.btn_push, 0)
        self.lbl_push_state = QtWidgets.QLabel("Push-to-talk inactif")
        ptt_row.addWidget(self.lbl_push_state, 1)
        control_layout.addLayout(ptt_row)

        self.lbl_audio_status = QtWidgets.QLabel("Audio inactif")
        control_layout.addWidget(self.lbl_audio_status)

        outer.addWidget(control_box)

        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(30)
        self.timer.timeout.connect(self._on_tick)

        self.monitor = AudioLevelMonitor(self)
        if hasattr(self.monitor, "levelChanged"):
            self.monitor.levelChanged.connect(self._on_audio_level)
        self.monitor.availabilityChanged.connect(self._on_audio_availability)
        self._on_audio_availability(self.monitor.available, self.monitor.status)

        self.registry.selectionChanged.connect(self._refresh_selection)
        self.registry.registryChanged.connect(self._apply_pending_selection)

        self.btn_remove.clicked.connect(self._remove_selected)
        self.btn_clear.clicked.connect(self._clear_selection)
        self.btn_enable.toggled.connect(self._on_toggle)
        self.cb_waveform.currentIndexChanged.connect(self.emit_delta)
        self.sp_amplitude.valueChanged.connect(self.emit_delta)
        self.sp_frequency.valueChanged.connect(self._on_frequency_changed)
        self.sp_phase.valueChanged.connect(self.emit_delta)
        self.sp_offset.valueChanged.connect(self.emit_delta)
        self.sp_smoothing.valueChanged.connect(self.emit_delta)
        self.sp_audio_gain.valueChanged.connect(self.emit_delta)
        self.chk_push_to_talk.stateChanged.connect(self._sync_push_to_talk_state)
        self.btn_push.toggled.connect(self._on_push_toggle)

        self._refresh_selection()
        self._sync_push_to_talk_state()

        self.setStyleSheet(
            """
            QLabel#LinkControllerInstructions {
                color: #1f3550;
            }
            QTreeWidget {
                border: 1px solid #d6e2ed;
                border-radius: 4px;
            }
            QPushButton:checked {
                background-color: #536dfe;
                color: white;
            }
        """
        )

    # ---------------------------------------------------------------- signals
    def _on_audio_level(self, level: float) -> None:
        self._audio_level = max(0.0, min(1.0, float(level))) * self.sp_audio_gain.value()
        self._audio_level = max(0.0, min(1.0, self._audio_level))

    def _on_audio_availability(self, available: bool, status: str) -> None:
        self.lbl_audio_status.setText(status)
        if available:
            self.lbl_audio_status.setStyleSheet("color:#1f7a1f;")
        else:
            self.lbl_audio_status.setStyleSheet("color:#aa3333;")

    def _on_push_toggle(self, active: bool) -> None:
        self._push_active = bool(active)
        self.lbl_push_state.setText("Push-to-talk actif" if active else "Push-to-talk inactif")
        self.emit_delta()

    def _sync_push_to_talk_state(self) -> None:
        enabled = self.chk_push_to_talk.isChecked()
        self.btn_push.setEnabled(enabled)
        if not enabled:
            self.btn_push.setChecked(False)
            self._push_active = False
            self.lbl_push_state.setText("Push-to-talk inactif")
        self.emit_delta()

    def _on_frequency_changed(self) -> None:
        self._start_time = time.monotonic()
        self.emit_delta()

    def _on_toggle(self, enabled: bool) -> None:
        if enabled and self.registry.selected_controls():
            self._start_time = time.monotonic()
            self.timer.start()
        else:
            self.timer.stop()
        self.emit_delta()

    def _remove_selected(self) -> None:
        items = self.tree.selectedItems()
        for item in items:
            ident = item.data(0, QtCore.Qt.UserRole)
            if not ident:
                continue
            self.registry.deselect_identifier(ident)

    def _clear_selection(self) -> None:
        self.registry.clear_selection()

    def _apply_pending_selection(self) -> None:
        if not self._pending_identifiers:
            return
        for ident in self._pending_identifiers:
            if self.registry.control_by_identifier(ident) is None:
                return
        self.registry.set_selection(self._pending_identifiers)
        self._pending_identifiers = []
        self._refresh_selection()

    def _refresh_selection(self) -> None:
        controls = self.registry.selected_controls()
        self.tree.setUpdatesEnabled(False)
        self.tree.clear()
        for control in controls:
            item = QtWidgets.QTreeWidgetItem([
                control.tab,
                control.label,
                control.identifier,
                control.control_type,
            ])
            item.setData(0, QtCore.Qt.UserRole, control.identifier)
            self.tree.addTopLevelItem(item)
        self.tree.resizeColumnToContents(0)
        self.tree.resizeColumnToContents(1)
        self.tree.resizeColumnToContents(2)
        self.tree.setUpdatesEnabled(True)
        active_ids = {control.identifier for control in controls}
        self._last_values = {k: v for k, v in self._last_values.items() if k in active_ids}
        if self.btn_enable.isChecked() and not controls:
            self.btn_enable.setChecked(False)
        self.emit_delta()

    # -------------------------------------------------------------- waveform
    def _on_tick(self) -> None:
        if not self.btn_enable.isChecked():
            return
        if self.chk_push_to_talk.isChecked() and not self._push_active:
            return
        controls = self.registry.selected_controls()
        if not controls:
            self.btn_enable.setChecked(False)
            return
        elapsed = time.monotonic() - self._start_time
        waveform = self.cb_waveform.currentData()
        target = self._waveform_value(waveform, elapsed)
        amplitude = max(0.0, min(1.0, self.sp_amplitude.value()))
        offset = max(-1.0, min(1.0, self.sp_offset.value()))
        smoothing = max(0.0, min(1.0, self.sp_smoothing.value()))

        for control in controls:
            min_val, max_val = control.range_getter()
            if not math.isfinite(min_val) or not math.isfinite(max_val):
                continue
            span = (max_val - min_val) * 0.5
            centre = (max_val + min_val) * 0.5
            desired = centre + span * offset + span * amplitude * target
            desired = max(min_val, min(max_val, desired))

            ident = control.identifier
            if smoothing > 0 and ident in self._last_values:
                previous = self._last_values[ident]
                desired = previous + (desired - previous) * smoothing

            if control.value_type is int:
                desired = int(round(desired))

            try:
                control.value_setter(desired)
                self._last_values[ident] = float(desired)
            except Exception:
                continue

    def _waveform_value(self, waveform: str, elapsed: float) -> float:
        phase = math.radians(self.sp_phase.value())
        freq = self.sp_frequency.value()
        if waveform == "audio":
            return self._audio_level * 2.0 - 1.0
        if waveform == "triangle":
            if freq <= 0:
                return 0.0
            period = 1.0 / freq
            local = ((elapsed + phase / (2 * math.pi * freq)) % period) / period
            return 4 * abs(local - 0.5) - 1.0
        if waveform == "square":
            if freq <= 0:
                return 0.0
            value = math.sin(2 * math.pi * freq * elapsed + phase)
            return 1.0 if value >= 0 else -1.0
        if waveform == "saw":
            if freq <= 0:
                return 0.0
            period = 1.0 / freq
            local = ((elapsed + phase / (2 * math.pi * freq)) % period) / period
            return 2.0 * local - 1.0
        if waveform == "lissajous":
            value = math.sin(2 * math.pi * freq * elapsed + phase)
            value2 = math.cos(4 * math.pi * freq * elapsed + phase * 0.5)
            return max(-1.0, min(1.0, 0.6 * value + 0.4 * value2))
        return math.sin(2 * math.pi * freq * elapsed + phase)

    # ----------------------------------------------------------------- state
    def collect(self) -> dict:
        payload = dict(
            enabled=self.btn_enable.isChecked(),
            waveform=self.cb_waveform.currentData(),
            amplitude=self.sp_amplitude.value(),
            frequency=self.sp_frequency.value(),
            phaseDeg=self.sp_phase.value(),
            offset=self.sp_offset.value(),
            smoothing=self.sp_smoothing.value(),
            pushToTalk=self.chk_push_to_talk.isChecked(),
            selected=[control.identifier for control in self.registry.selected_controls()],
            audioGain=self.sp_audio_gain.value(),
        )
        return payload

    def set_defaults(self, cfg: Optional[dict]):
        cfg = cfg or {}
        self._applying = True
        try:
            with QtCore.QSignalBlocker(self.cb_waveform):
                index = self.cb_waveform.findData(cfg.get("waveform", "sine"))
                if index != -1:
                    self.cb_waveform.setCurrentIndex(index)
            for spin, key in [
                (self.sp_amplitude, "amplitude"),
                (self.sp_frequency, "frequency"),
                (self.sp_phase, "phaseDeg"),
                (self.sp_offset, "offset"),
                (self.sp_smoothing, "smoothing"),
                (self.sp_audio_gain, "audioGain"),
            ]:
                with QtCore.QSignalBlocker(spin):
                    spin.setValue(float(cfg.get(key, spin.value())))
            with QtCore.QSignalBlocker(self.chk_push_to_talk):
                self.chk_push_to_talk.setChecked(bool(cfg.get("pushToTalk", False)))
            with QtCore.QSignalBlocker(self.btn_enable):
                self.btn_enable.setChecked(bool(cfg.get("enabled", False)))
            selected = cfg.get("selected", [])
            if isinstance(selected, (list, tuple)):
                self._pending_identifiers = [str(ident) for ident in selected]
            else:
                self._pending_identifiers = []
            self._apply_pending_selection()
        finally:
            self._applying = False
        self._sync_push_to_talk_state()
        if self.btn_enable.isChecked() and self.registry.selected_controls():
            self.timer.start()
        else:
            self.timer.stop()
        self.emit_delta()

    def attach_subprofile_manager(self, _manager):  # pragma: no cover - compatibility
        return

    def emit_delta(self):
        if self._applying:
            return
        self.changed.emit({"controller": self.collect()})

