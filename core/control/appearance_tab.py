
from PyQt5 import QtWidgets, QtCore, QtGui
from .widgets import row
from .config import DEFAULTS, TOOLTIPS

class AppearanceTab(QtWidgets.QWidget):
    changed = QtCore.pyqtSignal(dict)
    def __init__(self):
        super().__init__()
        d = DEFAULTS["appearance"]
        fl = QtWidgets.QFormLayout(self)
        self.ed_color = QtWidgets.QLineEdit(d["color"])
        self.bt_pick = QtWidgets.QPushButton("Pick"); self.bt_pick.clicked.connect(self.pick_color)
        cly = QtWidgets.QHBoxLayout(); cly.setContentsMargins(0,0,0,0); cly.addWidget(self.ed_color,1); cly.addWidget(self.bt_pick,0)
        cw = QtWidgets.QWidget(); cw.setLayout(cly)
        self.ed_colors = QtWidgets.QLineEdit(d["colors"])
        self.sp_opacity = QtWidgets.QDoubleSpinBox(); self.sp_opacity.setRange(0.0,1.0); self.sp_opacity.setSingleStep(0.05); self.sp_opacity.setValue(d["opacity"])
        self.sp_px = QtWidgets.QDoubleSpinBox(); self.sp_px.setRange(0.1,20.0); self.sp_px.setSingleStep(0.1); self.sp_px.setValue(d["px"])
        self.cb_palette = QtWidgets.QComboBox(); self.cb_palette.addItems(["uniform","gradient_linear","gradient_radial","every_other","every_kth","stripe_longitude","random_from_list","hsl_time","directional","by_lat","by_lon","by_noise"]); self.cb_palette.setCurrentText(d["palette"])
        self.sp_paletteK = QtWidgets.QSpinBox(); self.sp_paletteK.setRange(1,512); self.sp_paletteK.setValue(d["paletteK"])
        self.cb_blend = QtWidgets.QComboBox(); self.cb_blend.addItems(["source-over","lighter","multiply","screen"]); self.cb_blend.setCurrentText(d["blendMode"])
        self.cb_shape = QtWidgets.QComboBox(); self.cb_shape.addItems(["circle","square"]); self.cb_shape.setCurrentText(d["shape"])
        self.sp_alphaDepth = QtWidgets.QDoubleSpinBox(); self.sp_alphaDepth.setRange(0.0,1.0); self.sp_alphaDepth.setSingleStep(0.05); self.sp_alphaDepth.setValue(d["alphaDepth"])
        self.sp_h0 = QtWidgets.QDoubleSpinBox(); self.sp_h0.setRange(0.0,360.0); self.sp_h0.setValue(d["h0"])
        self.sp_dh = QtWidgets.QDoubleSpinBox(); self.sp_dh.setRange(0.0,360.0); self.sp_dh.setValue(d["dh"])
        self.sp_wh = QtWidgets.QDoubleSpinBox(); self.sp_wh.setRange(0.0,20.0); self.sp_wh.setValue(d["wh"])
        self.sp_noiseScale = QtWidgets.QDoubleSpinBox(); self.sp_noiseScale.setRange(0.05,10.0); self.sp_noiseScale.setSingleStep(0.05); self.sp_noiseScale.setValue(d["noiseScale"])
        self.sp_noiseSpeed = QtWidgets.QDoubleSpinBox(); self.sp_noiseSpeed.setRange(0.0,5.0); self.sp_noiseSpeed.setSingleStep(0.1); self.sp_noiseSpeed.setValue(d["noiseSpeed"])
        row(fl, "color (hex)", cw, TOOLTIPS["appearance.color"], lambda: self.ed_color.setText(d["color"]))
        row(fl, "colors (list@pos)", self.ed_colors, TOOLTIPS["appearance.colors"], lambda: self.ed_colors.setText(d["colors"]))
        row(fl, "opacity", self.sp_opacity, TOOLTIPS["appearance.opacity"], lambda: self.sp_opacity.setValue(d["opacity"]))
        row(fl, "particle size (px)", self.sp_px, TOOLTIPS["appearance.px"], lambda: self.sp_px.setValue(d["px"]))
        row(fl, "palette", self.cb_palette, TOOLTIPS["appearance.palette"], lambda: self.cb_palette.setCurrentText(d["palette"]))
        row(fl, "every_kth (K)", self.sp_paletteK, TOOLTIPS["appearance.paletteK"], lambda: self.sp_paletteK.setValue(d["paletteK"]))
        row(fl, "blend", self.cb_blend, TOOLTIPS["appearance.blendMode"], lambda: self.cb_blend.setCurrentText(d["blendMode"]))
        row(fl, "shape", self.cb_shape, TOOLTIPS["appearance.shape"], lambda: self.cb_shape.setCurrentText(d["shape"]))
        row(fl, "alphaDepth", self.sp_alphaDepth, TOOLTIPS["appearance.alphaDepth"], lambda: self.sp_alphaDepth.setValue(d["alphaDepth"]))
        row(fl, "HSL h0", self.sp_h0, TOOLTIPS["appearance.h0"], lambda: self.sp_h0.setValue(d["h0"]))
        row(fl, "HSL Δh", self.sp_dh, TOOLTIPS["appearance.dh"], lambda: self.sp_dh.setValue(d["dh"]))
        row(fl, "HSL ω", self.sp_wh, TOOLTIPS["appearance.wh"], lambda: self.sp_wh.setValue(d["wh"]))
        row(fl, "noise scale", self.sp_noiseScale, TOOLTIPS["appearance.noiseScale"], lambda: self.sp_noiseScale.setValue(d["noiseScale"]))
        row(fl, "noise speed", self.sp_noiseSpeed, TOOLTIPS["appearance.noiseSpeed"], lambda: self.sp_noiseSpeed.setValue(d["noiseSpeed"]))
        self.cb_pxMode = QtWidgets.QComboBox(); self.cb_pxMode.addItems(["none","by_index","by_radius"]); self.cb_pxMode.setCurrentText(d["pxModMode"])
        self.sp_pxAmp = QtWidgets.QDoubleSpinBox(); self.sp_pxAmp.setRange(0.0,1.0); self.sp_pxAmp.setSingleStep(0.01); self.sp_pxAmp.setValue(d["pxModAmp"])
        self.sp_pxFreq = QtWidgets.QDoubleSpinBox(); self.sp_pxFreq.setRange(0.0,10.0); self.sp_pxFreq.setSingleStep(0.1); self.sp_pxFreq.setValue(d["pxModFreq"])
        self.sp_pxPhase = QtWidgets.QDoubleSpinBox(); self.sp_pxPhase.setRange(0.0,360.0); self.sp_pxPhase.setValue(d["pxModPhaseDeg"])
        row(fl, "px mode", self.cb_pxMode, TOOLTIPS["appearance.pxModMode"], lambda: self.cb_pxMode.setCurrentText(d["pxModMode"]))
        row(fl, "px amp", self.sp_pxAmp, TOOLTIPS["appearance.pxModAmp"], lambda: self.sp_pxAmp.setValue(d["pxModAmp"]))
        row(fl, "px freq", self.sp_pxFreq, TOOLTIPS["appearance.pxModFreq"], lambda: self.sp_pxFreq.setValue(d["pxModFreq"]))
        row(fl, "px phase (°)", self.sp_pxPhase, TOOLTIPS["appearance.pxModPhaseDeg"], lambda: self.sp_pxPhase.setValue(d["pxModPhaseDeg"]))
        for w in self.findChildren((QtWidgets.QDoubleSpinBox, QtWidgets.QComboBox, QtWidgets.QLineEdit)):
            if isinstance(w, QtWidgets.QLineEdit): w.editingFinished.connect(self.emit_delta)
            elif isinstance(w, QtWidgets.QComboBox): w.currentIndexChanged.connect(self.emit_delta)
            else: w.valueChanged.connect(self.emit_delta)
    def pick_color(self):
        c = QtWidgets.QColorDialog.getColor(QtGui.QColor(self.ed_color.text().strip() or "#00C8FF"), self, "Couleur")
        if c.isValid(): self.ed_color.setText(c.name()); self.emit_delta()
    def collect(self):
        return dict(color=self.ed_color.text().strip(), colors=self.ed_colors.text().strip(), opacity=self.sp_opacity.value(),
                    px=self.sp_px.value(), palette=self.cb_palette.currentText(), paletteK=self.sp_paletteK.value(),
                    blendMode=self.cb_blend.currentText(), shape=self.cb_shape.currentText(), alphaDepth=self.sp_alphaDepth.value(),
                    h0=self.sp_h0.value(), dh=self.sp_dh.value(), wh=self.sp_wh.value(),
                    noiseScale=self.sp_noiseScale.value(), noiseSpeed=self.sp_noiseSpeed.value(),
                    pxModMode=self.cb_pxMode.currentText(), pxModAmp=self.sp_pxAmp.value(), pxModFreq=self.sp_pxFreq.value(), pxModPhaseDeg=self.sp_pxPhase.value())
    def set_defaults(self, cfg): pass
    def set_enabled(self, context: dict): pass
    def emit_delta(self, *a): self.changed.emit({"appearance": self.collect()})
