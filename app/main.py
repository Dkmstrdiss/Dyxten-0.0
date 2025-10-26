# -*- coding: utf-8 -*-
import sys, json
from pathlib import Path
from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QSurfaceFormat, QColor
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings, QWebEnginePage

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "ui" / "web" / "index.html"

fmt = QSurfaceFormat(); fmt.setAlphaBufferSize(8); QSurfaceFormat.setDefaultFormat(fmt)

class ViewWindow(QtWidgets.QMainWindow):
    def __init__(self, html_path: Path, screen: QtGui.QScreen):
        super().__init__(None)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.view = QWebEngineView(self); self.view.setPage(QWebEnginePage(self.view))
        s = self.view.settings()
        s.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        s.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, False)
        s.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        s.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)

        w = QtWidgets.QWidget(); w.setAutoFillBackground(False); w.setAttribute(Qt.WA_NoSystemBackground, True)
        lay = QtWidgets.QVBoxLayout(w); lay.setContentsMargins(0,0,0,0); lay.addWidget(self.view)
        self.setCentralWidget(w)

        self.view.load(QUrl.fromLocalFile(str(html_path.resolve())))
        self.setGeometry(screen.availableGeometry())
        QtWidgets.QShortcut(Qt.Key_Escape, self, activated=self.close)
        QtCore.QTimer.singleShot(300, lambda: self.set_transparent(True))

    def set_transparent(self, enabled: bool):
        self.setAttribute(Qt.WA_TranslucentBackground, enabled)
        self.setStyleSheet("background: transparent;" if enabled else "")
        self.view.setAttribute(Qt.WA_TranslucentBackground, enabled)
        self.view.setStyleSheet("background: transparent;" if enabled else "")
        try:
            self.view.page().setBackgroundColor(QColor(0, 0, 0, 0) if enabled else QColor(0, 0, 0, 255))
        except Exception:
            pass
        self.centralWidget().setAutoFillBackground(not enabled)
        self.view.update(); self.update()

class ControlWindow(QtWidgets.QMainWindow):
    def __init__(self, app: QtWidgets.QApplication, screen: QtGui.QScreen, view_win: ViewWindow):
        super().__init__(None)
        self.setWindowTitle("Dyxten — Control"); self.view_win = view_win
        self.tabs = QtWidgets.QTabWidget()

        def mk_info(t: str):
            b = QtWidgets.QToolButton(); b.setText("i"); b.setCursor(Qt.PointingHandCursor)
            b.setToolTipDuration(0); b.setToolTip(t); b.setFixedSize(20,20)
            b.setStyleSheet("QToolButton{border:1px solid #7aa7c7;border-radius:10px;font-weight:bold;padding:0;color:#2b6ea8;background:#e6f2fb;}QToolButton:hover{background:#d8ecfa;}")
            return b
        def mk_reset(cb):
            b = QtWidgets.QToolButton(); b.setText("↺"); b.setCursor(Qt.PointingHandCursor)
            b.setToolTip("Réinitialiser"); b.setFixedSize(22,22)
            b.setStyleSheet("QToolButton{border:1px solid #9aa5b1;border-radius:11px;padding:0;background:#f2f4f7;color:#2b2b2b;font-weight:bold;}QToolButton:hover{background:#e9edf2;}")
            b.clicked.connect(cb); return b
        def row(form, label, widget, tip, reset_cb=None):
            h = QtWidgets.QHBoxLayout(); h.setContentsMargins(0,0,0,0); h.setSpacing(6)
            h.addWidget(widget, 1)
            if reset_cb: h.addWidget(mk_reset(reset_cb), 0)
            h.addWidget(mk_info(tip), 0)
            w = QtWidgets.QWidget(); w.setLayout(h); form.addRow(label, w)

        self.defaults = dict(
            camRadius=3.2, camHeightDeg=15, camTiltDeg=0, omegaDegPerSec=20, fov=600,
            topology="uv_sphere",
            R=1.0, lat=64, lon=64, N=4096, phi_g=3.88322,
            # torus
            R_major=1.2, r_minor=0.45,
            # superquadric
            eps1=1.0, eps2=1.0, ax=1.0, ay=1.0, az=1.0,
            # geodesic
            geo_level=1,
            # mobius
            mobius_w=0.4,

            # Apparence étendue
            color="#00C8FF", colors="#00C8FF@0,#FFFFFF@1",
            opacity=1.0, px=2.0,
            palette="uniform", paletteK=2,
            h0=200.0, dh=0.0, wh=0.0,
            blendMode="source-over", shape="circle",
            alphaDepth=0.0,
            noiseScale=1.0, noiseSpeed=0.0,

            rotX=0.0, rotY=0.0, rotZ=0.0, pulseA=0.0, pulseW=1.0,
            pulsePhaseDeg=0.0, rotPhaseDeg=0.0, rotPhaseMode="none",
            pxModAmp=0.0, pxModFreq=0.0, pxModPhaseDeg=0.0, pxModMode="none",

            pr="uniform_area", dmin_px=0.0,

            # Masques
            maskEnabled=False, maskMode="none", maskAngleDeg=30.0,
            maskBandHalfDeg=20.0, maskLonCenterDeg=0.0, maskLonWidthDeg=30.0,
            maskSoftDeg=10.0, maskInvert=False,

            Nmax=50000, dprClamp=2.0, depthSort=True, transparent=True
        )

        # Caméra
        cam = QtWidgets.QWidget(); fl = QtWidgets.QFormLayout(cam)
        self.sp_camRadius = QtWidgets.QDoubleSpinBox(); self.sp_camRadius.setRange(0.1, 20.0); self.sp_camRadius.setValue(self.defaults["camRadius"]); self.sp_camRadius.setSingleStep(0.1)
        self.sl_camHeight = QtWidgets.QSlider(Qt.Horizontal); self.sl_camHeight.setRange(-90, 90); self.sl_camHeight.setValue(self.defaults["camHeightDeg"])
        self.sl_camTilt   = QtWidgets.QSlider(Qt.Horizontal); self.sl_camTilt.setRange(-90, 90); self.sl_camTilt.setValue(self.defaults["camTiltDeg"])
        self.sl_omega     = QtWidgets.QSlider(Qt.Horizontal); self.sl_omega.setRange(0, 180); self.sl_omega.setValue(self.defaults["omegaDegPerSec"])
        self.sp_fov       = QtWidgets.QSpinBox(); self.sp_fov.setRange(50, 2000); self.sp_fov.setValue(self.defaults["fov"])
        row(fl, "camRadius", self.sp_camRadius, "Distance caméra (zoom).", lambda: self.sp_camRadius.setValue(self.defaults["camRadius"]))
        row(fl, "camHeightDeg", self.sl_camHeight, "Hauteur d’orbite (°).", lambda: self.sl_camHeight.setValue(self.defaults["camHeightDeg"]))
        row(fl, "camTiltDeg", self.sl_camTilt, "Inclinaison du plan (°).", lambda: self.sl_camTilt.setValue(self.defaults["camTiltDeg"]))
        row(fl, "omegaDegPerSec", self.sl_omega, "Vitesse d’orbite (°/s).", lambda: self.sl_omega.setValue(self.defaults["omegaDegPerSec"]))
        row(fl, "fov", self.sp_fov, "Champ de vision.", lambda: self.sp_fov.setValue(self.defaults["fov"]))
        self.tabs.addTab(cam, "Caméra")

        # Géométrie
        geo = QtWidgets.QWidget(); fl = QtWidgets.QFormLayout(geo)
        self.cb_topology = QtWidgets.QComboBox()
        self.cb_topology.addItems(["uv_sphere","fibo_sphere","disk_phyllotaxis","torus","superquadric","geodesic","mobius"])
        self.sp_R   = QtWidgets.QDoubleSpinBox(); self.sp_R.setRange(0.1, 5.0); self.sp_R.setValue(self.defaults["R"]); self.sp_R.setSingleStep(0.1)
        self.sp_lat = QtWidgets.QSpinBox(); self.sp_lat.setRange(4, 512); self.sp_lat.setValue(self.defaults["lat"])
        self.sp_lon = QtWidgets.QSpinBox(); self.sp_lon.setRange(4, 512); self.sp_lon.setValue(self.defaults["lon"])
        self.sp_N   = QtWidgets.QSpinBox(); self.sp_N.setRange(10, 200000); self.sp_N.setValue(self.defaults["N"])
        self.sp_phi_g = QtWidgets.QDoubleSpinBox(); self.sp_phi_g.setRange(0.0, 6.28318); self.sp_phi_g.setDecimals(5); self.sp_phi_g.setValue(self.defaults["phi_g"])
        # torus
        self.sp_Rmaj = QtWidgets.QDoubleSpinBox(); self.sp_Rmaj.setRange(0.1, 10.0); self.sp_Rmaj.setSingleStep(0.05); self.sp_Rmaj.setValue(self.defaults["R_major"])
        self.sp_rmin = QtWidgets.QDoubleSpinBox(); self.sp_rmin.setRange(0.05, 5.0); self.sp_rmin.setSingleStep(0.05); self.sp_rmin.setValue(self.defaults["r_minor"])
        # superquadric
        self.sp_eps1 = QtWidgets.QDoubleSpinBox(); self.sp_eps1.setRange(0.2, 4.0); self.sp_eps1.setSingleStep(0.05); self.sp_eps1.setValue(self.defaults["eps1"])
        self.sp_eps2 = QtWidgets.QDoubleSpinBox(); self.sp_eps2.setRange(0.2, 4.0); self.sp_eps2.setSingleStep(0.05); self.sp_eps2.setValue(self.defaults["eps2"])
        self.sp_ax = QtWidgets.QDoubleSpinBox(); self.sp_ax.setRange(0.1, 5.0); self.sp_ax.setSingleStep(0.1); self.sp_ax.setValue(self.defaults["ax"])
        self.sp_ay = QtWidgets.QDoubleSpinBox(); self.sp_ay.setRange(0.1, 5.0); self.sp_ay.setSingleStep(0.1); self.sp_ay.setValue(self.defaults["ay"])
        self.sp_az = QtWidgets.QDoubleSpinBox(); self.sp_az.setRange(0.1, 5.0); self.sp_az.setSingleStep(0.1); self.sp_az.setValue(self.defaults["az"])
        # geodesic
        self.sp_geoLevel = QtWidgets.QSpinBox(); self.sp_geoLevel.setRange(0, 5); self.sp_geoLevel.setValue(self.defaults["geo_level"])
        # mobius
        self.sp_mobW = QtWidgets.QDoubleSpinBox(); self.sp_mobW.setRange(0.05, 2.0); self.sp_mobW.setSingleStep(0.05); self.sp_mobW.setValue(self.defaults["mobius_w"])

        row(fl, "Topology", self.cb_topology, "UV, Fibo, Phyllo, Torus, Superquadric, Geodesic, Möbius.", lambda: self.cb_topology.setCurrentText(self.defaults["topology"]))
        row(fl, "R", self.sp_R, "Échelle globale.", lambda: self.sp_R.setValue(self.defaults["R"]))
        row(fl, "lat", self.sp_lat, "Anneaux / v-samples.", lambda: self.sp_lat.setValue(self.defaults["lat"]))
        row(fl, "lon", self.sp_lon, "Segments / u-samples.", lambda: self.sp_lon.setValue(self.defaults["lon"]))
        row(fl, "N (Fibo/Phyllo)", self.sp_N, "Nombre total (génératifs).", lambda: self.sp_N.setValue(self.defaults["N"]))
        row(fl, "phi_g", self.sp_phi_g, "Angle doré.", lambda: self.sp_phi_g.setValue(self.defaults["phi_g"]))
        row(fl, "R_major (torus)", self.sp_Rmaj, "Grand rayon.", lambda: self.sp_Rmaj.setValue(self.defaults["R_major"]))
        row(fl, "r_minor (torus)", self.sp_rmin, "Rayon tube.", lambda: self.sp_rmin.setValue(self.defaults["r_minor"]))
        row(fl, "eps1 / eps2 (superq)", self._mk_vec_row([self.sp_eps1, self.sp_eps2]), "Exposants (forme).", lambda: (self.sp_eps1.setValue(self.defaults["eps1"]), self.sp_eps2.setValue(self.defaults["eps2"])))
        row(fl, "ax / ay / az (superq)", self._mk_vec_row([self.sp_ax, self.sp_ay, self.sp_az]), "Axes (échelle X/Y/Z).", lambda: (self.sp_ax.setValue(self.defaults["ax"]), self.sp_ay.setValue(self.defaults["ay"]), self.sp_az.setValue(self.defaults["az"])))
        row(fl, "geo level", self.sp_geoLevel, "Subdiv icosa (0..5).", lambda: self.sp_geoLevel.setValue(self.defaults["geo_level"]))
        row(fl, "mobius width", self.sp_mobW, "Largeur du ruban.", lambda: self.sp_mobW.setValue(self.defaults["mobius_w"]))
        self.tabs.addTab(geo, "Géométrie")

        # Apparence
        appa = QtWidgets.QWidget(); fl = QtWidgets.QFormLayout(appa)
        self.ed_color = QtWidgets.QLineEdit(self.defaults["color"])
        self.bt_pick = QtWidgets.QPushButton("Pick")
        def pick_color():
            c = QtWidgets.QColorDialog.getColor(QtGui.QColor(self.ed_color.text().strip() or "#00C8FF"), self, "Couleur")
            if c.isValid(): self.ed_color.setText(c.name()); self.push_params()
        self.bt_pick.clicked.connect(pick_color)
        cly = QtWidgets.QHBoxLayout(); cly.setContentsMargins(0,0,0,0); cly.addWidget(self.ed_color,1); cly.addWidget(self.bt_pick,0)
        cw = QtWidgets.QWidget(); cw.setLayout(cly)

        self.ed_colors = QtWidgets.QLineEdit(self.defaults["colors"])
        self.sp_opacity = QtWidgets.QDoubleSpinBox(); self.sp_opacity.setRange(0.0, 1.0); self.sp_opacity.setSingleStep(0.05); self.sp_opacity.setValue(self.defaults["opacity"])
        self.sp_px  = QtWidgets.QDoubleSpinBox(); self.sp_px.setRange(0.1, 20.0); self.sp_px.setSingleStep(0.1); self.sp_px.setValue(self.defaults["px"])
        self.cb_palette = QtWidgets.QComboBox()
        self.cb_palette.addItems([
            "uniform","gradient_linear","gradient_radial","every_other","every_kth","stripe_longitude","random_from_list",
            "hsl_time","directional","by_lat","by_lon","by_noise"
        ])
        self.sp_paletteK = QtWidgets.QSpinBox(); self.sp_paletteK.setRange(1, 512); self.sp_paletteK.setValue(self.defaults["paletteK"])
        self.cb_blend = QtWidgets.QComboBox(); self.cb_blend.addItems(["source-over","lighter","multiply","screen"])
        self.cb_shape = QtWidgets.QComboBox(); self.cb_shape.addItems(["circle","square"])
        self.sp_alphaDepth = QtWidgets.QDoubleSpinBox(); self.sp_alphaDepth.setRange(0.0,1.0); self.sp_alphaDepth.setSingleStep(0.05); self.sp_alphaDepth.setValue(self.defaults["alphaDepth"])
        self.sp_h0 = QtWidgets.QDoubleSpinBox(); self.sp_h0.setRange(0.0, 360.0); self.sp_h0.setValue(self.defaults["h0"])
        self.sp_dh = QtWidgets.QDoubleSpinBox(); self.sp_dh.setRange(0.0, 360.0); self.sp_dh.setValue(self.defaults["dh"])
        self.sp_wh = QtWidgets.QDoubleSpinBox(); self.sp_wh.setRange(0.0, 20.0); self.sp_wh.setValue(self.defaults["wh"])
        self.sp_noiseScale = QtWidgets.QDoubleSpinBox(); self.sp_noiseScale.setRange(0.05, 10.0); self.sp_noiseScale.setSingleStep(0.05); self.sp_noiseScale.setValue(self.defaults["noiseScale"])
        self.sp_noiseSpeed = QtWidgets.QDoubleSpinBox(); self.sp_noiseSpeed.setRange(0.0, 5.0); self.sp_noiseSpeed.setSingleStep(0.1); self.sp_noiseSpeed.setValue(self.defaults["noiseSpeed"])

        def row_simple(label, widget, tip):
            h = QtWidgets.QHBoxLayout(); h.setContentsMargins(0,0,0,0); h.setSpacing(6); h.addWidget(widget,1); h.addWidget(mk_info(tip),0)
            w = QtWidgets.QWidget(); w.setLayout(h); fl.addRow(label, w)

        row_simple("color (hex)", cw, "Couleur principale.")
        row_simple("colors (list@pos)", self.ed_colors, "Multi-stops: ex. #ff0@0,#0ff@0.5,#00f@1")
        row(fl, "opacity", self.sp_opacity, "Transparence 0..1.", lambda: self.sp_opacity.setValue(self.defaults["opacity"]))
        row(fl, "particle size (px)", self.sp_px, "Taille des particules.", lambda: self.sp_px.setValue(self.defaults["px"]))
        row(fl, "palette", self.cb_palette, "Schéma de couleur.", lambda: self.cb_palette.setCurrentText(self.defaults["palette"]))
        row(fl, "every_kth (K)", self.sp_paletteK, "Taille de bloc pour every_kth.", lambda: self.sp_paletteK.setValue(self.defaults["paletteK"]))
        row(fl, "blend", self.cb_blend, "Mode de fusion canvas.", lambda: self.cb_blend.setCurrentText(self.defaults["blendMode"]))
        row(fl, "shape", self.cb_shape, "Forme: cercle/carré.", lambda: self.cb_shape.setCurrentText(self.defaults["shape"]))
        row(fl, "alphaDepth", self.sp_alphaDepth, "Fondu avec distance.", lambda: self.sp_alphaDepth.setValue(self.defaults["alphaDepth"]))
        row(fl, "HSL h0", self.sp_h0, "Teinte base.", lambda: self.sp_h0.setValue(self.defaults["h0"]))
        row(fl, "HSL Δh", self.sp_dh, "Amplitude teinte.", lambda: self.sp_dh.setValue(self.defaults["dh"]))
        row(fl, "HSL ω", self.sp_wh, "Vitesse teinte.", lambda: self.sp_wh.setValue(self.defaults["wh"]))
        row(fl, "noise scale", self.sp_noiseScale, "Échelle bruit (by_noise).", lambda: self.sp_noiseScale.setValue(self.defaults["noiseScale"]))
        row(fl, "noise speed", self.sp_noiseSpeed, "Vitesse anim bruit.", lambda: self.sp_noiseSpeed.setValue(self.defaults["noiseSpeed"]))

        # modulation taille
        self.cb_pxMode = QtWidgets.QComboBox(); self.cb_pxMode.addItems(["none","by_index","by_radius"])
        self.sp_pxAmp = QtWidgets.QDoubleSpinBox(); self.sp_pxAmp.setRange(0.0,1.0); self.sp_pxAmp.setSingleStep(0.01); self.sp_pxAmp.setValue(self.defaults["pxModAmp"])
        self.sp_pxFreq = QtWidgets.QDoubleSpinBox(); self.sp_pxFreq.setRange(0.0,10.0); self.sp_pxFreq.setSingleStep(0.1); self.sp_pxFreq.setValue(self.defaults["pxModFreq"])
        self.sp_pxPhase = QtWidgets.QDoubleSpinBox(); self.sp_pxPhase.setRange(0.0,360.0); self.sp_pxPhase.setValue(self.defaults["pxModPhaseDeg"])
        row(fl, "px mode", self.cb_pxMode, "Déphasage taille.", lambda: self.cb_pxMode.setCurrentText(self.defaults["pxModMode"]))
        row(fl, "px amp", self.sp_pxAmp, "Amplitude taille.", lambda: self.sp_pxAmp.setValue(self.defaults["pxModAmp"]))
        row(fl, "px freq", self.sp_pxFreq, "Fréquence taille.", lambda: self.sp_pxFreq.setValue(self.defaults["pxModFreq"]))
        row(fl, "px phase (°)", self.sp_pxPhase, "Phase taille.", lambda: self.sp_pxPhase.setValue(self.defaults["pxModPhaseDeg"]))
        self.tabs.addTab(appa, "Apparence")

        # Dynamique
        dyn = QtWidgets.QWidget(); fl = QtWidgets.QFormLayout(dyn)
        self.sp_rotX = QtWidgets.QDoubleSpinBox(); self.sp_rotX.setRange(-360,360); self.sp_rotX.setValue(self.defaults["rotX"])
        self.sp_rotY = QtWidgets.QDoubleSpinBox(); self.sp_rotY.setRange(-360,360); self.sp_rotY.setValue(self.defaults["rotY"])
        self.sp_rotZ = QtWidgets.QDoubleSpinBox(); self.sp_rotZ.setRange(-360,360); self.sp_rotZ.setValue(self.defaults["rotZ"])
        self.sp_pulseA = QtWidgets.QDoubleSpinBox(); self.sp_pulseA.setRange(0.0,1.0); self.sp_pulseA.setSingleStep(0.01); self.sp_pulseA.setValue(self.defaults["pulseA"])
        self.sp_pulseW = QtWidgets.QDoubleSpinBox(); self.sp_pulseW.setRange(0.0,20.0); self.sp_pulseW.setValue(self.defaults["pulseW"])
        row(fl, "rotX (°/s)", self.sp_rotX, "Rotation locale X.", lambda: self.sp_rotX.setValue(self.defaults["rotX"]))
        row(fl, "rotY (°/s)", self.sp_rotY, "Rotation locale Y.", lambda: self.sp_rotY.setValue(self.defaults["rotY"]))
        row(fl, "rotZ (°/s)", self.sp_rotZ, "Rotation locale Z.", lambda: self.sp_rotZ.setValue(self.defaults["rotZ"]))
        row(fl, "pulse A", self.sp_pulseA, "Amplitude pulsation.", lambda: self.sp_pulseA.setValue(self.defaults["pulseA"]))
        row(fl, "pulse ω", self.sp_pulseW, "Fréquence pulsation.", lambda: self.sp_pulseW.setValue(self.defaults["pulseW"]))

        self.sp_pulsePhase = QtWidgets.QDoubleSpinBox(); self.sp_pulsePhase.setRange(0.0,360.0); self.sp_pulsePhase.setValue(self.defaults["pulsePhaseDeg"])
        self.cb_rotPhaseMode = QtWidgets.QComboBox(); self.cb_rotPhaseMode.addItems(["none","by_index","by_radius"])
        self.sp_rotPhaseDeg = QtWidgets.QDoubleSpinBox(); self.sp_rotPhaseDeg.setRange(0.0,360.0); self.sp_rotPhaseDeg.setValue(self.defaults["rotPhaseDeg"])
        row(fl, "pulse phase (°)", self.sp_pulsePhase, "Phase initiale pulsation.", lambda: self.sp_pulsePhase.setValue(self.defaults["pulsePhaseDeg"]))
        row(fl, "rot phase mode", self.cb_rotPhaseMode, "Déphasage rotation.", lambda: self.cb_rotPhaseMode.setCurrentText(self.defaults["rotPhaseMode"]))
        row(fl, "rot phase (°)", self.sp_rotPhaseDeg, "Amplitude phase rotation.", lambda: self.sp_rotPhaseDeg.setValue(self.defaults["rotPhaseDeg"]))
        self.tabs.addTab(dyn, "Dynamique")

        # Distribution
        dist = QtWidgets.QWidget(); fl = QtWidgets.QFormLayout(dist)
        self.cb_pr = QtWidgets.QComboBox(); self.cb_pr.addItems(["uniform_area","power_edge","gaussian_center","by_lat","by_lon"])
        self.sp_dmin_px = QtWidgets.QDoubleSpinBox(); self.sp_dmin_px.setRange(0.0, 200.0); self.sp_dmin_px.setSingleStep(1.0); self.sp_dmin_px.setValue(self.defaults["dmin_px"])
        row(fl, "p(select)", self.cb_pr, "Biais de conservation de points.", lambda: self.cb_pr.setCurrentText(self.defaults["pr"]))
        row(fl, "d_min (px)", self.sp_dmin_px, "Espacement minimal écran (pixels).", lambda: self.sp_dmin_px.setValue(self.defaults["dmin_px"]))
        self.tabs.addTab(dist, "Distribution")

        # Masques
        mask = QtWidgets.QWidget(); fl = QtWidgets.QFormLayout(mask)
        self.chk_mask = QtWidgets.QCheckBox(); self.chk_mask.setChecked(self.defaults["maskEnabled"])
        self.cb_maskMode = QtWidgets.QComboBox(); self.cb_maskMode.addItems(["none","north_cap","south_cap","equatorial_band","longitudinal_band"])
        self.sp_maskAngle = QtWidgets.QDoubleSpinBox(); self.sp_maskAngle.setRange(0.0,90.0); self.sp_maskAngle.setSingleStep(1.0); self.sp_maskAngle.setValue(self.defaults["maskAngleDeg"])
        self.sp_maskBand = QtWidgets.QDoubleSpinBox(); self.sp_maskBand.setRange(0.0,90.0); self.sp_maskBand.setSingleStep(1.0); self.sp_maskBand.setValue(self.defaults["maskBandHalfDeg"])
        self.sp_maskLonC = QtWidgets.QDoubleSpinBox(); self.sp_maskLonC.setRange(-180.0,180.0); self.sp_maskLonC.setSingleStep(1.0); self.sp_maskLonC.setValue(self.defaults["maskLonCenterDeg"])
        self.sp_maskLonW = QtWidgets.QDoubleSpinBox(); self.sp_maskLonW.setRange(0.0,180.0); self.sp_maskLonW.setSingleStep(1.0); self.sp_maskLonW.setValue(self.defaults["maskLonWidthDeg"])
        self.sp_maskSoft = QtWidgets.QDoubleSpinBox(); self.sp_maskSoft.setRange(0.0,45.0); self.sp_maskSoft.setSingleStep(1.0); self.sp_maskSoft.setValue(self.defaults["maskSoftDeg"])
        self.chk_maskInv = QtWidgets.QCheckBox(); self.chk_maskInv.setChecked(self.defaults["maskInvert"])
        row(fl, "enable", self.chk_mask, "Activer masque géométrique.", lambda: self.chk_mask.setChecked(self.defaults["maskEnabled"]))
        row(fl, "mode", self.cb_maskMode, "Type de masque.", lambda: self.cb_maskMode.setCurrentText(self.defaults["maskMode"]))
        row(fl, "cap angle (°)", self.sp_maskAngle, "Rayon du cap polaire.", lambda: self.sp_maskAngle.setValue(self.defaults["maskAngleDeg"]))
        row(fl, "band half (°)", self.sp_maskBand, "Demi-largeur bande équatoriale.", lambda: self.sp_maskBand.setValue(self.defaults["maskBandHalfDeg"]))
        row(fl, "lon center (°)", self.sp_maskLonC, "Centre longitude.", lambda: self.sp_maskLonC.setValue(self.defaults["maskLonCenterDeg"]))
        row(fl, "lon width (°)", self.sp_maskLonW, "Largeur longitude.", lambda: self.sp_maskLonW.setValue(self.defaults["maskLonWidthDeg"]))
        row(fl, "soft (°)", self.sp_maskSoft, "Lissage des bords.", lambda: self.sp_maskSoft.setValue(self.defaults["maskSoftDeg"]))
        row(fl, "invert", self.chk_maskInv, "Inverser masque.", lambda: self.chk_maskInv.setChecked(self.defaults["maskInvert"]))
        self.tabs.addTab(mask, "Masques")

        # Système
        sysw = QtWidgets.QWidget(); fl = QtWidgets.QFormLayout(sysw)
        self.sp_Nmax = QtWidgets.QSpinBox(); self.sp_Nmax.setRange(100,500000); self.sp_Nmax.setValue(self.defaults["Nmax"])
        self.sp_dpr  = QtWidgets.QDoubleSpinBox(); self.sp_dpr.setRange(1.0,2.0); self.sp_dpr.setSingleStep(0.1); self.sp_dpr.setValue(self.defaults["dprClamp"])
        self.chk_depthSort = QtWidgets.QCheckBox(); self.chk_depthSort.setChecked(self.defaults["depthSort"])
        self.chk_transparent = QtWidgets.QCheckBox(); self.chk_transparent.setChecked(self.defaults["transparent"])
        self.bt_shutdown = QtWidgets.QPushButton("Shutdown"); self.bt_shutdown.clicked.connect(app.quit)
        row(fl, "N max", self.sp_Nmax, "Budget points.", lambda: self.sp_Nmax.setValue(self.defaults["Nmax"]))
        row(fl, "DPR clamp", self.sp_dpr, "Limite résolution.", lambda: self.sp_dpr.setValue(self.defaults["dprClamp"]))
        row(fl, "Tri profondeur", self.chk_depthSort, "Dessin back→front.", lambda: self.chk_depthSort.setChecked(self.defaults["depthSort"]))
        row(fl, "Transparence", self.chk_transparent, "Bureau visible.", lambda: self.chk_transparent.setChecked(self.defaults["transparent"]))
        fl.addRow(self.bt_shutdown)
        self.tabs.addTab(sysw, "Système")

        # Fenêtre
        self.setCentralWidget(self.tabs); self.resize(700, 880)
        geo = screen.availableGeometry()
        self.move(geo.x()+(geo.width()-self.width())//2, geo.y()+(geo.height()-self.height())//2)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True); self.show()

        for w in self.findChildren((QtWidgets.QSlider, QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox,
                                    QtWidgets.QComboBox, QtWidgets.QLineEdit, QtWidgets.QCheckBox)):
            if isinstance(w, QtWidgets.QSlider): w.valueChanged.connect(self.push_params)
            elif isinstance(w, (QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox)): w.valueChanged.connect(self.push_params)
            elif isinstance(w, QtWidgets.QComboBox):
                w.currentIndexChanged.connect(self.on_topology_changed if w is self.cb_topology else self.push_params)
            elif isinstance(w, QtWidgets.QLineEdit): w.editingFinished.connect(self.push_params)
            elif isinstance(w, QtWidgets.QCheckBox): w.stateChanged.connect(self.push_params)

        self.view_win.view.page().loadFinished.connect(lambda ok: self.push_params())
        self.on_topology_changed(); self.push_params()

    def _mk_vec_row(self, spins):
        h = QtWidgets.QHBoxLayout(); h.setContentsMargins(0,0,0,0); h.setSpacing(6)
        for s in spins: h.addWidget(s)
        w = QtWidgets.QWidget(); w.setLayout(h); return w

    def on_topology_changed(self):
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
        self.sp_phi_g.setEnabled(fib or phy)

        self.sp_Rmaj.setEnabled(tor); self.sp_rmin.setEnabled(tor)
        self.sp_eps1.setEnabled(sup); self.sp_eps2.setEnabled(sup)
        self.sp_ax.setEnabled(sup); self.sp_ay.setEnabled(sup); self.sp_az.setEnabled(sup)
        self.sp_geoLevel.setEnabled(geo)
        self.sp_mobW.setEnabled(mob)
        self.push_params()

    def collect_params(self):
        return {
            "camera": {
                "camRadius": self.sp_camRadius.value(),
                "camHeightDeg": self.sl_camHeight.value(),
                "camTiltDeg": self.sl_camTilt.value(),
                "omegaDegPerSec": self.sl_omega.value(),
                "fov": self.sp_fov.value()
            },
            "geometry": {
                "topology": self.cb_topology.currentText(),
                "R": self.sp_R.value(), "lat": self.sp_lat.value(), "lon": self.sp_lon.value(),
                "N": self.sp_N.value(), "phi_g": self.sp_phi_g.value(),
                "R_major": self.sp_Rmaj.value(), "r_minor": self.sp_rmin.value(),
                "eps1": self.sp_eps1.value(), "eps2": self.sp_eps2.value(),
                "ax": self.sp_ax.value(), "ay": self.sp_ay.value(), "az": self.sp_az.value(),
                "geo_level": self.sp_geoLevel.value(),
                "mobius_w": self.sp_mobW.value()
            },
            "appearance": {
                "color": self.ed_color.text().strip(),
                "colors": self.ed_colors.text().strip(),
                "opacity": self.sp_opacity.value(),
                "px": self.sp_px.value(),
                "palette": self.cb_palette.currentText(),
                "paletteK": self.sp_paletteK.value(),
                "blendMode": self.cb_blend.currentText(),
                "shape": self.cb_shape.currentText(),
                "alphaDepth": self.sp_alphaDepth.value(),
                "h0": self.sp_h0.value(), "dh": self.sp_dh.value(), "wh": self.sp_wh.value(),
                "noiseScale": self.sp_noiseScale.value(), "noiseSpeed": self.sp_noiseSpeed.value(),
                "pxModMode": self.cb_pxMode.currentText(),
                "pxModAmp": self.sp_pxAmp.value(),
                "pxModFreq": self.sp_pxFreq.value(),
                "pxModPhaseDeg": self.sp_pxPhase.value()
            },
            "dynamics": {
                "rotX": self.sp_rotX.value(), "rotY": self.sp_rotY.value(), "rotZ": self.sp_rotZ.value(),
                "pulseA": self.sp_pulseA.value(), "pulseW": self.sp_pulseW.value(),
                "pulsePhaseDeg": self.sp_pulsePhase.value(),
                "rotPhaseMode": self.cb_rotPhaseMode.currentText(),
                "rotPhaseDeg": self.sp_rotPhaseDeg.value()
            },
            "distribution": {
                "pr": self.cb_pr.currentText(), "dmin_px": self.sp_dmin_px.value()
            },
            "mask": {
                "enabled": self.chk_mask.isChecked(),
                "mode": self.cb_maskMode.currentText(),
                "angleDeg": self.sp_maskAngle.value(),
                "bandHalfDeg": self.sp_maskBand.value(),
                "lonCenterDeg": self.sp_maskLonC.value(),
                "lonWidthDeg": self.sp_maskLonW.value(),
                "softDeg": self.sp_maskSoft.value(),
                "invert": self.chk_maskInv.isChecked()
            },
            "system": {
                "Nmax": self.sp_Nmax.value(), "dprClamp": self.sp_dpr.value(),
                "depthSort": self.chk_depthSort.isChecked(), "transparent": self.chk_transparent.isChecked()
            }
        }

    def push_params(self):
        p = self.collect_params()
        self.view_win.set_transparent(bool(p["system"]["transparent"]))
        js = "window.setDyxtenParams = window.setDyxtenParams || function(_){};" \
             f"window.setDyxtenParams({json.dumps(p, ensure_ascii=False)});"
        try: self.view_win.view.page().runJavaScript(js)
        except Exception: pass

def main():
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication(sys.argv)
    screens = QtGui.QGuiApplication.screens()
    primary = QtGui.QGuiApplication.primaryScreen()
    second = screens[1] if len(screens)>1 else primary
    view_win = ViewWindow(HTML, primary); view_win.show()
    _ = ControlWindow(app, second, view_win)
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
