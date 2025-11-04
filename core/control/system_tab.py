
from PyQt5 import QtWidgets, QtCore
from .widgets import row, SubProfilePanel
from .config import DEFAULTS, TOOLTIPS
from .link_registry import register_linkable_widget

class SystemTab(QtWidgets.QWidget):
    changed = QtCore.pyqtSignal(dict)
    def __init__(self):
        super().__init__()
        d = DEFAULTS["system"]

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        self._subprofile_panel = SubProfilePanel("Sous-profil système")
        outer.addWidget(self._subprofile_panel)

        container = QtWidgets.QWidget()
        fl = QtWidgets.QFormLayout(container)
        fl.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(container)
        self.sp_Nmax = QtWidgets.QSpinBox(); self.sp_Nmax.setRange(100,500000); self.sp_Nmax.setValue(d["Nmax"])
        self.sp_dpr  = QtWidgets.QDoubleSpinBox(); self.sp_dpr.setRange(1.0,2.0); self.sp_dpr.setSingleStep(0.1); self.sp_dpr.setValue(d["dprClamp"])
        self.sp_gravity_strength = QtWidgets.QDoubleSpinBox(); self.sp_gravity_strength.setRange(0.0,1.0); self.sp_gravity_strength.setSingleStep(0.05); self.sp_gravity_strength.setDecimals(3); self.sp_gravity_strength.setValue(d["donutGravityStrength"])
        self.sp_gravity_falloff = QtWidgets.QDoubleSpinBox(); self.sp_gravity_falloff.setRange(0.2,5.0); self.sp_gravity_falloff.setSingleStep(0.1); self.sp_gravity_falloff.setDecimals(3); self.sp_gravity_falloff.setValue(d["donutGravityFalloff"])
        self.sp_ring_offset = QtWidgets.QDoubleSpinBox(); self.sp_ring_offset.setRange(-48.0,120.0); self.sp_ring_offset.setSingleStep(1.0); self.sp_ring_offset.setDecimals(1); self.sp_ring_offset.setValue(d["donutGravityRingOffset"])
        self.chk_depthSort = QtWidgets.QCheckBox(); self.chk_depthSort.setChecked(d["depthSort"])
        self.chk_transparent = QtWidgets.QCheckBox(); self.chk_transparent.setChecked(d["transparent"])
        row(fl, "Particules max", self.sp_Nmax, TOOLTIPS["system.Nmax"], lambda: self.sp_Nmax.setValue(d["Nmax"]))
        row(fl, "Limite haute résolution", self.sp_dpr, TOOLTIPS["system.dprClamp"], lambda: self.sp_dpr.setValue(d["dprClamp"]))
        row(fl, "Gravité donut (force)", self.sp_gravity_strength, TOOLTIPS["system.donutGravityStrength"], lambda: self.sp_gravity_strength.setValue(d["donutGravityStrength"]))
        row(fl, "Gravité donut (progression)", self.sp_gravity_falloff, TOOLTIPS["system.donutGravityFalloff"], lambda: self.sp_gravity_falloff.setValue(d["donutGravityFalloff"]))
        row(fl, "Anneau donut (offset px)", self.sp_ring_offset, TOOLTIPS["system.donutGravityRingOffset"], lambda: self.sp_ring_offset.setValue(d["donutGravityRingOffset"]))
        row(fl, "Tri par profondeur", self.chk_depthSort, TOOLTIPS["system.depthSort"], lambda: self.chk_depthSort.setChecked(d["depthSort"]))
        row(fl, "Fenêtre transparente", self.chk_transparent, TOOLTIPS["system.transparent"], lambda: self.chk_transparent.setChecked(d["transparent"]))
        for w in [
            self.sp_Nmax,
            self.sp_dpr,
            self.sp_gravity_strength,
            self.sp_gravity_falloff,
            self.sp_ring_offset,
            self.chk_depthSort,
            self.chk_transparent,
        ]:
            if isinstance(w, QtWidgets.QCheckBox): w.stateChanged.connect(self.emit_delta)
            else: w.valueChanged.connect(self.emit_delta)
        register_linkable_widget(self.sp_Nmax, section="system", key="Nmax", tab="Système")
        register_linkable_widget(self.sp_dpr, section="system", key="dprClamp", tab="Système")
        register_linkable_widget(self.sp_gravity_strength, section="system", key="donutGravityStrength", tab="Système")
        register_linkable_widget(self.sp_gravity_falloff, section="system", key="donutGravityFalloff", tab="Système")
        register_linkable_widget(self.sp_ring_offset, section="system", key="donutGravityRingOffset", tab="Système")
        self._sync_subprofile_state()
    def collect(self):
        return dict(
            Nmax=self.sp_Nmax.value(),
            dprClamp=self.sp_dpr.value(),
            donutGravityStrength=self.sp_gravity_strength.value(),
            donutGravityFalloff=self.sp_gravity_falloff.value(),
            donutGravityRingOffset=self.sp_ring_offset.value(),
            depthSort=self.chk_depthSort.isChecked(),
            transparent=self.chk_transparent.isChecked(),
        )
    def set_defaults(self, cfg):
        cfg = cfg or {}
        d = DEFAULTS["system"]
        with QtCore.QSignalBlocker(self.sp_Nmax):
            self.sp_Nmax.setValue(int(cfg.get("Nmax", d["Nmax"])))
        with QtCore.QSignalBlocker(self.sp_dpr):
            self.sp_dpr.setValue(float(cfg.get("dprClamp", d["dprClamp"])))
        with QtCore.QSignalBlocker(self.sp_gravity_strength):
            self.sp_gravity_strength.setValue(float(cfg.get("donutGravityStrength", d["donutGravityStrength"])))
        with QtCore.QSignalBlocker(self.sp_gravity_falloff):
            self.sp_gravity_falloff.setValue(float(cfg.get("donutGravityFalloff", d["donutGravityFalloff"])))
        with QtCore.QSignalBlocker(self.sp_ring_offset):
            self.sp_ring_offset.setValue(float(cfg.get("donutGravityRingOffset", d["donutGravityRingOffset"])))
        with QtCore.QSignalBlocker(self.chk_depthSort):
            self.chk_depthSort.setChecked(bool(cfg.get("depthSort", d["depthSort"])))
        with QtCore.QSignalBlocker(self.chk_transparent):
            self.chk_transparent.setChecked(bool(cfg.get("transparent", d["transparent"])))
        self._sync_subprofile_state()
    def set_enabled(self, context: dict): pass
    def emit_delta(self, *a):
        self._sync_subprofile_state()
        self.changed.emit({"system": self.collect()})

    def attach_subprofile_manager(self, manager):
        self._subprofile_panel.bind(
            manager=manager,
            section="system",
            defaults=DEFAULTS["system"],
            collect_cb=self.collect,
            apply_cb=self.set_defaults,
            on_change=self.emit_delta,
        )
        self._sync_subprofile_state()

    def _sync_subprofile_state(self):
        if hasattr(self, "_subprofile_panel") and self._subprofile_panel is not None:
            self._subprofile_panel.sync_from_data(self.collect())
