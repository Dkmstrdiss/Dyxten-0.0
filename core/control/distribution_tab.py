
from PyQt5 import QtWidgets, QtCore
from .widgets import row
from .config import DEFAULTS, TOOLTIPS

class DistributionTab(QtWidgets.QWidget):
    changed = QtCore.pyqtSignal(dict)
    def __init__(self):
        super().__init__()
        d = DEFAULTS["distribution"]
        fl = QtWidgets.QFormLayout(self)
        self.cb_pr = QtWidgets.QComboBox(); self.cb_pr.addItems(["uniform_area","power_edge","gaussian_center","by_lat","by_lon"]); self.cb_pr.setCurrentText(d["pr"])
        self.sp_dmin_px = QtWidgets.QDoubleSpinBox(); self.sp_dmin_px.setRange(0.0,200.0); self.sp_dmin_px.setSingleStep(1.0); self.sp_dmin_px.setValue(d["dmin_px"])
        row(fl, "p(select)", self.cb_pr, TOOLTIPS["distribution.pr"], lambda: self.cb_pr.setCurrentText(d["pr"]))
        row(fl, "d_min (px)", self.sp_dmin_px, TOOLTIPS["distribution.dmin_px"], lambda: self.sp_dmin_px.setValue(d["dmin_px"]))
        self.cb_pr.currentIndexChanged.connect(self.emit_delta)
        self.sp_dmin_px.valueChanged.connect(self.emit_delta)
    def collect(self): return dict(pr=self.cb_pr.currentText(), dmin_px=self.sp_dmin_px.value())
    def set_defaults(self, cfg):
        cfg = cfg or {}
        d = DEFAULTS["distribution"]
        with QtCore.QSignalBlocker(self.cb_pr):
            self.cb_pr.setCurrentText(str(cfg.get("pr", d["pr"])))
        with QtCore.QSignalBlocker(self.sp_dmin_px):
            self.sp_dmin_px.setValue(float(cfg.get("dmin_px", d["dmin_px"])))
    def set_enabled(self, context: dict): pass
    def emit_delta(self, *a): self.changed.emit({"distribution": self.collect()})
