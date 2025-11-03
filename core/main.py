# -*- coding: utf-8 -*-
import io
import math
import sys
from pathlib import Path
from typing import cast
from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QSurfaceFormat

# --- autorise l'exécution directe ---
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class _DebugSilencer(io.TextIOBase):
    """Stream wrapper filtering the verbose engine diagnostics."""

    def __init__(self, stream: io.TextIOBase, marker: str) -> None:
        super().__init__()
        self._stream = stream
        self._marker = marker
        self._buffer: str = ""

    def write(self, text: str) -> int:  # type: ignore[override]
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self._emit(line + "\n")
        return len(text)

    def flush(self) -> None:  # type: ignore[override]
        if self._buffer:
            self._emit(self._buffer)
            self._buffer = ""
        self._stream.flush()

    def _emit(self, chunk: str) -> None:
        if self._marker not in chunk:
            self._stream.write(chunk)

    def writelines(self, lines) -> None:  # type: ignore[override]
        for line in lines:
            self.write(line)

    def close(self) -> None:  # type: ignore[override]
        self.flush()
        super().close()

    def __getattr__(self, name):
        return getattr(self._stream, name)


def _install_debug_silencer(marker: str = "[Dyxten][DEBUG]") -> None:
    if marker and not isinstance(sys.stdout, _DebugSilencer):
        sys.stdout = _DebugSilencer(sys.stdout, marker)
    if marker and not isinstance(sys.stderr, _DebugSilencer):
        sys.stderr = _DebugSilencer(sys.stderr, marker)


_install_debug_silencer()

try:
    from .control.control_window import ControlWindow  # exécution via -m
except ImportError:
    from core.control.control_window import ControlWindow  # exécution directe

try:
    from .view import DyxtenViewWidget  # type: ignore
except ImportError:  # pragma: no cover
    from core.view import DyxtenViewWidget  # type: ignore

try:
    from .donut import default_donut_config, sanitize_donut_state
except ImportError:  # pragma: no cover
    from core.donut import default_donut_config, sanitize_donut_state

fmt = QSurfaceFormat()
fmt.setAlphaBufferSize(8)
QSurfaceFormat.setDefaultFormat(fmt)


def _fail_fast_verify():
    import core.control.control_window as cw
    path = Path(cw.__file__).resolve()
    if not hasattr(cw, "ControlWindow"):
        raise SystemExit("FATAL: ControlWindow introuvable dans control_window.py")
    txt = path.read_text(encoding="utf-8", errors="ignore")
    if "Dyxten — Control v2" not in txt or "QStatusBar" not in txt or "ApplicationShortcut" not in txt:
        raise SystemExit("FATAL: Mauvaise version de control_window.py chargée (pas v2).")


class ViewWindow(QtWidgets.QMainWindow):
    def __init__(self, screen: QtGui.QScreen):
        super().__init__(None)
        self._target_screen = screen
        self.view = DyxtenViewWidget(self)

        w = QtWidgets.QWidget()
        w.setAttribute(Qt.WA_NoSystemBackground, True)
        w.setAutoFillBackground(False)
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.view)
        self.setCentralWidget(w)

        self._button_layer = QtWidgets.QWidget(self.view)
        self._button_layer.setAttribute(Qt.WA_NoSystemBackground, True)
        self._button_layer.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self._button_layer.setAttribute(Qt.WA_TranslucentBackground, True)
        self._button_layer.setAutoFillBackground(False)
        self._button_layer.setGeometry(self.view.rect())
        self._button_layer.raise_()
        self._button_layer.installEventFilter(self)
        self._donut_buttons: list[QtWidgets.QPushButton] = []
        self._donut_config = default_donut_config()
        self._donut_angle_offset = 0.0
        self._scroll_step_radians = math.radians(12.0)
        self.update_donut_buttons(self._donut_config)

        self.view.installEventFilter(self)
        self._sync_button_overlay()

        self._apply_screen_geometry(screen)
        QtWidgets.QShortcut(Qt.Key_Escape, self, activated=self.close)
        self._transparent = None
        QtCore.QTimer.singleShot(0, lambda: self.set_transparent(True))

    def _apply_screen_geometry(self, screen: QtGui.QScreen):
        if window_handle := self.windowHandle():
            window_handle.setScreen(screen)
        geometry = screen.geometry()
        width = int(geometry.width() * 0.8)
        height = int(geometry.height() * 0.8)
        left = geometry.left() + (geometry.width() - width) // 2
        top = geometry.top() + (geometry.height() - height) // 2
        self.setGeometry(left, top, width, height)

    def showEvent(self, event: QtGui.QShowEvent):
        self._apply_screen_geometry(self._target_screen)
        super().showEvent(event)

    def set_transparent(self, enabled: bool):
        enabled = bool(enabled)
        if self._transparent == enabled:
            return
        self._transparent = enabled
        bg_style = "background: transparent;" if enabled else ""
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, enabled)
        self.setAttribute(Qt.WA_TranslucentBackground, enabled)
        self.setStyleSheet(bg_style)
        central = self.centralWidget()
        if central is not None:
            central.setAttribute(Qt.WA_StyledBackground, True)
            central.setAutoFillBackground(not enabled)
            central.setAttribute(Qt.WA_NoSystemBackground, enabled)
            central.setAttribute(Qt.WA_TranslucentBackground, enabled)
            central.setStyleSheet(bg_style)
        if self._button_layer is not None:
            self._button_layer.setAttribute(Qt.WA_NoSystemBackground, True)
            self._button_layer.setAttribute(Qt.WA_TranslucentBackground, True)
            self._button_layer.setAutoFillBackground(False)
            self._button_layer.setStyleSheet("background: transparent;")
        self.view.setAttribute(Qt.WA_StyledBackground, True)
        self.view.setAttribute(Qt.WA_NoSystemBackground, enabled)
        self.view.setAttribute(Qt.WA_TranslucentBackground, enabled)
        self.view.setStyleSheet(bg_style)
        try:
            self.view.set_transparent(enabled)
        except Exception:
            pass
        self.view.update()
        self.update()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._sync_button_overlay()

    def update_donut_buttons(self, donut: dict) -> None:
        self._donut_config = sanitize_donut_state(donut)
        descriptors = self._donut_config.get("buttons", [])
        if len(self._donut_buttons) != len(descriptors):
            for btn in self._donut_buttons:
                btn.deleteLater()
            self._donut_buttons = []
            for descriptor in descriptors:
                button = QtWidgets.QPushButton(self._button_layer)
                button.setFixedSize(56, 56)
                button.setStyleSheet(
                    """
                    QPushButton {
                        border-radius: 28px;
                        border: 1px solid rgba(255,255,255,0.3);
                        background: rgba(12,18,27,0.65);
                        color: #f5f6ff;
                        font-family: 'Segoe UI', sans-serif;
                        font-size: 13px;
                        font-weight: 600;
                        letter-spacing: 0.04em;
                        text-transform: uppercase;
                        padding: 4px 10px;
                    }
                    QPushButton:hover { background: rgba(0,200,255,0.65); border-color: rgba(0,200,255,0.85); }
                    QPushButton:pressed { background: rgba(0,140,200,0.85); }
                    """
                )
                button.installEventFilter(self)
                button.show()
                self._donut_buttons.append(button)
        for idx, (button, descriptor) in enumerate(zip(self._donut_buttons, descriptors)):
            if isinstance(descriptor, dict):
                label = descriptor.get("label")
                ident = descriptor.get("id")
            else:
                label = None
                ident = None
            button.setText((label or f"Bouton {idx + 1}").strip())
            button.setProperty("buttonId", ident if isinstance(ident, int) else idx + 1)
        self._sync_button_overlay()

    def _marker_radii_for_view(self) -> tuple[float, float, float]:
        rect = self.view.rect()
        width = rect.width()
        height = rect.height()
        if width <= 0 or height <= 0:
            return 0.0, 0.0, 0.0
        base_area = (width * height) / 3.0
        base_radius = math.sqrt(max(base_area, 0.0) / math.pi)
        radius_red = base_radius * 0.5
        radius_yellow = radius_red * 1.15
        radius_blue = radius_yellow * 1.10
        max_radius = min(width, height) / 2.0
        radius_red = min(radius_red, max_radius)
        radius_yellow = min(radius_yellow, max_radius)
        radius_blue = min(radius_blue, max_radius)
        return radius_red, radius_yellow, radius_blue

    def _layout_buttons(self) -> None:
        if not self._donut_buttons:
            return
        rect = self.view.rect()
        width = rect.width()
        height = rect.height()
        if width <= 0 or height <= 0:
            return
        _, _, radius = self._marker_radii_for_view()
        if radius <= 0:
            return
        cx = width / 2
        cy = height / 2
        count = len(self._donut_buttons)
        if count <= 0:
            return
        step = (2 * math.pi) / count
        self._donut_angle_offset = self._donut_angle_offset % (2 * math.pi)
        base_angle = (-math.pi / 2) + self._donut_angle_offset
        for index, button in enumerate(self._donut_buttons):
            angle = base_angle + index * step
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            button.move(int(x - button.width() / 2), int(y - button.height() / 2))

    def _sync_button_overlay(self) -> None:
        if self._button_layer is None:
            return
        self._button_layer.setGeometry(self.view.rect())
        self._layout_buttons()

    def _handle_donut_wheel(self, event: QtGui.QWheelEvent) -> bool:
        if not self._donut_buttons:
            return False
        angle_delta = event.angleDelta()
        steps = angle_delta.y()
        if steps == 0:
            steps = angle_delta.x()
        if steps == 0:
            return False
        rotation = (steps / 120.0) * self._scroll_step_radians
        if rotation == 0.0:
            return False
        self._donut_angle_offset = (self._donut_angle_offset + rotation) % (2 * math.pi)
        self._layout_buttons()
        event.accept()
        return True

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if event.type() == QtCore.QEvent.Wheel:
            wheel_event = cast(QtGui.QWheelEvent, event)
            if watched is self.view or watched is self._button_layer or watched in self._donut_buttons:
                if self._handle_donut_wheel(wheel_event):
                    return True
        if watched is self.view and event.type() == QtCore.QEvent.Resize:
            self._sync_button_overlay()
        return super().eventFilter(watched, event)


def main():
    _fail_fast_verify()
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication(sys.argv)
    screens = QtGui.QGuiApplication.screens()
    primary = QtGui.QGuiApplication.primaryScreen()
    second = screens[1] if len(screens) > 1 else primary
    view_win = ViewWindow(second)
    view_win.show()
    _ = ControlWindow(app, second, view_win)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
