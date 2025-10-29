
from PyQt5 import QtWidgets, QtCore
from .widgets import row
from .config import DEFAULTS, TOOLTIPS

class DynamicsTab(QtWidgets.QWidget):
    changed = QtCore.pyqtSignal(dict)
    def __init__(self):
        super().__init__()
        d = DEFAULTS["dynamics"]
        fl = QtWidgets.QFormLayout(self)
        self.rows = {}

        self.sp_rotX = QtWidgets.QDoubleSpinBox(); self.sp_rotX.setRange(-360,360); self.sp_rotX.setValue(d["rotX"])
        self.sp_rotY = QtWidgets.QDoubleSpinBox(); self.sp_rotY.setRange(-360,360); self.sp_rotY.setValue(d["rotY"])
        self.sp_rotZ = QtWidgets.QDoubleSpinBox(); self.sp_rotZ.setRange(-360,360); self.sp_rotZ.setValue(d["rotZ"])
        self.sp_pulseA = QtWidgets.QDoubleSpinBox(); self.sp_pulseA.setRange(0.0,1.0); self.sp_pulseA.setSingleStep(0.01); self.sp_pulseA.setValue(d["pulseA"])
        self.sp_pulseW = QtWidgets.QDoubleSpinBox(); self.sp_pulseW.setRange(0.0,20.0); self.sp_pulseW.setValue(d["pulseW"])
        self.sp_pulsePhase = QtWidgets.QDoubleSpinBox(); self.sp_pulsePhase.setRange(0.0,360.0); self.sp_pulsePhase.setValue(d["pulsePhaseDeg"])
        self.cb_rotPhaseMode = QtWidgets.QComboBox(); self.cb_rotPhaseMode.addItems(["none","by_index","by_radius"]); self.cb_rotPhaseMode.setCurrentText(d["rotPhaseMode"])
        self.sp_rotPhaseDeg = QtWidgets.QDoubleSpinBox(); self.sp_rotPhaseDeg.setRange(0.0,360.0); self.sp_rotPhaseDeg.setValue(d["rotPhaseDeg"])
        self.rows["rotX"] = row(fl, "Rotation X (°/s)", self.sp_rotX, TOOLTIPS["dynamics.rotX"], lambda: self.sp_rotX.setValue(d["rotX"]))
        self.rows["rotY"] = row(fl, "Rotation Y (°/s)", self.sp_rotY, TOOLTIPS["dynamics.rotY"], lambda: self.sp_rotY.setValue(d["rotY"]))
        self.rows["rotZ"] = row(fl, "Rotation Z (°/s)", self.sp_rotZ, TOOLTIPS["dynamics.rotZ"], lambda: self.sp_rotZ.setValue(d["rotZ"]))
        row(fl, "Respiration (amplitude)", self.sp_pulseA, TOOLTIPS["dynamics.pulseA"], lambda: self.sp_pulseA.setValue(d["pulseA"]))
        row(fl, "Respiration (vitesse)", self.sp_pulseW, TOOLTIPS["dynamics.pulseW"], lambda: self.sp_pulseW.setValue(d["pulseW"]))
        row(fl, "Décalage respiration (°)", self.sp_pulsePhase, TOOLTIPS["dynamics.pulsePhaseDeg"], lambda: self.sp_pulsePhase.setValue(d["pulsePhaseDeg"]))
        self.rows["rotPhaseMode"] = row(fl, "Décalage rotations", self.cb_rotPhaseMode, TOOLTIPS["dynamics.rotPhaseMode"], lambda: self.cb_rotPhaseMode.setCurrentText(d["rotPhaseMode"]))
        self.rows["rotPhaseDeg"] = row(fl, "Amplitude du décalage (°)", self.sp_rotPhaseDeg, TOOLTIPS["dynamics.rotPhaseDeg"], lambda: self.sp_rotPhaseDeg.setValue(d["rotPhaseDeg"]))
        for w in [self.sp_rotX,self.sp_rotY,self.sp_rotZ,self.sp_pulseA,self.sp_pulseW,self.sp_pulsePhase,self.cb_rotPhaseMode,self.sp_rotPhaseDeg]:
            if isinstance(w, QtWidgets.QComboBox):
                w.currentIndexChanged.connect(self.emit_delta)
            else:
                w.valueChanged.connect(self.emit_delta)

        self.cb_rotPhaseMode.currentIndexChanged.connect(self._update_row_states)
        self._update_row_states()
    def collect(self):
        return dict(rotX=self.sp_rotX.value(), rotY=self.sp_rotY.value(), rotZ=self.sp_rotZ.value(),
                    pulseA=self.sp_pulseA.value(), pulseW=self.sp_pulseW.value(),
                    pulsePhaseDeg=self.sp_pulsePhase.value(),
                    rotPhaseMode=self.cb_rotPhaseMode.currentText(), rotPhaseDeg=self.sp_rotPhaseDeg.value())
    def set_defaults(self, cfg):
        cfg = cfg or {}
        d = DEFAULTS["dynamics"]
        def val(key):
            return cfg.get(key, d[key])

        with QtCore.QSignalBlocker(self.sp_rotX):
            self.sp_rotX.setValue(float(val("rotX")))
        with QtCore.QSignalBlocker(self.sp_rotY):
            self.sp_rotY.setValue(float(val("rotY")))
        with QtCore.QSignalBlocker(self.sp_rotZ):
            self.sp_rotZ.setValue(float(val("rotZ")))
        with QtCore.QSignalBlocker(self.sp_pulseA):
            self.sp_pulseA.setValue(float(val("pulseA")))
        with QtCore.QSignalBlocker(self.sp_pulseW):
            self.sp_pulseW.setValue(float(val("pulseW")))
        with QtCore.QSignalBlocker(self.sp_pulsePhase):
            self.sp_pulsePhase.setValue(float(val("pulsePhaseDeg")))
        with QtCore.QSignalBlocker(self.cb_rotPhaseMode):
            self.cb_rotPhaseMode.setCurrentText(str(val("rotPhaseMode")))
        with QtCore.QSignalBlocker(self.sp_rotPhaseDeg):
            self.sp_rotPhaseDeg.setValue(float(val("rotPhaseDeg")))
    def set_enabled(self, context: dict): pass

    def emit_delta(self, *a):
        self._update_row_states()
        self.changed.emit({"dynamics": self.collect()})

    # ------------------------------------------------------------------ utils
    def _set_row_visible(self, key: str, visible: bool):
        row_widget = self.rows.get(key)
        if row_widget is None:
            return
        row_widget.setVisible(visible)
        label = getattr(row_widget, "_form_label", None)
        if label is not None:
            label.setVisible(visible)

    def _update_row_states(self, *args):
        mode = self.cb_rotPhaseMode.currentText()
        show_phase = mode != "none"
        self._set_row_visible("rotPhaseDeg", show_phase)
        self.sp_rotPhaseDeg.setEnabled(show_phase)
