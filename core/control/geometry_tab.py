
from PyQt5 import QtWidgets, QtCore
from .widgets import row, vec_row
from .config import DEFAULTS, TOOLTIPS

class GeometryTab(QtWidgets.QWidget):
    changed = QtCore.pyqtSignal(dict)
    topologyChanged = QtCore.pyqtSignal(str)
    def __init__(self):
        super().__init__()
        d = DEFAULTS["geometry"]
        fl = QtWidgets.QFormLayout(self)
        self.cb_topology = QtWidgets.QComboBox(); self.cb_topology.addItems(["uv_sphere","fibo_sphere","disk_phyllotaxis","torus","superquadric","geodesic","mobius"])
        self.cb_topology.setCurrentText(d["topology"])
        self.sp_R   = QtWidgets.QDoubleSpinBox(); self.sp_R.setRange(0.1, 5.0); self.sp_R.setSingleStep(0.1); self.sp_R.setValue(d["R"])
        self.sp_lat = QtWidgets.QSpinBox(); self.sp_lat.setRange(4,512); self.sp_lat.setValue(d["lat"])
        self.sp_lon = QtWidgets.QSpinBox(); self.sp_lon.setRange(4,512); self.sp_lon.setValue(d["lon"])
        self.sp_N   = QtWidgets.QSpinBox(); self.sp_N.setRange(10,200000); self.sp_N.setValue(d["N"])
        self.sp_phi = QtWidgets.QDoubleSpinBox(); self.sp_phi.setRange(0.0,6.28318); self.sp_phi.setDecimals(5); self.sp_phi.setValue(d["phi_g"])
        self.sp_Rmaj = QtWidgets.QDoubleSpinBox(); self.sp_Rmaj.setRange(0.1,10.0); self.sp_Rmaj.setSingleStep(0.05); self.sp_Rmaj.setValue(d["R_major"])
        self.sp_rmin = QtWidgets.QDoubleSpinBox(); self.sp_rmin.setRange(0.05,5.0); self.sp_rmin.setSingleStep(0.05); self.sp_rmin.setValue(d["r_minor"])
        self.sp_eps1 = QtWidgets.QDoubleSpinBox(); self.sp_eps1.setRange(0.2,4.0); self.sp_eps1.setSingleStep(0.05); self.sp_eps1.setValue(d["eps1"])
        self.sp_eps2 = QtWidgets.QDoubleSpinBox(); self.sp_eps2.setRange(0.2,4.0); self.sp_eps2.setSingleStep(0.05); self.sp_eps2.setValue(d["eps2"])
        self.sp_ax = QtWidgets.QDoubleSpinBox(); self.sp_ax.setRange(0.1,5.0); self.sp_ax.setSingleStep(0.1); self.sp_ax.setValue(d["ax"])
        self.sp_ay = QtWidgets.QDoubleSpinBox(); self.sp_ay.setRange(0.1,5.0); self.sp_ay.setSingleStep(0.1); self.sp_ay.setValue(d["ay"])
        self.sp_az = QtWidgets.QDoubleSpinBox(); self.sp_az.setRange(0.1,5.0); self.sp_az.setSingleStep(0.1); self.sp_az.setValue(d["az"])
        self.sp_geoLevel = QtWidgets.QSpinBox(); self.sp_geoLevel.setRange(0,5); self.sp_geoLevel.setValue(d["geo_level"])
        self.sp_mobW = QtWidgets.QDoubleSpinBox(); self.sp_mobW.setRange(0.05,2.0); self.sp_mobW.setSingleStep(0.05); self.sp_mobW.setValue(d["mobius_w"])
        row(fl, "Topology", self.cb_topology, TOOLTIPS["geometry.topology"], lambda: self.cb_topology.setCurrentText(d["topology"]))
        row(fl, "R", self.sp_R, TOOLTIPS["geometry.R"], lambda: self.sp_R.setValue(d["R"]))
        row(fl, "lat", self.sp_lat, TOOLTIPS["geometry.lat"], lambda: self.sp_lat.setValue(d["lat"]))
        row(fl, "lon", self.sp_lon, TOOLTIPS["geometry.lon"], lambda: self.sp_lon.setValue(d["lon"]))
        row(fl, "N (Fibo/Phyllo)", self.sp_N, TOOLTIPS["geometry.N"], lambda: self.sp_N.setValue(d["N"]))
        row(fl, "phi_g", self.sp_phi, TOOLTIPS["geometry.phi_g"], lambda: self.sp_phi.setValue(d["phi_g"]))
        row(fl, "R_major (torus)", self.sp_Rmaj, TOOLTIPS["geometry.R_major"], lambda: self.sp_Rmaj.setValue(d["R_major"]))
        row(fl, "r_minor (torus)", self.sp_rmin, TOOLTIPS["geometry.r_minor"], lambda: self.sp_rmin.setValue(d["r_minor"]))
        row(fl, "eps1/eps2 (superq)", vec_row([self.sp_eps1,self.sp_eps2]), TOOLTIPS["geometry.eps1"], lambda: (self.sp_eps1.setValue(d["eps1"]), self.sp_eps2.setValue(d["eps2"])))
        row(fl, "ax/ay/az (superq)", vec_row([self.sp_ax,self.sp_ay,self.sp_az]), TOOLTIPS["geometry.ax"], lambda: (self.sp_ax.setValue(d["ax"]), self.sp_ay.setValue(d["ay"]), self.sp_az.setValue(d["az"])))
        row(fl, "geo level", self.sp_geoLevel, TOOLTIPS["geometry.geo_level"], lambda: self.sp_geoLevel.setValue(d["geo_level"]))
        row(fl, "mobius width", self.sp_mobW, TOOLTIPS["geometry.mobius_w"], lambda: self.sp_mobW.setValue(d["mobius_w"]))
        self.cb_topology.currentIndexChanged.connect(self.on_topology_changed)
        for w in [self.sp_R,self.sp_lat,self.sp_lon,self.sp_N,self.sp_phi,self.sp_Rmaj,self.sp_rmin,self.sp_eps1,self.sp_eps2,self.sp_ax,self.sp_ay,self.sp_az,self.sp_geoLevel,self.sp_mobW]:
            w.valueChanged.connect(self.emit_delta)
        self.on_topology_changed()
    def _apply_topology_state(self, emit=True):
        t = self.cb_topology.currentText()
        uv  = (t=="uv_sphere")
        fib = (t=="fibo_sphere")
        phy = (t=="disk_phyllotaxis")
        tor = (t=="torus")
        sup = (t=="superquadric")
        geo = (t=="geodesic")
        mob = (t=="mobius")
        self.sp_lat.setEnabled(uv or tor or sup or mob)
        self.sp_lon.setEnabled(uv or tor or sup or mob)
        self.sp_N.setEnabled(fib or phy)
        self.sp_phi.setEnabled(fib or phy)
        self.sp_Rmaj.setEnabled(tor)
        self.sp_rmin.setEnabled(tor)
        for w in [self.sp_eps1,self.sp_eps2,self.sp_ax,self.sp_ay,self.sp_az]: w.setEnabled(sup)
        self.sp_geoLevel.setEnabled(geo)
        self.sp_mobW.setEnabled(mob)
        if emit:
            self.topologyChanged.emit(t)
            self.emit_delta()
        return t
    def on_topology_changed(self, *a):
        self._apply_topology_state(True)
    def collect(self):
        return dict(
            topology=self.cb_topology.currentText(),
            R=self.sp_R.value(), lat=self.sp_lat.value(), lon=self.sp_lon.value(),
            N=self.sp_N.value(), phi_g=self.sp_phi.value(),
            R_major=self.sp_Rmaj.value(), r_minor=self.sp_rmin.value(),
            eps1=self.sp_eps1.value(), eps2=self.sp_eps2.value(),
            ax=self.sp_ax.value(), ay=self.sp_ay.value(), az=self.sp_az.value(),
            geo_level=self.sp_geoLevel.value(), mobius_w=self.sp_mobW.value()
        )
    def set_defaults(self, cfg):
        cfg = cfg or {}
        d = DEFAULTS["geometry"]
        mappings = [
            (self.cb_topology, cfg.get("topology", d["topology"])),
            (self.sp_R, float(cfg.get("R", d["R"]))),
            (self.sp_lat, int(cfg.get("lat", d["lat"]))),
            (self.sp_lon, int(cfg.get("lon", d["lon"]))),
            (self.sp_N, int(cfg.get("N", d["N"]))),
            (self.sp_phi, float(cfg.get("phi_g", d["phi_g"]))),
            (self.sp_Rmaj, float(cfg.get("R_major", d["R_major"]))),
            (self.sp_rmin, float(cfg.get("r_minor", d["r_minor"]))),
            (self.sp_eps1, float(cfg.get("eps1", d["eps1"]))),
            (self.sp_eps2, float(cfg.get("eps2", d["eps2"]))),
            (self.sp_ax, float(cfg.get("ax", d["ax"]))),
            (self.sp_ay, float(cfg.get("ay", d["ay"]))),
            (self.sp_az, float(cfg.get("az", d["az"]))),
            (self.sp_geoLevel, int(cfg.get("geo_level", d["geo_level"]))),
            (self.sp_mobW, float(cfg.get("mobius_w", d["mobius_w"]))),
        ]

        with QtCore.QSignalBlocker(self.cb_topology):
            self.cb_topology.setCurrentText(mappings[0][1])

        for widget, value in mappings[1:]:
            with QtCore.QSignalBlocker(widget):
                widget.setValue(value)

        self._apply_topology_state(emit=False)
    def set_enabled(self, context: dict): pass
    def emit_delta(self, *a): self.changed.emit({"geometry": self.collect()})
