
from PyQt5 import QtWidgets, QtCore

def mk_info(text: str) -> QtWidgets.QToolButton:
    b = QtWidgets.QToolButton(); b.setText("i"); b.setCursor(QtCore.Qt.PointingHandCursor)
    b.setToolTipDuration(0); b.setToolTip(text); b.setFixedSize(20,20)
    b.setStyleSheet("QToolButton{border:1px solid #7aa7c7;border-radius:10px;font-weight:bold;padding:0;color:#2b6ea8;background:#e6f2fb;}QToolButton:hover{background:#d8ecfa;}")
    return b

def mk_reset(cb) -> QtWidgets.QToolButton:
    b = QtWidgets.QToolButton(); b.setText("↺"); b.setCursor(QtCore.Qt.PointingHandCursor)
    b.setToolTip("Réinitialiser"); b.setFixedSize(22,22)
    b.setStyleSheet("QToolButton{border:1px solid #9aa5b1;border-radius:11px;padding:0;background:#f2f4f7;color:#2b2b2b;font-weight:bold;}QToolButton:hover{background:#e9edf2;}")
    b.clicked.connect(cb); return b

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
    return w

def vec_row(spins):
    h = QtWidgets.QHBoxLayout(); h.setContentsMargins(0,0,0,0); h.setSpacing(6)
    for s in spins: h.addWidget(s)
    w = QtWidgets.QWidget(); w.setLayout(h); return w
