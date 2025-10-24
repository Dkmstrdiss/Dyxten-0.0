from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

class Host(QObject):
    stateChanged = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = {
            "rotationSpeed": 0.0,
            "pulse": 0.0,
        }

    @pyqtSlot(result=dict)
    def getState(self):
        return dict(self._state)

    @pyqtSlot(str, float)
    def setParam(self, key, value):
        if key in self._state:
            self._state[key] = float(value)
            self.stateChanged.emit(dict(self._state))

    @pyqtSlot()
    def reset(self):
        self._state["rotationSpeed"] = 0.0
        self._state["pulse"] = 0.0
        self.stateChanged.emit(dict(self._state))
