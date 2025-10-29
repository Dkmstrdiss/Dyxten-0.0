
from PyQt5 import QtWidgets, QtCore
from .widgets import row, SubProfilePanel
from .config import DEFAULTS, TOOLTIPS

class MaskTab(QtWidgets.QWidget):
    changed = QtCore.pyqtSignal(dict)
    def __init__(self):
        super().__init__()
        d = DEFAULTS["mask"]
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        self._subprofile_panel = SubProfilePanel("Sous-profil masque")
        outer.addWidget(self._subprofile_panel)

        container = QtWidgets.QWidget()
        fl = QtWidgets.QFormLayout(container)
        fl.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(container)
        self.chk_enabled = QtWidgets.QCheckBox(); self.chk_enabled.setChecked(d["enabled"])
        self.cb_mode = QtWidgets.QComboBox(); self.cb_mode.addItems(["none","north_cap","south_cap","equatorial_band","longitudinal_band"]); self.cb_mode.setCurrentText(d["mode"])
        self.sp_angle = QtWidgets.QDoubleSpinBox(); self.sp_angle.setRange(0.0,90.0); self.sp_angle.setSingleStep(1.0); self.sp_angle.setValue(d["angleDeg"])
        self.sp_band = QtWidgets.QDoubleSpinBox(); self.sp_band.setRange(0.0,90.0); self.sp_band.setSingleStep(1.0); self.sp_band.setValue(d["bandHalfDeg"])
        self.sp_lonC = QtWidgets.QDoubleSpinBox(); self.sp_lonC.setRange(-180.0,180.0); self.sp_lonC.setSingleStep(1.0); self.sp_lonC.setValue(d["lonCenterDeg"])
        self.sp_lonW = QtWidgets.QDoubleSpinBox(); self.sp_lonW.setRange(0.0,180.0); self.sp_lonW.setSingleStep(1.0); self.sp_lonW.setValue(d["lonWidthDeg"])
        self.sp_soft = QtWidgets.QDoubleSpinBox(); self.sp_soft.setRange(0.0,45.0); self.sp_soft.setSingleStep(1.0); self.sp_soft.setValue(d["softDeg"])
        self.chk_invert = QtWidgets.QCheckBox(); self.chk_invert.setChecked(d["invert"])
        row(fl, "Activer le masque", self.chk_enabled, TOOLTIPS["mask.enabled"], lambda: self.chk_enabled.setChecked(d["enabled"]))
        row(fl, "Type de masque", self.cb_mode, TOOLTIPS["mask.mode"], lambda: self.cb_mode.setCurrentText(d["mode"]))
        row(fl, "Angle de coupe (°)", self.sp_angle, TOOLTIPS["mask.angleDeg"], lambda: self.sp_angle.setValue(d["angleDeg"]))
        row(fl, "Largeur demi-bande (°)", self.sp_band, TOOLTIPS["mask.bandHalfDeg"], lambda: self.sp_band.setValue(d["bandHalfDeg"]))
        row(fl, "Longitude centrée (°)", self.sp_lonC, TOOLTIPS["mask.lonCenterDeg"], lambda: self.sp_lonC.setValue(d["lonCenterDeg"]))
        row(fl, "Largeur en longitude (°)", self.sp_lonW, TOOLTIPS["mask.lonWidthDeg"], lambda: self.sp_lonW.setValue(d["lonWidthDeg"]))
        row(fl, "Bord doux (°)", self.sp_soft, TOOLTIPS["mask.softDeg"], lambda: self.sp_soft.setValue(d["softDeg"]))
        row(fl, "Inverser la sélection", self.chk_invert, TOOLTIPS["mask.invert"], lambda: self.chk_invert.setChecked(d["invert"]))
        for w in [self.chk_enabled,self.cb_mode,self.sp_angle,self.sp_band,self.sp_lonC,self.sp_lonW,self.sp_soft,self.chk_invert]:
            if isinstance(w, QtWidgets.QCheckBox): w.stateChanged.connect(self.emit_delta)
            elif isinstance(w, QtWidgets.QComboBox): w.currentIndexChanged.connect(self.emit_delta)
            else: w.valueChanged.connect(self.emit_delta)
        self._sync_subprofile_state()
    def collect(self):
        return dict(enabled=self.chk_enabled.isChecked(), mode=self.cb_mode.currentText(), angleDeg=self.sp_angle.value(),
                    bandHalfDeg=self.sp_band.value(), lonCenterDeg=self.sp_lonC.value(), lonWidthDeg=self.sp_lonW.value(),
                    softDeg=self.sp_soft.value(), invert=self.chk_invert.isChecked())
    def set_defaults(self, cfg):
        cfg = cfg or {}
        d = DEFAULTS["mask"]
        with QtCore.QSignalBlocker(self.chk_enabled):
            self.chk_enabled.setChecked(bool(cfg.get("enabled", d["enabled"])))
        with QtCore.QSignalBlocker(self.cb_mode):
            self.cb_mode.setCurrentText(str(cfg.get("mode", d["mode"])))
        with QtCore.QSignalBlocker(self.sp_angle):
            self.sp_angle.setValue(float(cfg.get("angleDeg", d["angleDeg"])))
        with QtCore.QSignalBlocker(self.sp_band):
            self.sp_band.setValue(float(cfg.get("bandHalfDeg", d["bandHalfDeg"])))
        with QtCore.QSignalBlocker(self.sp_lonC):
            self.sp_lonC.setValue(float(cfg.get("lonCenterDeg", d["lonCenterDeg"])))
        with QtCore.QSignalBlocker(self.sp_lonW):
            self.sp_lonW.setValue(float(cfg.get("lonWidthDeg", d["lonWidthDeg"])))
        with QtCore.QSignalBlocker(self.sp_soft):
            self.sp_soft.setValue(float(cfg.get("softDeg", d["softDeg"])))
        with QtCore.QSignalBlocker(self.chk_invert):
            self.chk_invert.setChecked(bool(cfg.get("invert", d["invert"])))
        self._sync_subprofile_state()
    def set_enabled(self, context: dict): pass
    def emit_delta(self, *a):
        self._sync_subprofile_state()
        self.changed.emit({"mask": self.collect()})
    def attach_subprofile_manager(self, manager):
        self._subprofile_panel.bind(
            manager=manager,
            section="mask",
            defaults=DEFAULTS["mask"],
            collect_cb=self.collect,
            apply_cb=self.set_defaults,
            on_change=self.emit_delta,
        )
        self._sync_subprofile_state()
    def _sync_subprofile_state(self):
        if hasattr(self, "_subprofile_panel") and self._subprofile_panel is not None:
            self._subprofile_panel.sync_from_data(self.collect())
