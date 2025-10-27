from PyQt5 import QtWidgets, QtCore, QtGui

try:
    from .widgets import row
    from .config import DEFAULTS
except ImportError:
    from core.control.widgets import row
    from core.control.config import DEFAULTS


class AppearanceTab(QtWidgets.QWidget):
    changed = QtCore.pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        d = DEFAULTS["appearance"]
        fl = QtWidgets.QFormLayout(self)

        # Couleur unique + picker
        self.ed_color = QtWidgets.QLineEdit(d["color"])
        self.bt_pick = QtWidgets.QPushButton("Pick"); self.bt_pick.clicked.connect(self.pick_color)
        cly = QtWidgets.QHBoxLayout(); cly.setContentsMargins(0,0,0,0)
        cly.addWidget(self.ed_color, 1); cly.addWidget(self.bt_pick, 0)
        cw = QtWidgets.QWidget(); cw.setLayout(cly)
        row(fl, "color (hex)", cw, "Couleur principale", reset_cb=lambda: (self.ed_color.setText(d["color"]), self.emit_delta()))

        # Liste de couleurs
        self.ed_colors = QtWidgets.QLineEdit(d["colors"])
        row(fl, "colors (list@pos)", self.ed_colors, "Ex: #F00@0,#0F0@0.5,#00F@1",
            reset_cb=lambda: (self.ed_colors.setText(d["colors"]), self.emit_delta()))

        # Opacité / taille
        self.sp_opacity = QtWidgets.QDoubleSpinBox(); self.sp_opacity.setRange(0.0,1.0); self.sp_opacity.setSingleStep(0.05); self.sp_opacity.setValue(d["opacity"])
        self.sp_px = QtWidgets.QDoubleSpinBox(); self.sp_px.setRange(0.1,20.0); self.sp_px.setSingleStep(0.1); self.sp_px.setValue(d["px"])
        row(fl, "opacity", self.sp_opacity, "Opacité globale", reset_cb=lambda: (self.sp_opacity.setValue(d["opacity"]), self.emit_delta()))
        row(fl, "particle size (px)", self.sp_px, "Taille particule", reset_cb=lambda: (self.sp_px.setValue(d["px"]), self.emit_delta()))

        # Palette et options
        self.cb_palette = QtWidgets.QComboBox()
        self.cb_palette.addItems([
            "uniform","gradient_linear","gradient_radial",
            "every_other","every_kth","stripe_longitude",
            "random_from_list","hsl_time","directional",
            "by_lat","by_lon","by_noise"
        ])
        self.cb_palette.setCurrentText(d["palette"])
        row(fl, "palette", self.cb_palette, "Schéma de couleur", reset_cb=lambda: (self.cb_palette.setCurrentText(d["palette"]), self.emit_delta()))

        self.sp_paletteK = QtWidgets.QSpinBox(); self.sp_paletteK.setRange(1,512); self.sp_paletteK.setValue(d["paletteK"])
        row(fl, "every_kth (K)", self.sp_paletteK, "Périodicité", reset_cb=lambda: (self.sp_paletteK.setValue(d["paletteK"]), self.emit_delta()))

        # Blend / shape / profondeur alpha
        self.cb_blend = QtWidgets.QComboBox(); self.cb_blend.addItems(["source-over","lighter","multiply","screen"]); self.cb_blend.setCurrentText(d["blendMode"])
        self.cb_shape = QtWidgets.QComboBox(); self.cb_shape.addItems(["circle","square"]); self.cb_shape.setCurrentText(d["shape"])
        self.sp_alphaDepth = QtWidgets.QDoubleSpinBox(); self.sp_alphaDepth.setRange(0.0,1.0); self.sp_alphaDepth.setSingleStep(0.05); self.sp_alphaDepth.setValue(d["alphaDepth"])
        row(fl, "blend", self.cb_blend, "Mode de fusion", reset_cb=lambda: (self.cb_blend.setCurrentText(d["blendMode"]), self.emit_delta()))
        row(fl, "shape", self.cb_shape, "Forme sprite", reset_cb=lambda: (self.cb_shape.setCurrentText(d["shape"]), self.emit_delta()))
        row(fl, "alphaDepth", self.sp_alphaDepth, "Fondu distance", reset_cb=lambda: (self.sp_alphaDepth.setValue(d["alphaDepth"]), self.emit_delta()))

        # HSL
        self.sp_h0 = QtWidgets.QDoubleSpinBox(); self.sp_h0.setRange(0.0,360.0); self.sp_h0.setValue(d["h0"])
        self.sp_dh = QtWidgets.QDoubleSpinBox(); self.sp_dh.setRange(0.0,360.0); self.sp_dh.setValue(d["dh"])
        self.sp_wh = QtWidgets.QDoubleSpinBox(); self.sp_wh.setRange(0.0,20.0); self.sp_wh.setValue(d["wh"])
        row(fl, "HSL h0", self.sp_h0, "Teinte base (°)", reset_cb=lambda: (self.sp_h0.setValue(d["h0"]), self.emit_delta()))
        row(fl, "HSL Δh", self.sp_dh, "Amplitude teinte (°)", reset_cb=lambda: (self.sp_dh.setValue(d["dh"]), self.emit_delta()))
        row(fl, "HSL ω", self.sp_wh, "Vitesse teinte", reset_cb=lambda: (self.sp_wh.setValue(d["wh"]), self.emit_delta()))

        # Noise
        self.sp_noiseScale = QtWidgets.QDoubleSpinBox(); self.sp_noiseScale.setRange(0.05,10.0); self.sp_noiseScale.setSingleStep(0.05); self.sp_noiseScale.setValue(d["noiseScale"])
        self.sp_noiseSpeed = QtWidgets.QDoubleSpinBox(); self.sp_noiseSpeed.setRange(0.0,5.0); self.sp_noiseSpeed.setSingleStep(0.1); self.sp_noiseSpeed.setValue(d["noiseSpeed"])
        row(fl, "noise scale", self.sp_noiseScale, "Échelle bruit", reset_cb=lambda: (self.sp_noiseScale.setValue(d["noiseScale"]), self.emit_delta()))
        row(fl, "noise speed", self.sp_noiseSpeed, "Vitesse bruit", reset_cb=lambda: (self.sp_noiseSpeed.setValue(d["noiseSpeed"]), self.emit_delta()))

        # Modulation de taille
        self.cb_pxMode = QtWidgets.QComboBox(); self.cb_pxMode.addItems(["none","by_index","by_radius"]); self.cb_pxMode.setCurrentText(d["pxModMode"])
        self.sp_pxAmp = QtWidgets.QDoubleSpinBox(); self.sp_pxAmp.setRange(0.0,1.0); self.sp_pxAmp.setSingleStep(0.01); self.sp_pxAmp.setValue(d["pxModAmp"])
        self.sp_pxFreq = QtWidgets.QDoubleSpinBox(); self.sp_pxFreq.setRange(0.0,10.0); self.sp_pxFreq.setSingleStep(0.1); self.sp_pxFreq.setValue(d["pxModFreq"])
        self.sp_pxPhase = QtWidgets.QDoubleSpinBox(); self.sp_pxPhase.setRange(0.0,360.0); self.sp_pxPhase.setValue(d["pxModPhaseDeg"])
        row(fl, "px mode", self.cb_pxMode, "Modulation taille", reset_cb=lambda: (self.cb_pxMode.setCurrentText(d["pxModMode"]), self.emit_delta()))
        row(fl, "px amp", self.sp_pxAmp, "Amplitude", reset_cb=lambda: (self.sp_pxAmp.setValue(d["pxModAmp"]), self.emit_delta()))
        row(fl, "px freq", self.sp_pxFreq, "Fréquence", reset_cb=lambda: (self.sp_pxFreq.setValue(d["pxModFreq"]), self.emit_delta()))
        row(fl, "px phase (°)", self.sp_pxPhase, "Phase", reset_cb=lambda: (self.sp_pxPhase.setValue(d["pxModPhaseDeg"]), self.emit_delta()))

        # Signaux
        for w in self.findChildren((QtWidgets.QDoubleSpinBox, QtWidgets.QComboBox, QtWidgets.QLineEdit)):
            if isinstance(w, QtWidgets.QLineEdit): w.editingFinished.connect(self._on_change)
            elif isinstance(w, QtWidgets.QComboBox): w.currentIndexChanged.connect(self._on_change)
            else: w.valueChanged.connect(self._on_change)

        self.cb_palette.currentIndexChanged.connect(self.sync_enabled)
        self.cb_pxMode.currentIndexChanged.connect(self.sync_enabled)
        self.sync_enabled()  # grise ce qu’il faut

    def sync_enabled(self):
        p = self.cb_palette.currentText()
        enable_colors = enable_k = enable_hsl = enable_noise = False

        if p == "uniform":
            pass
        elif p in ("gradient_linear", "gradient_radial", "every_other", "stripe_longitude", "random_from_list"):
            enable_colors = True
        elif p == "every_kth":
            enable_colors = True; enable_k = True
        elif p in ("hsl_time", "by_lat", "by_lon", "directional"):
            enable_hsl = True
        elif p == "by_noise":
            enable_noise = True; enable_colors = True  # si mix sur 2 stops

        self.ed_colors.setEnabled(enable_colors)
        self.sp_paletteK.setEnabled(enable_k)
        for w in (self.sp_h0, self.sp_dh, self.sp_wh): w.setEnabled(enable_hsl)
        for w in (self.sp_noiseScale, self.sp_noiseSpeed): w.setEnabled(enable_noise)

        pm = self.cb_pxMode.currentText()
        px_enabled = (pm != "none")
        self.sp_pxAmp.setEnabled(px_enabled)
        self.sp_pxFreq.setEnabled(px_enabled)
        self.sp_pxPhase.setEnabled(px_enabled)

        self.emit_delta()

    def _on_change(self, *a): self.sync_enabled()

    def emit_delta(self): self.changed.emit({"appearance": self.collect()})

    def collect(self):
        return dict(
            color=self.ed_color.text().strip(),
            colors=self.ed_colors.text().strip(),
            opacity=self.sp_opacity.value(),
            px=self.sp_px.value(),
            palette=self.cb_palette.currentText(),
            paletteK=self.sp_paletteK.value(),
            blendMode=self.cb_blend.currentText(),
            shape=self.cb_shape.currentText(),
            alphaDepth=self.sp_alphaDepth.value(),
            h0=self.sp_h0.value(), dh=self.sp_dh.value(), wh=self.sp_wh.value(),
            noiseScale=self.sp_noiseScale.value(), noiseSpeed=self.sp_noiseSpeed.value(),
            pxModMode=self.cb_pxMode.currentText(), pxModAmp=self.sp_pxAmp.value(),
            pxModFreq=self.sp_pxFreq.value(), pxModPhaseDeg=self.sp_pxPhase.value(),
        )

    def pick_color(self):
        c = QtWidgets.QColorDialog.getColor(QtGui.QColor(self.ed_color.text().strip() or "#00C8FF"), self, "Couleur")
        if c.isValid():
            self.ed_color.setText(c.name())
            self.emit_delta()
