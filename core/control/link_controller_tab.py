"""Tab used to link parameters to automated controllers with multi-track support."""

from __future__ import annotations

import collections
import math
import struct
import time
from typing import Callable, Dict, List, Optional

from PyQt5 import QtCore, QtGui, QtWidgets

try:  # pragma: no cover - optional multimedia support
    from PyQt5 import QtMultimedia
except Exception:  # pragma: no cover - fallback when QtMultimedia unavailable
    QtMultimedia = None  # type: ignore

try:
    from .link_registry import LINK_REGISTRY, TRACK_COUNT
except ImportError:  # pragma: no cover - package aliasing
    from core.control.link_registry import LINK_REGISTRY, TRACK_COUNT  # type: ignore


class _BaseAudioMonitor(QtCore.QObject):
    """Base helper capturing peak audio levels from a Qt audio device."""

    levelChanged = QtCore.pyqtSignal(float)
    availabilityChanged = QtCore.pyqtSignal(bool, str)

    def __init__(
        self,
        device_resolver: Callable[[], Optional[object]],
        *,
        inactive_label: str,
        active_label: str,
        failure_label: str,
        parent: Optional[QtCore.QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._available = False
        self._audio_input = None
        self._device = None
        self._format = None
        self._inactive_label = inactive_label
        self._active_label = active_label
        self._failure_label = failure_label
        self._status_message = inactive_label
        self._device_resolver = device_resolver
        if QtMultimedia is None:  # pragma: no cover - environment dependent
            self._status_message = "QtMultimedia indisponible"
            self.availabilityChanged.emit(False, self._status_message)
            return
        try:
            self._init_audio()
        except Exception as exc:  # pragma: no cover - hardware dependent
            self._status_message = str(exc)
            self.availabilityChanged.emit(False, self._status_message)

    # ------------------------------------------------------------------ helpers
    def _init_audio(self) -> None:  # pragma: no cover - depends on system audio
        if QtMultimedia is None:
            return
        info = self._resolve_device()
        if info is None or info.isNull():
            raise RuntimeError(self._failure_label)
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
            raise RuntimeError(self._failure_label)
        self._device = device
        device.readyRead.connect(self._on_ready_read)
        self._available = True
        self._status_message = self._active_label
        self.availabilityChanged.emit(True, self._status_message)

    def _resolve_device(self):  # pragma: no cover - depends on QtMultimedia
        resolver = self._device_resolver
        if resolver is None:
            return None
        result = resolver()
        return result

    def _on_ready_read(self) -> None:  # pragma: no cover - depends on system audio
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

    # ----------------------------------------------------------------- properties
    @property
    def available(self) -> bool:
        return self._available

    @property
    def status(self) -> str:
        return self._status_message


def _resolve_loopback_device() -> Optional[object]:  # pragma: no cover - platform dependent
    if QtMultimedia is None:
        return None
    # Try to find common loopback device names first
    loopback_keywords = [
        "loopback",
        "stereo mix",
        "wave out",
        "what u hear",
        "mixage stéréo",
    ]
    devices = QtMultimedia.QAudioDeviceInfo.availableDevices(QtMultimedia.QAudio.AudioInput)
    fallback = None
    for device in devices:
        name = device.deviceName().lower()
        if any(keyword in name for keyword in loopback_keywords):
            return device
        if fallback is None and not device.isNull():
            fallback = device
    return fallback


class MicrophoneLevelMonitor(_BaseAudioMonitor):
    """Monitor microphone audio level if QtMultimedia is available."""

    def __init__(self, parent: Optional[QtCore.QObject] = None) -> None:
        resolver: Callable[[], Optional[object]]
        if QtMultimedia is None:
            resolver = lambda: None
        else:
            resolver = QtMultimedia.QAudioDeviceInfo.defaultInputDevice
        super().__init__(
            resolver,
            inactive_label="Capture micro inactive",
            active_label="Capture micro active",
            failure_label="Aucun périphérique audio d’entrée détecté",
            parent=parent,
        )


class PlaybackLevelMonitor(_BaseAudioMonitor):
    """Monitor system playback level using loopback capture where available."""

    def __init__(self, parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(
            _resolve_loopback_device,
            inactive_label="Capture lecture inactive",
            active_label="Capture lecture active",
            failure_label="Aucun périphérique de lecture capturable trouvé",
            parent=parent,
        )


class OscilloscopeWidget(QtWidgets.QWidget):
    """Simple oscilloscope rendering the recent modulation curve."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(140)
        self._samples: collections.deque = collections.deque()
        self._time_base = 2.0
        self._vertical_scale = 1.0

    def set_time_base(self, seconds: float) -> None:
        self._time_base = max(0.1, float(seconds))
        self._trim_samples()
        self.update()

    def set_vertical_scale(self, factor: float) -> None:
        self._vertical_scale = max(0.1, float(factor))
        self.update()

    def add_sample(self, value: float, timestamp: float) -> None:
        self._samples.append((timestamp, float(value)))
        self._trim_samples(timestamp)
        self.update()

    def reset(self) -> None:
        self._samples.clear()
        self.update()

    # ------------------------------------------------------------------ internals
    def _trim_samples(self, current_ts: Optional[float] = None) -> None:
        if not self._samples:
            return
        if current_ts is None:
            current_ts = self._samples[-1][0]
        cutoff = current_ts - self._time_base
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.popleft()

    # ---------------------------------------------------------------- painting
    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        rect = self.rect()
        palette = self.palette()
        painter.fillRect(rect, palette.base())
        painter.setPen(QtGui.QPen(palette.mid().color(), 1))
        painter.drawRect(rect.adjusted(0, 0, -1, -1))

        mid_y = rect.center().y()
        painter.setPen(QtGui.QPen(palette.mid().color(), 1, QtCore.Qt.DashLine))
        painter.drawLine(rect.left(), mid_y, rect.right(), mid_y)

        if len(self._samples) < 2:
            return

        latest_ts = self._samples[-1][0]
        time_span = max(1e-6, self._time_base)
        width = rect.width()
        height = rect.height()
        half_height = height / 2.0

        pen = QtGui.QPen(QtGui.QColor("#1f7a1f"), 2)
        painter.setPen(pen)

        points: List[QtCore.QPointF] = []
        for ts, value in self._samples:
            x_ratio = 1.0 - (latest_ts - ts) / time_span
            x = rect.left() + max(0.0, min(1.0, x_ratio)) * width
            y = mid_y - value * self._vertical_scale * half_height
            y = max(rect.top(), min(rect.bottom(), y))
            points.append(QtCore.QPointF(x, y))

        if len(points) < 2:
            return

        path = QtGui.QPainterPath(points[0])
        for point in points[1:]:
            path.lineTo(point)
        painter.drawPath(path)


class TrackPanel(QtWidgets.QWidget):
    """UI bundle describing a modulation track."""

    settingsChanged = QtCore.pyqtSignal()
    activationChanged = QtCore.pyqtSignal()
    assignmentChanged = QtCore.pyqtSignal()

    def __init__(self, index: int, registry, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.track_index = index
        self.registry = registry
        self._start_time: Optional[float] = None
        self._last_values: Dict[str, float] = {}
        self._pending_identifiers: List[str] = []
        self._push_active = False
        self._mic_status: tuple[bool, str] = (False, "Capture micro inactive")
        self._system_status: tuple[bool, str] = (False, "Capture lecture inactive")

        self._build_ui()
        self._connect_signals()
        self._refresh_selection()
        self._update_scope_mode()
        self._update_audio_label()

    # ------------------------------------------------------------------ setup
    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["Onglet", "Contrôle", "Paramètre", "Type"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        layout.addWidget(self.tree, 1)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(6)
        self.btn_remove = QtWidgets.QPushButton("Retirer la sélection")
        self.btn_clear = QtWidgets.QPushButton("Vider la piste")
        btn_row.addWidget(self.btn_remove)
        btn_row.addWidget(self.btn_clear)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

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
        self.cb_waveform.addItem("Microphone (entrée)", "mic")
        self.cb_waveform.addItem("Audio du système (lecture)", "system")
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

        layout.addWidget(waveform_box)

        scope_box = QtWidgets.QGroupBox("Oscilloscope")
        scope_layout = QtWidgets.QVBoxLayout(scope_box)
        scope_layout.setContentsMargins(12, 12, 12, 12)
        scope_layout.setSpacing(8)

        self.oscilloscope = OscilloscopeWidget()
        scope_layout.addWidget(self.oscilloscope)

        scope_controls = QtWidgets.QHBoxLayout()
        scope_controls.setContentsMargins(0, 0, 0, 0)
        scope_controls.setSpacing(6)
        self.sp_scope_time = QtWidgets.QDoubleSpinBox()
        self.sp_scope_time.setRange(0.1, 10.0)
        self.sp_scope_time.setSingleStep(0.1)
        self.sp_scope_time.setValue(2.0)
        scope_controls.addWidget(QtWidgets.QLabel("Fenêtre (s)"))
        scope_controls.addWidget(self.sp_scope_time)
        self.sp_scope_scale = QtWidgets.QDoubleSpinBox()
        self.sp_scope_scale.setRange(0.1, 4.0)
        self.sp_scope_scale.setSingleStep(0.1)
        self.sp_scope_scale.setValue(1.0)
        scope_controls.addWidget(QtWidgets.QLabel("Échelle"))
        scope_controls.addWidget(self.sp_scope_scale)
        scope_controls.addStretch(1)
        scope_layout.addLayout(scope_controls)

        layout.addWidget(scope_box)

        control_box = QtWidgets.QGroupBox("Contrôle de la piste")
        control_layout = QtWidgets.QVBoxLayout(control_box)
        control_layout.setContentsMargins(12, 12, 12, 12)
        control_layout.setSpacing(8)

        toggle_row = QtWidgets.QHBoxLayout()
        toggle_row.setContentsMargins(0, 0, 0, 0)
        toggle_row.setSpacing(6)
        self.btn_enable = QtWidgets.QPushButton("Activer la piste")
        self.btn_enable.setCheckable(True)
        toggle_row.addWidget(self.btn_enable)
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

        self.lbl_audio_status = QtWidgets.QLabel("Capture audio inactive")
        control_layout.addWidget(self.lbl_audio_status)

        layout.addWidget(control_box)

        self.scope_box = scope_box

    def _connect_signals(self) -> None:
        self.btn_remove.clicked.connect(self._remove_selected)
        self.btn_clear.clicked.connect(self._clear_selection)
        self.cb_waveform.currentIndexChanged.connect(self._on_waveform_changed)
        self.sp_amplitude.valueChanged.connect(self._on_settings_changed)
        self.sp_frequency.valueChanged.connect(self._on_frequency_changed)
        self.sp_phase.valueChanged.connect(self._on_settings_changed)
        self.sp_offset.valueChanged.connect(self._on_settings_changed)
        self.sp_smoothing.valueChanged.connect(self._on_settings_changed)
        self.sp_audio_gain.valueChanged.connect(self._on_settings_changed)
        self.sp_scope_time.valueChanged.connect(self._on_scope_time_changed)
        self.sp_scope_scale.valueChanged.connect(self._on_scope_scale_changed)
        self.btn_enable.toggled.connect(self._on_toggle)
        self.chk_push_to_talk.stateChanged.connect(self._sync_push_to_talk_state)
        self.btn_push.toggled.connect(self._on_push_toggle)

    # ---------------------------------------------------------------- selection
    def _remove_selected(self) -> None:
        items = self.tree.selectedItems()
        for item in items:
            ident = item.data(0, QtCore.Qt.UserRole)
            if not ident:
                continue
            self.registry.deselect_identifier(ident, track=self.track_index)

    def _clear_selection(self) -> None:
        self.registry.clear_selection(track=self.track_index)

    def _refresh_selection(self) -> None:
        controls = self.registry.selected_controls(track=self.track_index)
        self.tree.setUpdatesEnabled(False)
        self.tree.clear()
        for control in controls:
            item = QtWidgets.QTreeWidgetItem(
                [control.tab, control.label, control.identifier, control.control_type]
            )
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
        self.assignmentChanged.emit()

    def apply_pending_selection(self) -> None:
        if not self._pending_identifiers:
            return
        for ident in self._pending_identifiers:
            if self.registry.control_by_identifier(ident) is None:
                return
        self.registry.set_selection(self._pending_identifiers, track=self.track_index)
        self._pending_identifiers = []
        self._refresh_selection()

    # ---------------------------------------------------------------- waveform
    def _on_waveform_changed(self) -> None:
        self._update_scope_mode()
        self._update_audio_label()
        self._on_settings_changed()

    def _on_settings_changed(self) -> None:
        self.settingsChanged.emit()

    def _on_frequency_changed(self) -> None:
        self._start_time = None
        self._on_settings_changed()

    def _on_scope_time_changed(self, value: float) -> None:
        self.oscilloscope.set_time_base(value)
        self._on_settings_changed()

    def _on_scope_scale_changed(self, value: float) -> None:
        self.oscilloscope.set_vertical_scale(value)
        self._on_settings_changed()

    def _update_scope_mode(self) -> None:
        waveform = self.cb_waveform.currentData()
        is_audio = waveform in {"mic", "system"}
        self.scope_box.setEnabled(not is_audio)
        self.sp_frequency.setEnabled(not is_audio)
        self.sp_phase.setEnabled(not is_audio)
        if is_audio:
            self.oscilloscope.reset()

    # --------------------------------------------------------------- push-to-talk
    def _sync_push_to_talk_state(self) -> None:
        enabled = self.chk_push_to_talk.isChecked()
        self.btn_push.setEnabled(enabled)
        if not enabled:
            self.btn_push.setChecked(False)
            self._push_active = False
            self.lbl_push_state.setText("Push-to-talk inactif")
        self._on_settings_changed()

    def _on_push_toggle(self, active: bool) -> None:
        self._push_active = bool(active)
        self.lbl_push_state.setText("Push-to-talk actif" if active else "Push-to-talk inactif")
        self.settingsChanged.emit()

    # ---------------------------------------------------------------- activation
    def _on_toggle(self, enabled: bool) -> None:
        if enabled:
            self._start_time = None
        else:
            self._push_active = False
            self.btn_push.setChecked(False)
            self.lbl_push_state.setText("Push-to-talk inactif")
        self.activationChanged.emit()
        self.settingsChanged.emit()

    def requires_timer(self) -> bool:
        if not self.btn_enable.isChecked():
            return False
        return bool(self.registry.selected_controls(track=self.track_index))

    # ------------------------------------------------------------------- audio ui
    def update_audio_status(self, source: str, available: bool, status: str) -> None:
        if source == "mic":
            self._mic_status = (available, status)
        elif source == "system":
            self._system_status = (available, status)
        self._update_audio_label()

    def _update_audio_label(self) -> None:
        waveform = self.cb_waveform.currentData()
        if waveform == "mic":
            available, status = self._mic_status
        elif waveform == "system":
            available, status = self._system_status
        else:
            available, status = (True, "Oscillateur interne")
        self.lbl_audio_status.setText(status)
        color = "#1f7a1f" if available else "#aa3333"
        self.lbl_audio_status.setStyleSheet(f"color:{color};")

    # ------------------------------------------------------------------- runtime
    def tick(self, timestamp: float, mic_level: float, system_level: float) -> None:
        if not self.btn_enable.isChecked():
            return
        controls = self.registry.selected_controls(track=self.track_index)
        if not controls:
            self.btn_enable.setChecked(False)
            return
        if self.chk_push_to_talk.isChecked() and not self._push_active:
            return
        if self._start_time is None:
            self._start_time = timestamp
        elapsed = timestamp - self._start_time
        waveform = self.cb_waveform.currentData()
        target = self._waveform_value(waveform, elapsed, mic_level, system_level)
        amplitude = max(0.0, min(1.0, self.sp_amplitude.value()))
        offset = max(-1.0, min(1.0, self.sp_offset.value()))
        smoothing = max(0.0, min(1.0, self.sp_smoothing.value()))

        display_value = max(-1.0, min(1.0, offset + amplitude * target))
        if waveform not in {"mic", "system"}:
            self.oscilloscope.add_sample(display_value, timestamp)

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

    def _waveform_value(self, waveform: str, elapsed: float, mic_level: float, system_level: float) -> float:
        gain = max(0.1, float(self.sp_audio_gain.value()))
        phase = math.radians(self.sp_phase.value())
        freq = max(0.0, self.sp_frequency.value())
        if waveform == "mic":
            return max(-1.0, min(1.0, mic_level * gain * 2.0 - 1.0))
        if waveform == "system":
            return max(-1.0, min(1.0, system_level * gain * 2.0 - 1.0))
        if freq <= 0 and waveform != "sine":
            return 0.0
        if waveform == "triangle":
            if freq <= 0:
                return 0.0
            period = 1.0 / freq
            local = ((elapsed + phase / (2 * math.pi * freq)) % period) / period
            return 4 * abs(local - 0.5) - 1.0
        if waveform == "square":
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
        return math.sin(2 * math.pi * max(freq, 0.0) * elapsed + phase)

    # ------------------------------------------------------------------- state io
    def collect_config(self) -> dict:
        return dict(
            enabled=self.btn_enable.isChecked(),
            waveform=self.cb_waveform.currentData(),
            amplitude=self.sp_amplitude.value(),
            frequency=self.sp_frequency.value(),
            phaseDeg=self.sp_phase.value(),
            offset=self.sp_offset.value(),
            smoothing=self.sp_smoothing.value(),
            pushToTalk=self.chk_push_to_talk.isChecked(),
            selected=self.registry.selected_identifiers(track=self.track_index),
            audioGain=self.sp_audio_gain.value(),
            scope=dict(timeBase=self.sp_scope_time.value(), scale=self.sp_scope_scale.value()),
        )

    def apply_config(self, cfg: Optional[dict]) -> None:
        cfg = cfg or {}
        with QtCore.QSignalBlocker(self.cb_waveform):
            index = self.cb_waveform.findData(cfg.get("waveform", "sine"))
            if index != -1:
                self.cb_waveform.setCurrentIndex(index)
            else:
                self.cb_waveform.setCurrentIndex(0)
        for spin, key in [
            (self.sp_amplitude, "amplitude"),
            (self.sp_frequency, "frequency"),
            (self.sp_phase, "phaseDeg"),
            (self.sp_offset, "offset"),
            (self.sp_smoothing, "smoothing"),
            (self.sp_audio_gain, "audioGain"),
        ]:
            with QtCore.QSignalBlocker(spin):
                if key in cfg:
                    spin.setValue(float(cfg.get(key, spin.value())))
        scope = cfg.get("scope", {})
        with QtCore.QSignalBlocker(self.sp_scope_time):
            if "timeBase" in scope:
                self.sp_scope_time.setValue(float(scope.get("timeBase", 2.0)))
        with QtCore.QSignalBlocker(self.sp_scope_scale):
            if "scale" in scope:
                self.sp_scope_scale.setValue(float(scope.get("scale", 1.0)))
        with QtCore.QSignalBlocker(self.chk_push_to_talk):
            self.chk_push_to_talk.setChecked(bool(cfg.get("pushToTalk", False)))
        with QtCore.QSignalBlocker(self.btn_enable):
            self.btn_enable.setChecked(bool(cfg.get("enabled", False)))
        selected = cfg.get("selected", [])
        if isinstance(selected, (list, tuple)):
            self._pending_identifiers = [str(ident) for ident in selected]
        else:
            self._pending_identifiers = []
        self.apply_pending_selection()
        self._update_scope_mode()
        self._update_audio_label()
        self.settingsChanged.emit()
        self.activationChanged.emit()


class LinkControllerTab(QtWidgets.QWidget):
    """Tab providing waveform-driven control over registered widgets."""

    changed = QtCore.pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.registry = LINK_REGISTRY
        self._applying = False
        self._mic_level = 0.0
        self._system_level = 0.0

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)

        instructions = QtWidgets.QLabel(
            "Clic droit sur un slider, un dial ou une boîte numérique pour les lier à une piste."
        )
        instructions.setWordWrap(True)
        instructions.setObjectName("LinkControllerInstructions")
        outer.addWidget(instructions)

        self.track_tabs = QtWidgets.QTabWidget()
        outer.addWidget(self.track_tabs, 1)

        self.tracks: List[TrackPanel] = []
        for index in range(TRACK_COUNT):
            track = TrackPanel(index, self.registry)
            self.tracks.append(track)
            self.track_tabs.addTab(track, f"Piste {index + 1}")
            track.settingsChanged.connect(self._on_track_settings_changed)
            track.activationChanged.connect(self._update_timer_state)
            track.assignmentChanged.connect(self._on_track_assignment_changed)

        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(30)
        self.timer.timeout.connect(self._on_tick)

        self.mic_monitor = MicrophoneLevelMonitor(self)
        self.playback_monitor = PlaybackLevelMonitor(self)

        self.mic_monitor.levelChanged.connect(self._on_mic_level)
        self.playback_monitor.levelChanged.connect(self._on_system_level)
        self.mic_monitor.availabilityChanged.connect(
            lambda available, status: self._update_audio_status("mic", available, status)
        )
        self.playback_monitor.availabilityChanged.connect(
            lambda available, status: self._update_audio_status("system", available, status)
        )
        self._update_audio_status("mic", self.mic_monitor.available, self.mic_monitor.status)
        self._update_audio_status(
            "system", self.playback_monitor.available, self.playback_monitor.status
        )

        self.registry.selectionChanged.connect(self._on_registry_selection_changed)
        self.registry.registryChanged.connect(self._on_registry_registry_changed)

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
    def _on_mic_level(self, level: float) -> None:
        self._mic_level = max(0.0, min(1.0, float(level)))

    def _on_system_level(self, level: float) -> None:
        self._system_level = max(0.0, min(1.0, float(level)))

    def _update_audio_status(self, source: str, available: bool, status: str) -> None:
        for track in self.tracks:
            track.update_audio_status(source, available, status)

    def _on_track_settings_changed(self) -> None:
        if not self._applying:
            self.emit_delta()

    def _on_track_assignment_changed(self) -> None:
        if not self._applying:
            self.emit_delta()
        self._update_timer_state()

    def _on_registry_selection_changed(self) -> None:
        for track in self.tracks:
            track._refresh_selection()
        if not self._applying:
            self.emit_delta()
        self._update_timer_state()

    def _on_registry_registry_changed(self) -> None:
        for track in self.tracks:
            track.apply_pending_selection()

    # ----------------------------------------------------------------- runtime
    def _on_tick(self) -> None:
        timestamp = time.monotonic()
        for track in self.tracks:
            track.tick(timestamp, self._mic_level, self._system_level)

    def _update_timer_state(self) -> None:
        if any(track.requires_timer() for track in self.tracks):
            if not self.timer.isActive():
                self.timer.start()
        else:
            self.timer.stop()

    # ------------------------------------------------------------------- state io
    def collect(self) -> dict:
        return dict(tracks=[track.collect_config() for track in self.tracks])

    def set_defaults(self, cfg: Optional[dict]):
        cfg = cfg or {}
        tracks_cfg = cfg.get("tracks")
        if not isinstance(tracks_cfg, (list, tuple)):
            legacy = dict(cfg)
            tracks_cfg = [legacy]
        self._applying = True
        try:
            for index, track in enumerate(self.tracks):
                track_cfg = tracks_cfg[index] if index < len(tracks_cfg) else None
                track.apply_config(track_cfg)
        finally:
            self._applying = False
        self._update_timer_state()
        self.emit_delta()

    def attach_subprofile_manager(self, _manager):  # pragma: no cover - compatibility
        return

    def emit_delta(self) -> None:
        if self._applying:
            return
        self.changed.emit({"controller": self.collect()})

