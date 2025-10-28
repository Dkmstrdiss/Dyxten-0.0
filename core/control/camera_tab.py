from PyQt5 import QtWidgets, QtCore
from .widgets import row
from .config import DEFAULTS

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

        row(fl, "camRadius", self.sp_camRadius, "Distance caméra")
        row(fl, "camHeightDeg", self.sl_camHeight, "Hauteur orbite (°)")
        row(fl, "camTiltDeg", self.sl_camTilt, "Inclinaison (°)")
        row(fl, "omegaDegPerSec", self.sl_omega, "Vitesse d’orbite (°/s)")
        row(fl, "fov", self.sp_fov, "Champ de vision")

        for w in [self.sp_camRadius,self.sl_camHeight,self.sl_camTilt,self.sl_omega,self.sp_fov]:
            w.valueChanged.connect(self.emit_delta)

    def emit_delta(self, *a):
        self.changed.emit({"camera": self.collect()})

    def collect(self):
        return dict(
            camRadius=self.sp_camRadius.value(),
            camHeightDeg=self.sl_camHeight.value(),
            camTiltDeg=self.sl_camTilt.value(),
            omegaDegPerSec=self.sl_omega.value(),
            fov=self.sp_fov.value()
        )

    def set_defaults(self, cfg):
        cfg = cfg or {}
        d = DEFAULTS["camera"]
        mappings = [
            (self.sp_camRadius, float, cfg.get("camRadius", d["camRadius"])),
            (self.sl_camHeight, int, cfg.get("camHeightDeg", d["camHeightDeg"])),
            (self.sl_camTilt, int, cfg.get("camTiltDeg", d["camTiltDeg"])),
            (self.sl_omega, int, cfg.get("omegaDegPerSec", d["omegaDegPerSec"])),
            (self.sp_fov, int, cfg.get("fov", d["fov"])),
        ]
        for widget, cast, value in mappings:
            with QtCore.QSignalBlocker(widget):
                widget.setValue(cast(value))
