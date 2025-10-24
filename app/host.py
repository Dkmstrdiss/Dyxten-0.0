from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

class Host(QObject):
    # Utiliser QVariant côté QtWebChannel
    stateChanged = pyqtSignal('QVariant')

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = {
            "rotationSpeed": 0.0,
            "pulse": 0.0,
        }

    @pyqtSlot(result='QVariant')
    def getState(self):
        # Retourner un dict Python -> QVariant automatiquement
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
