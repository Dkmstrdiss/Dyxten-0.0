from PyQt5 import QtWidgets, QtCore, QtGui

try:
    from .widgets import row, SubProfilePanel
    from .config import DEFAULTS
except ImportError:
    from core.control.widgets import row, SubProfilePanel
    from core.control.config import DEFAULTS


def open_color_dialog(parent, initial: QtGui.QColor, title: str) -> QtGui.QColor:
    dlg = QtWidgets.QColorDialog(initial, parent)
    dlg.setWindowTitle(title)
    dlg.setOption(QtWidgets.QColorDialog.ShowAlphaChannel, False)
    dlg.setStyleSheet("""
        QColorDialog, QColorDialog QWidget {
            color: #15151f;
            background-color: #ffffff;
        }
        QPushButton {
            color: #000000;
        }
    """)
    if dlg.exec_() == QtWidgets.QDialog.Accepted:
        return dlg.selectedColor()
    return QtGui.QColor()


class AppearanceTab(QtWidgets.QWidget):
    changed = QtCore.pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        d = DEFAULTS["appearance"]
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        self._subprofile_panel = SubProfilePanel("Sous-profil apparence")
        outer.addWidget(self._subprofile_panel)

        container = QtWidgets.QWidget()
        fl = QtWidgets.QFormLayout(container)
        fl.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(container)
        self.rows = {}

        # Couleur unique + picker
        self.ed_color = QtWidgets.QLineEdit(d["color"])
        self.bt_pick = QtWidgets.QPushButton("Pick"); self.bt_pick.clicked.connect(self.pick_color)
        self.bt_pick.setStyleSheet("color: #FFFFFF;")
        cly = QtWidgets.QHBoxLayout(); cly.setContentsMargins(0,0,0,0)
        cly.addWidget(self.ed_color, 1); cly.addWidget(self.bt_pick, 0)
        cw = QtWidgets.QWidget(); cw.setLayout(cly)
        self.rows["color"] = row(
            fl,
            "Couleur principale",
            cw,
            "Couleur appliquée à toutes les particules lorsque la palette est uniforme.",
            reset_cb=lambda: (self.ed_color.setText(d["color"]), self.emit_delta()),
        )

        # Liste de couleurs
        self.ed_colors = QtWidgets.QLineEdit(d["colors"])
        self.bt_colors = QtWidgets.QPushButton("Pick list")
        self.bt_colors.setStyleSheet("color: #FFFFFF;")
        self.bt_colors.clicked.connect(self.pick_colors)
        cly = QtWidgets.QHBoxLayout(); cly.setContentsMargins(0, 0, 0, 0)
        cly.addWidget(self.ed_colors, 1); cly.addWidget(self.bt_colors, 0)
        cw = QtWidgets.QWidget(); cw.setLayout(cly)
        self.rows["colors"] = row(
            fl,
            "Dégradé personnalisé",
            cw,
            "Liste de couleurs et positions (ex. #F00@0,#0F0@0.5,#00F@1) pour les palettes dynamiques.",
            reset_cb=lambda: (self.ed_colors.setText(d["colors"]), self.emit_delta()),
        )

        # Opacité / taille
        self.sp_opacity = QtWidgets.QDoubleSpinBox(); self.sp_opacity.setRange(0.0,1.0); self.sp_opacity.setSingleStep(0.05); self.sp_opacity.setValue(d["opacity"])
        self.sp_px = QtWidgets.QDoubleSpinBox(); self.sp_px.setRange(0.1,50.0); self.sp_px.setSingleStep(0.1); self.sp_px.setValue(d["px"])
        self.rows["opacity"] = row(fl, "Opacité", self.sp_opacity, "Rend les particules plus ou moins transparentes.", reset_cb=lambda: (self.sp_opacity.setValue(d["opacity"]), self.emit_delta()))
        self.rows["px"] = row(fl, "Taille des particules (px)", self.sp_px, "Définit le diamètre moyen des particules à l’écran.", reset_cb=lambda: (self.sp_px.setValue(d["px"]), self.emit_delta()))

        # Palette et options
        self.cb_palette = QtWidgets.QComboBox()
        self.cb_palette.addItems([
            "uniform","gradient_linear","gradient_radial",
            "every_other","every_kth","stripe_longitude",
            "random_from_list","hsl_time","directional",
            "by_lat","by_lon","by_noise"
        ])
        self.cb_palette.setCurrentText(d["palette"])
        self.rows["palette"] = row(fl, "Palette de couleurs", self.cb_palette, "Choisissez la façon dont les couleurs sont attribuées aux particules.", reset_cb=lambda: (self.cb_palette.setCurrentText(d["palette"]), self.emit_delta()))

        self.sp_paletteK = QtWidgets.QSpinBox(); self.sp_paletteK.setRange(1,512); self.sp_paletteK.setValue(d["paletteK"])
        self.rows["paletteK"] = row(fl, "Répétition (K)", self.sp_paletteK, "Nombre d’éléments avant que le motif de couleurs ne se répète.", reset_cb=lambda: (self.sp_paletteK.setValue(d["paletteK"]), self.emit_delta()))

        # Blend / shape / profondeur alpha
        self.cb_blend = QtWidgets.QComboBox(); self.cb_blend.addItems(["source-over","lighter","multiply","screen"]); self.cb_blend.setCurrentText(d["blendMode"])
        self.cb_shape = QtWidgets.QComboBox(); self.cb_shape.addItems(["circle","square"]); self.cb_shape.setCurrentText(d["shape"])
        self.sp_alphaDepth = QtWidgets.QDoubleSpinBox(); self.sp_alphaDepth.setRange(0.0,1.0); self.sp_alphaDepth.setSingleStep(0.05); self.sp_alphaDepth.setValue(d["alphaDepth"])
        self.rows["blendMode"] = row(fl, "Fusion des couleurs", self.cb_blend, "Détermine comment les particules se mélangent entre elles et avec l’arrière-plan.", reset_cb=lambda: (self.cb_blend.setCurrentText(d["blendMode"]), self.emit_delta()))
        self.rows["shape"] = row(fl, "Forme des particules", self.cb_shape, "Choisissez entre des particules rondes ou carrées.", reset_cb=lambda: (self.cb_shape.setCurrentText(d["shape"]), self.emit_delta()))
        self.rows["alphaDepth"] = row(fl, "Fondu avec la profondeur", self.sp_alphaDepth, "Atténue progressivement les particules lointaines.", reset_cb=lambda: (self.sp_alphaDepth.setValue(d["alphaDepth"]), self.emit_delta()))

        # HSL
        self.sp_h0 = QtWidgets.QDoubleSpinBox(); self.sp_h0.setRange(0.0,360.0); self.sp_h0.setValue(d["h0"])
        self.sp_dh = QtWidgets.QDoubleSpinBox(); self.sp_dh.setRange(0.0,360.0); self.sp_dh.setValue(d["dh"])
        self.sp_wh = QtWidgets.QDoubleSpinBox(); self.sp_wh.setRange(0.0,20.0); self.sp_wh.setValue(d["wh"])
        self.rows["h0"] = row(fl, "Teinte de départ (°)", self.sp_h0, "Couleur de base utilisée par les palettes HSL animées.", reset_cb=lambda: (self.sp_h0.setValue(d["h0"]), self.emit_delta()))
        self.rows["dh"] = row(fl, "Amplitude de teinte (°)", self.sp_dh, "Élargit la plage de couleurs parcourue par l’animation.", reset_cb=lambda: (self.sp_dh.setValue(d["dh"]), self.emit_delta()))
        self.rows["wh"] = row(fl, "Vitesse de variation", self.sp_wh, "Contrôle la rapidité du changement de couleur dans le temps.", reset_cb=lambda: (self.sp_wh.setValue(d["wh"]), self.emit_delta()))

        # Noise
        self.sp_noiseScale = QtWidgets.QDoubleSpinBox(); self.sp_noiseScale.setRange(0.05,10.0); self.sp_noiseScale.setSingleStep(0.05); self.sp_noiseScale.setValue(d["noiseScale"])
        self.sp_noiseSpeed = QtWidgets.QDoubleSpinBox(); self.sp_noiseSpeed.setRange(0.0,5.0); self.sp_noiseSpeed.setSingleStep(0.1); self.sp_noiseSpeed.setValue(d["noiseSpeed"])
        self.rows["noiseScale"] = row(fl, "Taille du relief", self.sp_noiseScale, "Définit la taille des variations de couleur générées par le bruit.", reset_cb=lambda: (self.sp_noiseScale.setValue(d["noiseScale"]), self.emit_delta()))
        self.rows["noiseSpeed"] = row(fl, "Vitesse du relief", self.sp_noiseSpeed, "Anime les variations de couleur générées par le bruit.", reset_cb=lambda: (self.sp_noiseSpeed.setValue(d["noiseSpeed"]), self.emit_delta()))

        # Modulation de taille
        self.cb_pxMode = QtWidgets.QComboBox(); self.cb_pxMode.addItems(["none","by_index","by_radius"]); self.cb_pxMode.setCurrentText(d["pxModMode"])
        self.sp_pxAmp = QtWidgets.QDoubleSpinBox(); self.sp_pxAmp.setRange(0.0,1.0); self.sp_pxAmp.setSingleStep(0.01); self.sp_pxAmp.setValue(d["pxModAmp"])
        self.sp_pxFreq = QtWidgets.QDoubleSpinBox(); self.sp_pxFreq.setRange(0.0,10.0); self.sp_pxFreq.setSingleStep(0.1); self.sp_pxFreq.setValue(d["pxModFreq"])
        self.sp_pxPhase = QtWidgets.QDoubleSpinBox(); self.sp_pxPhase.setRange(0.0,360.0); self.sp_pxPhase.setValue(d["pxModPhaseDeg"])
        self.rows["pxModMode"] = row(fl, "Variation de taille", self.cb_pxMode, "Active des effets qui agrandissent ou réduisent les particules selon leur position.", reset_cb=lambda: (self.cb_pxMode.setCurrentText(d["pxModMode"]), self.emit_delta()))
        self.rows["pxModAmp"] = row(fl, "Amplitude de variation", self.sp_pxAmp, "Contrôle l’écart maximum entre les particules les plus petites et les plus grandes.", reset_cb=lambda: (self.sp_pxAmp.setValue(d["pxModAmp"]), self.emit_delta()))
        self.rows["pxModFreq"] = row(fl, "Rythme de variation", self.sp_pxFreq, "Règle la répétition du motif de taille.", reset_cb=lambda: (self.sp_pxFreq.setValue(d["pxModFreq"]), self.emit_delta()))
        self.rows["pxModPhaseDeg"] = row(fl, "Décalage du motif (°)", self.sp_pxPhase, "Décale le motif de variation pour aligner les tailles comme souhaité.", reset_cb=lambda: (self.sp_pxPhase.setValue(d["pxModPhaseDeg"]), self.emit_delta()))

        # Signaux
        for w in self.findChildren((QtWidgets.QDoubleSpinBox, QtWidgets.QComboBox, QtWidgets.QLineEdit)):
            if isinstance(w, QtWidgets.QLineEdit): w.editingFinished.connect(self._on_change)
            elif isinstance(w, QtWidgets.QComboBox): w.currentIndexChanged.connect(self._on_change)
            else: w.valueChanged.connect(self._on_change)

        self.cb_palette.currentIndexChanged.connect(self.sync_enabled)
        self.cb_pxMode.currentIndexChanged.connect(self.sync_enabled)
        self.sync_enabled()  # grise ce qu’il faut
        self._sync_subprofile_state()

    def sync_enabled(self, emit=True):
        palette = self.cb_palette.currentText()

        show_color = palette not in ("hsl_time", "by_lat", "by_lon", "directional")
        show_colors = palette in {"gradient_linear", "gradient_radial", "every_other", "every_kth", "stripe_longitude", "random_from_list", "by_noise"}
        show_k = palette == "every_kth"
        show_hsl = palette in ("hsl_time", "by_lat", "by_lon", "directional")
        show_noise = palette == "by_noise"

        self._set_row_visible("color", show_color)
        self._set_row_visible("colors", show_colors)
        self._set_row_visible("paletteK", show_k)
        for key in ("h0", "dh", "wh"):
            self._set_row_visible(key, show_hsl)
        for key in ("noiseScale", "noiseSpeed"):
            self._set_row_visible(key, show_noise)

        self.ed_colors.setEnabled(show_colors)
        self.sp_paletteK.setEnabled(show_k)
        for w in (self.sp_h0, self.sp_dh, self.sp_wh):
            w.setEnabled(show_hsl)
        for w in (self.sp_noiseScale, self.sp_noiseSpeed):
            w.setEnabled(show_noise)

        pm = self.cb_pxMode.currentText()
        show_px_mod = pm != "none"
        for key in ("pxModAmp", "pxModFreq", "pxModPhaseDeg"):
            self._set_row_visible(key, show_px_mod)
        self.sp_pxAmp.setEnabled(show_px_mod)
        self.sp_pxFreq.setEnabled(show_px_mod)
        self.sp_pxPhase.setEnabled(show_px_mod)

        if emit:
            self.emit_delta()

    def _on_change(self, *a): self.sync_enabled()

    def _set_row_visible(self, key: str, visible: bool):
        row_widget = self.rows.get(key)
        if row_widget is None:
            return
        row_widget.setVisible(visible)
        label = getattr(row_widget, "_form_label", None)
        if label is not None:
            label.setVisible(visible)

    def emit_delta(self):
        self._sync_subprofile_state()
        self.changed.emit({"appearance": self.collect()})

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

    def attach_subprofile_manager(self, manager):
        self._subprofile_panel.bind(
            manager=manager,
            section="appearance",
            defaults=DEFAULTS["appearance"],
            collect_cb=self.collect,
            apply_cb=self.set_defaults,
            on_change=self.emit_delta,
        )
        self._sync_subprofile_state()

    def set_defaults(self, cfg):
        cfg = cfg or {}
        d = DEFAULTS["appearance"]
        def val(key):
            return cfg.get(key, d[key])

        with QtCore.QSignalBlocker(self.ed_color):
            self.ed_color.setText(str(val("color")))
        with QtCore.QSignalBlocker(self.ed_colors):
            self.ed_colors.setText(str(val("colors")))
        with QtCore.QSignalBlocker(self.sp_opacity):
            self.sp_opacity.setValue(float(val("opacity")))
        with QtCore.QSignalBlocker(self.sp_px):
            self.sp_px.setValue(float(val("px")))
        with QtCore.QSignalBlocker(self.cb_palette):
            self.cb_palette.setCurrentText(str(val("palette")))
        with QtCore.QSignalBlocker(self.sp_paletteK):
            self.sp_paletteK.setValue(int(val("paletteK")))
        with QtCore.QSignalBlocker(self.cb_blend):
            self.cb_blend.setCurrentText(str(val("blendMode")))
        with QtCore.QSignalBlocker(self.cb_shape):
            self.cb_shape.setCurrentText(str(val("shape")))
        with QtCore.QSignalBlocker(self.sp_alphaDepth):
            self.sp_alphaDepth.setValue(float(val("alphaDepth")))
        with QtCore.QSignalBlocker(self.sp_h0):
            self.sp_h0.setValue(float(val("h0")))
        with QtCore.QSignalBlocker(self.sp_dh):
            self.sp_dh.setValue(float(val("dh")))
        with QtCore.QSignalBlocker(self.sp_wh):
            self.sp_wh.setValue(float(val("wh")))
        with QtCore.QSignalBlocker(self.sp_noiseScale):
            self.sp_noiseScale.setValue(float(val("noiseScale")))
        with QtCore.QSignalBlocker(self.sp_noiseSpeed):
            self.sp_noiseSpeed.setValue(float(val("noiseSpeed")))
        with QtCore.QSignalBlocker(self.cb_pxMode):
            self.cb_pxMode.setCurrentText(str(val("pxModMode")))
        with QtCore.QSignalBlocker(self.sp_pxAmp):
            self.sp_pxAmp.setValue(float(val("pxModAmp")))
        with QtCore.QSignalBlocker(self.sp_pxFreq):
            self.sp_pxFreq.setValue(float(val("pxModFreq")))
        with QtCore.QSignalBlocker(self.sp_pxPhase):
            self.sp_pxPhase.setValue(float(val("pxModPhaseDeg")))

        self.sync_enabled(emit=False)
        self._sync_subprofile_state()

    def _sync_subprofile_state(self):
        if hasattr(self, "_subprofile_panel") and self._subprofile_panel is not None:
            self._subprofile_panel.sync_from_data(self.collect())

    def pick_color(self):
        c = open_color_dialog(self, QtGui.QColor(self.ed_color.text().strip() or "#00C8FF"), "Couleur")
        if c.isValid():
            self.ed_color.setText(c.name())
            self.emit_delta()

    # --- Couleurs multiples -------------------------------------------------

    def parse_color_stops(self):
        stops = []
        for chunk in self.ed_colors.text().split(','):
            chunk = chunk.strip()
            if not chunk:
                continue
            if '@' in chunk:
                color, pos = chunk.split('@', 1)
            else:
                color, pos = chunk, ''
            color = color.strip() or '#000000'
            try:
                pos_val = float(pos.strip()) if pos.strip() else 0.0
            except ValueError:
                pos_val = 0.0
            stops.append((color, max(0.0, min(1.0, pos_val))))
        return stops

    def format_color_stops(self, stops):
        parts = []
        for color, pos in stops:
            color = color if color.startswith('#') else QtGui.QColor(color).name()
            parts.append(f"{color}@{pos:g}")
        return ','.join(parts)

    def pick_colors(self):
        dlg = ColorListDialog(self.parse_color_stops(), self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self.ed_colors.setText(self.format_color_stops(dlg.stops()))
            self.emit_delta()


class ColorListDialog(QtWidgets.QDialog):
    def __init__(self, stops=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Liste de couleurs")
        self.resize(420, 280)

        self.setStyleSheet("""
            QDialog, QWidget {
                color: #15151f;
                background-color: #ffffff;
            }
            QHeaderView::section {
                background-color: #f0f0f5;
                color: #15151f;
            }
            QTableWidget {
                background-color: #ffffff;
                alternate-background-color: #f7f7fb;
                gridline-color: rgba(0, 0, 0, 0.15);
            }
            QLineEdit, QSpinBox, QDoubleSpinBox, QAbstractSpinBox {
                color: #15151f;
                background-color: #ffffff;
            }
            QPushButton {
                color: #000000;
            }
        """)

        layout = QtWidgets.QVBoxLayout(self)
        self.table = QtWidgets.QTableWidget(0, 2, self)
        self.table.setHorizontalHeaderLabels(["Couleur", "Position"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.cellDoubleClicked.connect(self.edit_color_cell)
        layout.addWidget(self.table)

        btn_layout = QtWidgets.QHBoxLayout()
        self.bt_add = QtWidgets.QPushButton("Ajouter")
        self.bt_remove = QtWidgets.QPushButton("Supprimer")
        btn_layout.addWidget(self.bt_add)
        btn_layout.addWidget(self.bt_remove)
        btn_layout.addStretch(1)
        layout.addLayout(btn_layout)

        self.bt_add.clicked.connect(self._on_add_clicked)
        self.bt_remove.clicked.connect(self.remove_selected)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        for color, pos in stops or []:
            self.add_row(color, pos)
        if self.table.rowCount() == 0:
            self.add_row()

    # -- table helpers ------------------------------------------------------

    def _on_add_clicked(self, checked=False):
        # ``clicked`` emits a boolean, swallow it so ``add_row`` always uses defaults.
        self.add_row()

    def add_row(self, color="#FFFFFF", pos=0.0):
        color = self._normalize_color_value(color)
        row = self.table.rowCount()
        self.table.insertRow(row)
        item = QtWidgets.QTableWidgetItem(color)
        item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
        self.table.setItem(row, 0, item)
        self._update_color_item(item, color)

        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(0.0, 1.0)
        spin.setSingleStep(0.05)
        spin.setDecimals(3)
        spin.setValue(pos)
        self.table.setCellWidget(row, 1, spin)
        self.table.setCurrentCell(row, 0)

    def remove_selected(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
        if self.table.rowCount() == 0:
            self.add_row()

    def edit_color_cell(self, row, column):
        if column != 0:
            return
        item = self.table.item(row, 0)
        current = QtGui.QColor(item.text() or '#FFFFFF')
        color = open_color_dialog(self, current, "Choisir une couleur")
        if color.isValid():
            self._update_color_item(item, color.name())

    def _update_color_item(self, item, value):
        value = self._normalize_color_value(value)
        item.setText(value)
        item.setData(QtCore.Qt.UserRole, value)
        color = QtGui.QColor(value)
        if color.isValid():
            item.setBackground(QtGui.QBrush(color))
            brightness = QtGui.QColor(255, 255, 255) if color.lightness() < 128 else QtGui.QColor(0, 0, 0)
            item.setForeground(QtGui.QBrush(brightness))
        else:
            item.setBackground(QtGui.QBrush())
            item.setForeground(QtGui.QBrush())

    def stops(self):
        data = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            color = item.data(QtCore.Qt.UserRole) or item.text()
            spin = self.table.cellWidget(row, 1)
            pos = spin.value() if isinstance(spin, QtWidgets.QDoubleSpinBox) else 0.0
            data.append((color, pos))
        return data

    def _normalize_color_value(self, value):
        if isinstance(value, QtGui.QColor):
            value = value.name()
        if not isinstance(value, str):
            value = "#FFFFFF"
        value = value.strip() or "#FFFFFF"
        if not QtGui.QColor(value).isValid():
            value = "#FFFFFF"
        return value
