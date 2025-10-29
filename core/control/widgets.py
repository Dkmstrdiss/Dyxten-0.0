
from PyQt5 import QtWidgets, QtCore, QtGui


SUBPROFILE_HEADER_ROLE = QtCore.Qt.UserRole + 1


class SubProfileItemDelegate(QtWidgets.QStyledItemDelegate):
    """Draw category headers and indent entries without breaking combo display."""

    def __init__(self, *, indent: int = 12, parent=None):
        super().__init__(parent)
        self._indent = indent

    def paint(self, painter, option, index):
        is_header = bool(index.data(SUBPROFILE_HEADER_ROLE))
        opt = QtWidgets.QStyleOptionViewItem(option)
        if not is_header and index.data(QtCore.Qt.UserRole) is not None:
            if isinstance(option.widget, QtWidgets.QListView):
                opt.rect = opt.rect.adjusted(self._indent, 0, 0, 0)
        super().paint(painter, opt, index)

    def sizeHint(self, option, index):
        hint = super().sizeHint(option, index)
        if bool(index.data(SUBPROFILE_HEADER_ROLE)):
            return hint
        if index.data(QtCore.Qt.UserRole) is not None and isinstance(option.widget, QtWidgets.QListView):
            return QtCore.QSize(hint.width() + self._indent, hint.height())
        return hint


class SubProfilePanel(QtWidgets.QFrame):
    """Common toolbar used to manage per-tab sub profiles."""

    def __init__(self, title: str):
        super().__init__()
        self.setObjectName("SubProfilePanel")
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self._manager = None
        self._section = ""
        self._collect_cb = None
        self._apply_cb = None
        self._on_change = None
        self._applying = False
        self._active_name = None

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        label = QtWidgets.QLabel(title)
        label.setObjectName("SubProfileLabel")
        layout.addWidget(label)

        self.combo = QtWidgets.QComboBox()
        self.combo.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.combo.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.combo.setMinimumWidth(260)
        self.combo.setModel(QtGui.QStandardItemModel(self.combo))
        self.combo.setView(QtWidgets.QListView())
        self.combo.view().setSpacing(2)
        delegate = SubProfileItemDelegate(parent=self.combo)
        self.combo.setItemDelegate(delegate)
        self.combo.view().setItemDelegate(delegate)
        self._header_font = QtGui.QFont(self.font())
        self._header_font.setBold(True)
        self._header_brush = QtGui.QBrush(QtGui.QColor(76, 94, 111))
        self._header_background = QtGui.QBrush(QtGui.QColor(238, 242, 247))
        self._populate_combo_header()
        self.combo.currentIndexChanged.connect(self._on_select)
        layout.addWidget(self.combo, 1)

        self.btn_menu = QtWidgets.QToolButton()
        self.btn_menu.setObjectName("SubProfileMenuButton")
        self.btn_menu.setText("⋯")
        self.btn_menu.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_menu.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        layout.addWidget(self.btn_menu)

        menu = QtWidgets.QMenu(self)
        self.act_save = menu.addAction("Sauver le sous-profil", self._on_save)
        self.act_save_as = menu.addAction("Créer un nouveau…", self._on_save_as)
        self.act_rename = menu.addAction("Renommer…", self._on_rename)
        self.act_delete = menu.addAction("Supprimer", self._on_delete)
        self.btn_menu.setMenu(menu)

        self.setStyleSheet("""
            QFrame#SubProfilePanel {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f9fbfe, stop:1 #edf3fb);
                border: 1px solid #d7e4f3;
                border-radius: 5px;
                min-height: 52px;
            }
            QLabel#SubProfileLabel {
                color: #204060;
                font-weight: 600;
            }
            QComboBox {
                min-height: 28px;
                padding-left: 6px;
            }
            QToolButton#SubProfileMenuButton {
                width: 28px;
                border-radius: 14px;
                border: 1px solid #7aa7c7;
                background: #e6f2fb;
                color: #0f0f0f;
                font-weight: 700;
            }
            QToolButton#SubProfileMenuButton:hover {
                background: #d8ecfa;
                color: #000000;
            }
        """)

        self._update_buttons()

    # ------------------------------------------------------------------ API
    def bind(self, *, manager, section: str, defaults: dict, collect_cb, apply_cb, on_change):
        self._manager = manager
        self._section = section
        self._collect_cb = collect_cb
        self._apply_cb = apply_cb
        self._on_change = on_change
        if manager is not None:
            manager.ensure_section(section, defaults)
        self.refresh()

    HEADER_ROLE = SUBPROFILE_HEADER_ROLE

    def _populate_combo_header(self) -> None:
        model: QtGui.QStandardItemModel = self.combo.model()  # type: ignore[assignment]
        model.clear()
        custom = QtGui.QStandardItem("— Personnalisé —")
        custom.setData(None, QtCore.Qt.UserRole)
        custom.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
        model.appendRow(custom)

    def _append_category(self, label: str, names):
        if not names:
            return
        model: QtGui.QStandardItemModel = self.combo.model()  # type: ignore[assignment]
        header = QtGui.QStandardItem(label)
        header.setFlags(QtCore.Qt.NoItemFlags)
        header.setData(True, self.HEADER_ROLE)
        header.setFont(self._header_font)
        header.setForeground(self._header_brush)
        header.setBackground(self._header_background)
        model.appendRow(header)
        for name in names:
            item = QtGui.QStandardItem(name)
            item.setEditable(False)
            item.setData(name, QtCore.Qt.UserRole)
            model.appendRow(item)

    def refresh(self, select=None):
        current = select or self.combo.currentData(QtCore.Qt.UserRole)
        with QtCore.QSignalBlocker(self.combo):
            self._populate_combo_header()
            if self._manager is not None:
                groups = self._manager.list_grouped(self._section)
                for label, names in groups:
                    self._append_category(label, names)
            target_index = 0
            model: QtGui.QStandardItemModel = self.combo.model()  # type: ignore[assignment]
            for row in range(model.rowCount()):
                item = model.item(row)
                if not item:
                    continue
                if item.data(self.HEADER_ROLE):
                    continue
                if item.data(QtCore.Qt.UserRole) == current:
                    target_index = row
                    break
            self.combo.setCurrentIndex(target_index)
        data = self.combo.currentData()
        self._active_name = data if isinstance(data, str) else None
        self._update_buttons()

    def sync_from_data(self, payload: dict):
        if self._manager is None:
            return
        match = self._manager.find_match(self._section, payload)
        with QtCore.QSignalBlocker(self.combo):
            if match:
                index = self.combo.findData(match)
                if index != -1:
                    self.combo.setCurrentIndex(index)
                    self._active_name = match
                    self._update_buttons()
                    return
            self.combo.setCurrentIndex(0)
            self._active_name = None
        self._update_buttons()

    # ---------------------------------------------------------------- events
    def _on_select(self, index: int):
        if self._applying:
            return
        name = self.combo.itemData(index)
        self._active_name = name if isinstance(name, str) else None
        self._update_buttons()
        if self._manager is None or self._apply_cb is None or not isinstance(name, str):
            return
        payload = self._manager.get(self._section, name)
        self._applying = True
        try:
            self._apply_cb(payload)
        finally:
            self._applying = False
        if callable(self._on_change):
            self._on_change()
        if callable(self._collect_cb):
            self.sync_from_data(self._collect_cb())

    def _on_save(self):
        if self._manager is None or self._collect_cb is None:
            return
        target = self._active_name
        if not target:
            self._on_save_as()
            return
        payload = self._collect_cb()
        try:
            self._manager.save(self._section, target, payload)
        except Exception as exc:  # pragma: no cover - feedback utilisateur
            QtWidgets.QMessageBox.warning(self, "Erreur", str(exc))
            return
        self.refresh(select=target)

    def _on_save_as(self):
        if self._manager is None or self._collect_cb is None:
            return
        name, ok = QtWidgets.QInputDialog.getText(
            self,
            "Nouveau sous-profil",
            "Nom du sous-profil :",
            text=self._active_name or "",
        )
        if not ok:
            return
        name = name.strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Nom invalide", "Veuillez saisir un nom valide.")
            return
        payload = self._collect_cb()
        try:
            self._manager.save(self._section, name, payload)
        except Exception as exc:  # pragma: no cover - feedback utilisateur
            QtWidgets.QMessageBox.warning(self, "Erreur", str(exc))
            return
        self.refresh(select=name)

    def _on_rename(self):
        if self._manager is None or not self._active_name:
            return
        if self._active_name == self._manager.DEFAULT_NAME:
            QtWidgets.QMessageBox.information(
                self,
                "Action impossible",
                "Le sous-profil par défaut ne peut pas être renommé.",
            )
            return
        name, ok = QtWidgets.QInputDialog.getText(
            self,
            "Renommer le sous-profil",
            "Nouveau nom :",
            text=self._active_name,
        )
        if not ok:
            return
        name = name.strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Nom invalide", "Veuillez saisir un nom valide.")
            return
        try:
            self._manager.rename(self._section, self._active_name, name)
        except Exception as exc:  # pragma: no cover - feedback utilisateur
            QtWidgets.QMessageBox.warning(self, "Erreur", str(exc))
            return
        self.refresh(select=name)

    def _on_delete(self):
        if self._manager is None or not self._active_name:
            return
        if self._active_name == self._manager.DEFAULT_NAME:
            QtWidgets.QMessageBox.information(
                self,
                "Action impossible",
                "Le sous-profil par défaut ne peut pas être supprimé.",
            )
            return
        response = QtWidgets.QMessageBox.question(
            self,
            "Supprimer le sous-profil",
            f"Supprimer '{self._active_name}' ?",
        )
        if response != QtWidgets.QMessageBox.Yes:
            return
        try:
            self._manager.delete(self._section, self._active_name)
        except Exception as exc:  # pragma: no cover - feedback utilisateur
            QtWidgets.QMessageBox.warning(self, "Erreur", str(exc))
            return
        self.refresh(select=None)

    def _update_buttons(self):
        has_selection = bool(self._active_name)
        can_edit = has_selection and self._manager is not None and self._active_name != getattr(self._manager, "DEFAULT_NAME", "")
        has_manager = self._manager is not None
        if self.btn_menu.menu() is not None:
            self.act_save.setEnabled(has_manager)
            self.act_save_as.setEnabled(has_manager)
            self.act_rename.setEnabled(can_edit)
            self.act_delete.setEnabled(can_edit)
        self.btn_menu.setEnabled(has_manager)


def mk_info(text: str) -> QtWidgets.QToolButton:
    b = QtWidgets.QToolButton(); b.setText("i"); b.setCursor(QtCore.Qt.PointingHandCursor)
    b.setToolTipDuration(0); b.setToolTip(text); b.setFixedSize(20,20)
    b.setStyleSheet("QToolButton{border:1px solid #7aa7c7;border-radius:10px;font-weight:bold;padding:0;color:#2b6ea8;background:#e6f2fb;}QToolButton:hover{background:#d8ecfa;}")
    return b

def mk_reset(cb) -> QtWidgets.QToolButton:
    b = QtWidgets.QToolButton(); b.setText("↺"); b.setCursor(QtCore.Qt.PointingHandCursor)
    b.setToolTip("Réinitialiser"); b.setFixedSize(22,22)
    b.setStyleSheet("QToolButton{border:1px solid #9aa5b1;border-radius:11px;padding:0;background:#f2f4f7;color:#2b2b2b;font-weight:bold;}QToolButton:hover{background:#e9edf2;}")
    b.clicked.connect(lambda checked=False, _cb=cb: _cb())
    return b

def row(form: QtWidgets.QFormLayout, label: str, widget: QtWidgets.QWidget, tip: str, reset_cb=None):
    h = QtWidgets.QHBoxLayout(); h.setContentsMargins(0,0,0,0); h.setSpacing(6)
    h.addWidget(widget, 1)
    if reset_cb: h.addWidget(mk_reset(reset_cb), 0)
    h.addWidget(mk_info(tip), 0)
    w = QtWidgets.QWidget(); w.setLayout(h)
    lbl = QtWidgets.QLabel(label)
    lbl.setObjectName("FormLabel")
    form.addRow(lbl, w)
    w._form_label = lbl  # type: ignore[attr-defined]
    try:
        widget.setProperty("dyxten_form_label", label)
    except Exception:
        pass
    return w

def vec_row(spins):
    h = QtWidgets.QHBoxLayout(); h.setContentsMargins(0,0,0,0); h.setSpacing(6)
    for s in spins: h.addWidget(s)
    w = QtWidgets.QWidget(); w.setLayout(h); return w


class SliderWithMax(QtWidgets.QWidget):
    valueChanged = QtCore.pyqtSignal(float)
    maxChanged = QtCore.pyqtSignal(float)

    def __init__(self, value: float = 0.0, max_value: float = 360.0, decimals: int = 1):
        super().__init__()
        self._decimals = max(0, int(decimals))
        self._resolution = 10 ** self._decimals or 1

        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setTracking(True)

        self.value_spin = QtWidgets.QDoubleSpinBox()
        self.value_spin.setDecimals(self._decimals)
        self.value_spin.setSingleStep(1 / self._resolution)

        self.max_spin = QtWidgets.QDoubleSpinBox()
        self.max_spin.setDecimals(self._decimals)
        self.max_spin.setSingleStep(1.0)
        self.max_spin.setRange(1.0, 2000.0)

        max_box = QtWidgets.QHBoxLayout()
        max_box.setContentsMargins(0, 0, 0, 0)
        max_box.setSpacing(4)
        lbl = QtWidgets.QLabel("Max")
        lbl.setObjectName("SliderMaxLabel")
        max_box.addWidget(lbl)
        max_box.addWidget(self.max_spin)
        max_widget = QtWidgets.QWidget()
        max_widget.setLayout(max_box)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.value_spin)
        layout.addWidget(max_widget)

        self.max_spin.valueChanged.connect(self._on_max_changed)
        self.slider.valueChanged.connect(self._on_slider_changed)
        self.value_spin.valueChanged.connect(self._on_spin_changed)

        self.setMaximum(max_value)
        self.setValue(value)

    def _on_max_changed(self, new_max: float):
        limit = max(1 / self._resolution, float(new_max))
        self._apply_limit(limit)
        self.maxChanged.emit(limit)

    def _on_slider_changed(self, raw: int):
        value = raw / self._resolution
        with QtCore.QSignalBlocker(self.value_spin):
            self.value_spin.setValue(value)
        self.valueChanged.emit(value)

    def _on_spin_changed(self, value: float):
        limit = self.maximum()
        clamped = max(-limit, min(limit, value))
        if clamped != value:
            with QtCore.QSignalBlocker(self.value_spin):
                self.value_spin.setValue(clamped)
        with QtCore.QSignalBlocker(self.slider):
            self.slider.setValue(int(round(clamped * self._resolution)))
        self.valueChanged.emit(clamped)

    def _apply_limit(self, limit: float):
        limit = max(1 / self._resolution, float(limit))
        with QtCore.QSignalBlocker(self.max_spin):
            self.max_spin.setValue(limit)
        self.value_spin.setRange(-limit, limit)
        with QtCore.QSignalBlocker(self.slider):
            span = int(round(limit * self._resolution))
            self.slider.setRange(-span, span)
            current = max(-span, min(span, self.slider.value()))
            self.slider.setValue(current)
        with QtCore.QSignalBlocker(self.value_spin):
            current_value = self.slider.value() / self._resolution
            self.value_spin.setValue(current_value)

    def setMaximum(self, limit: float):
        self._apply_limit(limit)

    def maximum(self) -> float:
        return float(self.max_spin.value())

    def setValue(self, value: float):
        limit = self.maximum()
        clamped = max(-limit, min(limit, float(value)))
        with QtCore.QSignalBlocker(self.value_spin):
            self.value_spin.setValue(clamped)
        with QtCore.QSignalBlocker(self.slider):
            self.slider.setValue(int(round(clamped * self._resolution)))

    def value(self) -> float:
        return float(self.value_spin.value())
