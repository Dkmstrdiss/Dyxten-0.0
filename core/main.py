# -*- coding: utf-8 -*-
import io
import math
import sys
from pathlib import Path
from typing import NoReturn, cast


def _handle_qt_import_error(exc: ImportError) -> NoReturn:
    """Exit with a helpful message when the Qt bindings cannot be imported."""

    details = str(exc)
    message_lines = [
        "Impossible de lancer Dyxten : l'import de PyQt5 a échoué.",
        "Vérifiez que PyQt5 est installé et que les bibliothèques OpenGL requises sont disponibles.",
    ]
    if "libGL.so.1" in details:
        message_lines.append(
            "Indice : la bibliothèque système libGL.so.1 est manquante. Installez les paquets Mesa/OpenGL appropriés."
        )
    message_lines.append(f"Erreur d'origine : {details}")
    raise SystemExit("\n".join(message_lines)) from exc


try:
    from PyQt5 import QtCore, QtWidgets, QtGui
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QSurfaceFormat
except ImportError as exc:  # pragma: no cover - dépendances environnementales
    _handle_qt_import_error(exc)

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
    from .donut_hub import default_donut_config, sanitize_donut_state
except ImportError:  # pragma: no cover
    from core.donut_hub import default_donut_config, sanitize_donut_state

try:
    from .donut_hub import DonutHub
except ImportError:  # pragma: no cover
    from core.donut_hub import DonutHub

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
        self._external_layout = False  # when True, don't auto-center/resize on show
        self.view = DyxtenViewWidget(self)

        w = QtWidgets.QWidget()
        w.setAttribute(Qt.WA_NoSystemBackground, True)
        w.setAutoFillBackground(False)
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.view)
        self.setCentralWidget(w)

        # Overlay: use DonutHub as the host for donut buttons. DonutHub will
        # emit layouts that we forward to the view's renderer.
        try:
            self.donut_hub = DonutHub(parent=self.view)
            self.donut_hub.setAttribute(Qt.WA_NoSystemBackground, True)
            self.donut_hub.setAttribute(Qt.WA_TranslucentBackground, True)
            self.donut_hub.setAutoFillBackground(False)
            self.donut_hub.setGeometry(self.view.rect())
            self.donut_hub.raise_()
        except Exception:
            self.donut_hub = None

        self._donut_angle_offset = 0.0
        self._scroll_step_radians = math.radians(12.0)

        # Connect layout updates from DonutHub to the renderer
        if self.donut_hub is not None:
            try:
                self.donut_hub.donutLayoutChanged.connect(
                    lambda centers, radii: self.view.update_donut_layout(centers, width=int(self.view.width()), height=int(self.view.height()), radii=radii)
                )
                # initialize buttons from default config
                try:
                    self.donut_hub.update_donut_buttons(default_donut_config())
                except Exception:
                    pass
            except Exception:
                pass

        # Keep listening to view resize/wheel events
        self.view.installEventFilter(self)

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
        # Respect external layout requests (e.g., side-by-side tiling)
        if not getattr(self, "_external_layout", False):
            self._apply_screen_geometry(self._target_screen)
        super().showEvent(event)

    def set_external_layout(self, enabled: bool) -> None:
        self._external_layout = bool(enabled)

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
        if getattr(self, "donut_hub", None) is not None:
            try:
                self.donut_hub.setAttribute(Qt.WA_NoSystemBackground, True)
                self.donut_hub.setAttribute(Qt.WA_TranslucentBackground, True)
                self.donut_hub.setAutoFillBackground(False)
                self.donut_hub.setStyleSheet("background: transparent;")
            except Exception:
                pass
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
        # Delegate to DonutHub when available; otherwise keep the state.
        if getattr(self, "donut_hub", None) is not None:
            try:
                self.donut_hub.update_donut_buttons(donut)
            except Exception:
                pass
        else:
            # fallback: store sanitized config
            try:
                self._donut_config = sanitize_donut_state(donut)
            except Exception:
                self._donut_config = default_donut_config()

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
        # Delegate layout to DonutHub (if present). Otherwise no-op.
        if getattr(self, "donut_hub", None) is None:
            return
        try:
            # ensure hub geometry matches the view and let it position buttons
            self.donut_hub.setGeometry(self.view.rect())
            # request a layout update from the DonutHub (public API)
            try:
                self.donut_hub.request_layout_update()
            except Exception:
                try:
                    # fallback to private in case older hub doesn't expose the public method
                    self.donut_hub._position_all()
                except Exception:
                    pass
        except Exception:
            pass

    def _sync_button_overlay(self) -> None:
        if getattr(self, "donut_hub", None) is None:
            return
        try:
            self.donut_hub.setGeometry(self.view.rect())
            try:
                self.donut_hub.request_layout_update()
            except Exception:
                try:
                    self.donut_hub._position_all()
                except Exception:
                    pass
        except Exception:
            pass

    def _handle_donut_wheel(self, event: QtGui.QWheelEvent) -> bool:
        if getattr(self, "donut_hub", None) is None:
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
        # rotation is in radians; convert to degrees for DonutHub
        deg = math.degrees(rotation)
        self._donut_angle_offset = (self._donut_angle_offset + deg) % 360.0
        try:
            self.donut_hub.set_angle_offset(self._donut_angle_offset)
        except Exception:
            pass
        event.accept()
        return True

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if event.type() == QtCore.QEvent.Wheel:
            wheel_event = cast(QtGui.QWheelEvent, event)
            if watched is self.view or watched is getattr(self, "donut_hub", None):
                if self._handle_donut_wheel(wheel_event):
                    return True
        if watched is self.view and event.type() == QtCore.QEvent.Resize:
            self._sync_button_overlay()
        return super().eventFilter(watched, event)


def main(headless: bool = False) -> int:
    """Start the application and return the exit code.

    When ``headless`` is True the function will perform minimal verification
    and return 0 without instantiating any Qt objects. This is useful for
    unit tests or import-time calls that must not start the GUI event loop.
    """
    _fail_fast_verify()
    if headless:
        # Avoid creating a QApplication and opening windows during tests.
        return 0

    # Install a simple excepthook that writes unhandled Python exceptions to
    # <repo>/run_exception.txt. This helps capture tracebacks coming from the
    # GUI event loop or other threads where exceptions might otherwise be lost.
    def _write_unhandled(exc_type, exc_value, exc_tb):
        try:
            out_path = ROOT / "run_exception.txt"
            import traceback as _tb

            with out_path.open("w", encoding="utf-8") as f:
                _tb.print_exception(exc_type, exc_value, exc_tb, file=f)
        except Exception:
            # Best-effort only; don't let the hook raise.
            pass
        # Delegate to the default hook to preserve console behaviour
        try:
            sys.__excepthook__(exc_type, exc_value, exc_tb)
        except Exception:
            pass

    sys.excepthook = _write_unhandled
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication(sys.argv)
    screens = QtGui.QGuiApplication.screens()
    primary = QtGui.QGuiApplication.primaryScreen()
    second = screens[1] if len(screens) > 1 else primary

    # Create both windows targeting the secondary screen
    view_win = ViewWindow(second)
    view_win.set_external_layout(True)
    control_win = ControlWindow(app, second, view_win)

    # Arrange side-by-side on the secondary screen: View (left), Control (right)
    try:
        geo = second.availableGeometry()
        half_w = max(200, geo.width() // 2)
        full_h = max(200, geo.height())
        left_x = geo.left()
        top_y = geo.top()

        # View window on the left half
        if view_win.windowHandle():
            view_win.windowHandle().setScreen(second)
        view_win.setGeometry(left_x, top_y, half_w, full_h)

        # Control window on the right half
        if control_win.windowHandle():
            control_win.windowHandle().setScreen(second)
        right_x = left_x + half_w
        right_w = geo.width() - (right_x - left_x)
        control_win.resize(right_w, full_h)
        control_win.move(right_x, top_y)
    except Exception:
        # Fallback: let each window manage its own geometry
        pass

    # Show after arranging; ViewWindow won't auto-center when external layout is enabled
    view_win.show()
    # Return the application's exit code instead of calling sys.exit here.
    # This allows callers (tests, importers) to invoke main() without
    # raising SystemExit; the script entrypoint below will still
    # exit the interpreter when run directly.
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
