
from PyQt5 import QtWidgets, QtCore
from .widgets import row
from .config import DEFAULTS, TOOLTIPS

class CameraTab(QtWidgets.QWidget):
    changed = QtCore.pyqtSignal(dict)
    def __init__(self):
        super().__init__()
        d = DEFAULTS["camera"]
        fl = QtWidgets.QFormLayout(self)
        self.sp_camRadius = QtWidgets.QDoubleSpinBox(); self.sp_camRadius.setRange(0.1, 20.0); self.sp_camRadius.setSingleStep(0.1); self.sp_camRadius.setValue(d["camRadius"])
        self.sl_camHeight = QtWidgets.QSlider(QtCore.Qt.Horizontal); self.sl_camHeight.setRange(-90,90); self.sl_camHeight.setValue(d["camHeightDeg"])
        self.sl_camTilt   = QtWidgets.QSlider(QtCore.Qt.Horizontal); self.sl_camTilt.setRange(-90,90); self.sl_camTilt.setValue(d["camTiltDeg"])
        self.sl_omega     = QtWidgets.QSlider(QtCore.Qt.Horizontal); self.sl_omega.setRange(0,180); self.sl_omega.setValue(d["omegaDegPerSec"])
        self.sp_fov       = QtWidgets.QSpinBox(); self.sp_fov.setRange(50,2000); self.sp_fov.setValue(d["fov"])
        row(fl, "camRadius", self.sp_camRadius, TOOLTIPS["camera.camRadius"], lambda: self.sp_camRadius.setValue(d["camRadius"]))
        row(fl, "camHeightDeg", self.sl_camHeight, TOOLTIPS["camera.camHeightDeg"], lambda: self.sl_camHeight.setValue(d["camHeightDeg"]))
        row(fl, "camTiltDeg", self.sl_camTilt, TOOLTIPS["camera.camTiltDeg"], lambda: self.sl_camTilt.setValue(d["camTiltDeg"]))
        row(fl, "omegaDegPerSec", self.sl_omega, TOOLTIPS["camera.omegaDegPerSec"], lambda: self.sl_omega.setValue(d["omegaDegPerSec"]))
        row(fl, "fov", self.sp_fov, TOOLTIPS["camera.fov"], lambda: self.sp_fov.setValue(d["fov"]))
        for w in [self.sp_camRadius,self.sl_camHeight,self.sl_camTilt,self.sl_omega,self.sp_fov]:
            if isinstance(w, QtWidgets.QSlider): w.valueChanged.connect(self.emit_delta)
            else: w.valueChanged.connect(self.emit_delta)
    def emit_delta(self, *a): self.changed.emit({"camera": self.collect()})
    def collect(self):
        return dict(camRadius=self.sp_camRadius.value(), camHeightDeg=self.sl_camHeight.value(), camTiltDeg=self.sl_camTilt.value(),
                    omegaDegPerSec=self.sl_omega.value(), fov=self.sp_fov.value())
    def set_defaults(self, cfg): pass
    def set_enabled(self, context: dict): pass
