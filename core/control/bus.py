
from PyQt5 import QtCore

class Bus(QtCore.QObject):
    changed = QtCore.pyqtSignal(dict)
