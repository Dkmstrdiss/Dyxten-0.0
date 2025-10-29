from PyQt5 import QtWidgets, QtCore
from .widgets import row
from .config import DEFAULTS


POPULAR_AXES_ANGLES = [-90, -60, -45, -30, -15, 0, 15, 30, 45, 60, 90]
POPULAR_SPIN_ANGLES = [0, 15, 30, 45, 60, 90, 120, 150, 180]

class CameraTab(QtWidgets.QWidget):
    changed = QtCore.pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        d = DEFAULTS["camera"]
        fl = QtWidgets.QFormLayout(self)

        self._snap_targets = {}

        self.sp_camRadius = QtWidgets.QDoubleSpinBox(); self.sp_camRadius.setRange(0.1, 20.0); self.sp_camRadius.setSingleStep(0.1); self.sp_camRadius.setValue(d["camRadius"])
        self.sl_camHeight = QtWidgets.QSlider(QtCore.Qt.Horizontal); self.sl_camHeight.setRange(-90,90); self.sl_camHeight.setValue(d["camHeightDeg"])
        self.sl_camTilt   = QtWidgets.QSlider(QtCore.Qt.Horizontal); self.sl_camTilt.setRange(-90,90); self.sl_camTilt.setValue(d["camTiltDeg"])
        self.sl_omega     = QtWidgets.QSlider(QtCore.Qt.Horizontal); self.sl_omega.setRange(0,180); self.sl_omega.setValue(d["omegaDegPerSec"])
        self.sp_fov       = QtWidgets.QSpinBox(); self.sp_fov.setRange(50,2000); self.sp_fov.setValue(d["fov"])

        self._install_angle_snap(self.sl_camHeight, POPULAR_AXES_ANGLES)
        self._install_angle_snap(self.sl_camTilt, POPULAR_AXES_ANGLES)
        self._install_angle_snap(self.sl_omega, POPULAR_SPIN_ANGLES)

        row(fl, "Distance à la scène", self.sp_camRadius, "Éloigne ou rapproche la caméra du centre de la scène.")
        row(fl, "Hauteur de vue (°)", self.sl_camHeight, "Monte ou descend la caméra sur son orbite.")
        row(fl, "Inclinaison (°)", self.sl_camTilt, "Incline la caméra vers le haut ou vers le bas.")
        row(fl, "Rotation automatique (°/s)", self.sl_omega, "Fait tourner la caméra autour de la scène à vitesse constante.")
        row(fl, "Zoom (champ de vision)", self.sp_fov, "Ajuste l’angle de vue : petit = zoom avant, grand = grand-angle.")

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

    def set_tilt_to_max(self):
        target = self.sl_camTilt.maximum()
        if self.sl_camTilt.value() == target:
            return
        with QtCore.QSignalBlocker(self.sl_camTilt):
            self.sl_camTilt.setValue(target)
        self.emit_delta()

    # Ancienne méthode conservée pour compatibilité : elle ne fait plus rien
    # mais reste présente afin d'éviter les erreurs si du code externe tente
    # encore de l'appeler après les régressions signalées.
    def _install_angle_snap(self, *_args, **_kwargs):  # pragma: no cover - compat
        """Méthode laissée volontairement vide (aucun snap sur les sliders)."""
        return
