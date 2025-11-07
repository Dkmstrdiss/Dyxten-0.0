"""PyQt donut hub embedding a Java view on Windows.

This module provides the :class:`DonutHub` widget that renders a colorful
circular launcher and embeds an undecorated Java ``JFrame`` inside the
transparent core of the donut.

The implementation mirrors the prototype shared by the designers while adding
minor robustness tweaks so that it integrates nicely with the rest of the
codebase:

* The search for the Java window title is isolated inside :func:`find_hwnd`.
* Icon assets are resolved relative to the repository root when possible.
* Optional type hints are added for clarity.
"""

from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from PyQt5 import QtCore, QtGui, QtWidgets

from typing import List, Optional, Sequence

# --- moved from core/donut.py to unify donut utilities with DonutHub ---
DEFAULT_DONUT_BUTTON_COUNT = 10
_DEFAULT_RADIUS_RATIO = 0.25


def _make_button(idx: int, label: Optional[str] = None, *, button_id: Optional[int] = None) -> dict:
    """Return a normalized button payload."""
    clean_label = label if (label and label.strip()) else f"Bouton {idx}"
    clean_id = button_id if isinstance(button_id, int) else idx
    return {"id": clean_id, "label": clean_label.strip()}


def default_donut_buttons(count: int = DEFAULT_DONUT_BUTTON_COUNT) -> List[dict]:
    """Build a list of default donut buttons."""
    return [_make_button(i + 1) for i in range(max(1, count))]


def default_donut_config() -> dict:
    """Return the default configuration used by both the UI and the web view."""
    return {
        "buttons": default_donut_buttons(),
        "radiusRatio": _DEFAULT_RADIUS_RATIO,
    }


def _sanitize_buttons(buttons: Sequence[object]) -> List[dict]:
    sanitized: List[dict] = []
    for idx, entry in enumerate(buttons):
        slot = idx + 1
        if isinstance(entry, dict):
            label = str(entry.get("label") or entry.get("text") or entry.get("name") or "").strip()
            ident = entry.get("id")
            sanitized.append(_make_button(slot, label, button_id=ident if isinstance(ident, int) else None))
        elif isinstance(entry, str):
            sanitized.append(_make_button(slot, entry))
        elif entry is None:
            sanitized.append(_make_button(slot))
        if len(sanitized) >= DEFAULT_DONUT_BUTTON_COUNT:
            break
    while len(sanitized) < DEFAULT_DONUT_BUTTON_COUNT:
        sanitized.append(_make_button(len(sanitized) + 1))
    return sanitized


def sanitize_donut_state(payload: Optional[dict]) -> dict:
    """Return a sanitized donut state based on user-provided payload."""
    if not isinstance(payload, dict):
        return default_donut_config()

    base = default_donut_config()

    buttons = payload.get("buttons")
    if isinstance(buttons, Sequence):
        base["buttons"] = _sanitize_buttons(buttons)

    radius = payload.get("radiusRatio")
    if isinstance(radius, (int, float)):
        base["radiusRatio"] = max(0.05, min(0.9, float(radius)))

    return base

# ------------------------------------------------------------------

try:  # pragma: no cover - only available on Windows
    from win32 import win32con, win32gui
except ImportError:  # pragma: no cover - the widget only works on Windows
    win32con = None  # type: ignore[assignment]
    win32gui = None  # type: ignore[assignment]


TITLE = "DyxtenJavaView"
ROOT = Path(__file__).resolve().parents[1]
PNG_DIR = ROOT / "PNG"


def find_hwnd(title_sub: str) -> Optional[int]:
    """Return the first visible top-level window whose title contains ``title_sub``.

    Parameters
    ----------
    title_sub:
        Substring that must be present in the window title.
    """

    if win32gui is None:  # pragma: no cover - safety guard for non-Windows devs
        return None

    matches: List[int] = []

    def _enum(hwnd: int, _unused: Optional[int]) -> None:
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title_sub in title:
                matches.append(hwnd)

    win32gui.EnumWindows(_enum, None)
    return matches[0] if matches else None


class DonutHub(QtWidgets.QWidget):
    """Circular launcher that embeds a Java window in its core."""

    # Emitted after buttons are positioned. Payload: (centers, radii)
    # centers: list of (x, y) in local widget coordinates
    # radii: list of float (pixels)
    donutLayoutChanged = QtCore.pyqtSignal(object, object)

    def __init__(
        self,
        jar_path: Optional[Path | str] = None,
        parent: Optional[QtWidgets.QWidget] = None,
        *,
        icon_map: Optional[Dict[str, Path | str]] = None,
    ) -> None:
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.FramelessWindowHint)
        self.resize(900, 700)

        # angle offset (degrees) applied when positioning buttons
        self._angle_offset_deg = 0.0

        # Donut geometry - use default radius ratio
        self._radius_ratio = _DEFAULT_RADIUS_RATIO  # 0.25
        self.R_outer = 260
        self.R_inner = 160
        self.core_diam = 360
        # Double the diameter of the buttons as requested
        self.icon_size = 80

        # Core widget that will host the Java window
        self.core = QtWidgets.QWidget(self)
        self.core.setAttribute(QtCore.Qt.WA_NativeWindow, True)
        self.core.resize(self.core_diam, self.core_diam)

        # Segments (keys + colors). Use the default donut button count from
        # `core.donut` so the hub matches the configured number of buttons.
        # Keys are generic (btn1, btn2, ...) to allow mapping by order from
        # the PNG/ folder. Colors are generated evenly around the hue circle.
        count = DEFAULT_DONUT_BUTTON_COUNT
        self.segments = []  # type: ignore[var-annotated]
        for i in range(count):
            key = f"btn{i+1}"
            hue = int((360.0 * i) / max(1, count))
            color = QtGui.QColor()
            color.setHsl(hue, 180, 140)  # moderate saturation/lightness
            self.segments.append((key, color))

        # Build the icon map with priority:
        # 1) explicit icon_map passed to constructor
        # 2) images found in the PNG/ folder (filenames like 'music.png' match keys)
        # 3) DEFAULT_ICONS shipped with the app
        supplied: Dict[str, Path | str] = {k: v for k, v in (icon_map or {}).items()}
        pngs_dict = _collect_png_icons()

        # also capture ordered list of PNG files; this enables assignment by
        # order when the user placed exactly one image per button in PNG/
        png_list: List[Path] = []
        try:
            if PNG_DIR.exists() and PNG_DIR.is_dir():
                png_list = sorted(PNG_DIR.glob("*.png"))
        except Exception:
            png_list = []

        ordered_map: Dict[str, Path] = {}
        # If the PNG folder contains at least as many files as segments, map
        # the first N files by order to the N segments. This allows users to
        # drop a set of images and have them assigned even when counts differ
        # (extra files are ignored).
        if len(png_list) >= len(self.segments) and len(png_list) > 0:
            for (key, _), p in zip(self.segments, png_list[: len(self.segments)]):
                ordered_map[key] = p

        final_map: Dict[str, Path | str | None] = {}
        for key, _ in self.segments:
            # priority: explicit supplied map > ordered PNG list (if exact count) > named PNGs > defaults
            if key in supplied:
                final_map[key] = _resolve_icon(supplied[key])
            elif key in ordered_map:
                final_map[key] = _resolve_icon(ordered_map[key])
            elif key in pngs_dict:
                final_map[key] = _resolve_icon(pngs_dict[key])
            elif key in DEFAULT_ICONS:
                # only use DEFAULT_ICONS when a matching key exists there
                final_map[key] = _resolve_icon(DEFAULT_ICONS[key])
            else:
                # no icon available; keep None so callers can handle absence
                final_map[key] = None

        self.icon_map = final_map

        # Debug: print resolved icon paths so we can verify which images are used
        try:
            print("[DonutHub] resolved icon_map:")
            for k, v in self.icon_map.items():
                print(f"  {k}: {str(v)}")
        except Exception:
            # Avoid crashing if print/logging fails in some environments
            pass

        self.buttons: List[QtWidgets.QToolButton] = []
        self._build_buttons()

        # Java embedding
        self.jar_path = Path(jar_path) if jar_path else None
        self.proc: Optional[subprocess.Popen[str]] = None
        if self.jar_path is not None:
            QtCore.QTimer.singleShot(200, self._start_java)

    # ------------------------------------------------------------------
    # Public API for integration with the view widget
    def update_donut_buttons(self, donut: dict) -> None:
        """Update button labels/ids from a sanitized donut config."""
        try:
            cfg = sanitize_donut_state(donut if isinstance(donut, dict) else None)
        except Exception:
            cfg = default_donut_config()
        descriptors = cfg.get("buttons", [])
        # Ensure we have at least the same number of internal buttons
        # We keep existing icon buttons but update text/tooltips and ids.
        for idx, (button, descriptor) in enumerate(zip(self.buttons, descriptors)):
            if isinstance(descriptor, dict):
                label = descriptor.get("label")
                ident = descriptor.get("id")
            else:
                label = None
                ident = None
            text = (label or f"Bouton {idx + 1}").strip()
            try:
                # Use tooltip and accessible name to surface the label
                button.setToolTip(text)
                button.setAccessibleName(text)
                # Also set text for possible text-mode toolbuttons
                button.setText(text)
            except Exception:
                pass
            # store id property for external usage
            try:
                button.setProperty("buttonId", ident if isinstance(ident, int) else idx + 1)
            except Exception:
                pass

    def set_angle_offset(self, degrees: float) -> None:
        """Set rotation offset (degrees) for button layout and re-position."""
        try:
            self._angle_offset_deg = float(degrees) % 360.0
        except Exception:
            self._angle_offset_deg = 0.0
        self._position_all()

    def request_layout_update(self) -> None:
        """Public hook to request recomputing button positions and emit layout.

        Prefer calling this over directly invoking :pymeth:`_position_all` so
        external code does not reach into private methods.
        """
        self._position_all()

    def update_geometry_from_system(self, system_cfg: dict) -> None:
        """Update button size and radius ratio from system configuration.
        
        Parameters
        ----------
        system_cfg : dict
            System configuration containing donutButtonSize and donutRadiusRatio.
        """
        try:
            # Update button size
            new_size = int(system_cfg.get("donutButtonSize", 80))
            new_size = max(20, min(200, new_size))
            if new_size != self.icon_size:
                self.icon_size = new_size
                # Update existing buttons
                for button in self.buttons:
                    button.setFixedSize(self.icon_size, self.icon_size)
                    button.setIconSize(QtCore.QSize(self.icon_size - 8, self.icon_size - 8))
                    button.setStyleSheet(
                        f"""
                        QToolButton {{
                            background: transparent;
                            border: none;
                            border-radius: {self.icon_size // 2}px;
                        }}
                        QToolButton:hover {{ background: rgba(255,255,255,0.04); }}
                        """
                    )
            
            # Update radius ratio
            new_ratio = float(system_cfg.get("donutRadiusRatio", _DEFAULT_RADIUS_RATIO))
            new_ratio = max(0.05, min(0.90, new_ratio))
            self._radius_ratio = new_ratio
            
            # Update R_outer and R_inner for reference (though _position_all uses _radius_ratio now)
            min_dim = min(self.width(), self.height())
            if min_dim > 0:
                radius_mid = int(min_dim * new_ratio)
                self.R_inner = int(radius_mid * 0.85)
                self.R_outer = int(radius_mid * 1.15)
            
            # Reposition buttons with new geometry
            self._position_all()
        except Exception:
            pass


    # ------------------------------------------------------------------
    # Buttons
    def _build_buttons(self) -> None:
        for button in self.buttons:
            button.deleteLater()
        self.buttons.clear()

        for key, _color in self.segments:
            button = QtWidgets.QToolButton(self)
            button.setCursor(QtCore.Qt.PointingHandCursor)
            button.setFixedSize(self.icon_size, self.icon_size)
            button.setIconSize(QtCore.QSize(self.icon_size - 8, self.icon_size - 8))
            icon_path = self.icon_map.get(key)
            if icon_path:
                button.setIcon(QtGui.QIcon(str(icon_path)))
                # Use the icon filename (stem) as a user-friendly tooltip when possible
                try:
                    tip = Path(str(icon_path)).stem
                except Exception:
                    tip = key
            else:
                tip = key
            # Normalize tip for display
            try:
                disp_tip = str(tip).replace("-", " ").replace("_", " ").capitalize()
            except Exception:
                disp_tip = str(key)
            button.setToolTip(disp_tip)
            button.setStyleSheet(
                f"""
                QToolButton {{
                                    background: transparent;
                                    border: none;
                                    border-radius: {self.icon_size // 2}px;
                }}
                                QToolButton:hover {{ background: rgba(255,255,255,0.04); }}
                """
            )
            button.clicked.connect(lambda _checked=False, k=key: self.on_action(k))
            self.buttons.append(button)
        self._position_all()

    def on_action(self, key: str) -> None:
        """Default callback for segment actions.

        The method prints the action to the console. Override it or connect to
        :pyattr:`~PyQt5.QtWidgets.QToolButton.clicked` for custom behavior.
        """

        print("action:", key)

    def _position_all(self) -> None:
        cx, cy = self.width() // 2, self.height() // 2

        # position Java core
        self.core.move(cx - self.core_diam // 2, cy - self.core_diam // 2)

        # Calculate radius based on _radius_ratio and window size
        min_dim = min(self.width(), self.height())
        if min_dim > 0:
            radius_mid = int(min_dim * self._radius_ratio)
        else:
            radius_mid = (self.R_outer + self.R_inner) // 2

        # position buttons along the ring
        total = len(self.buttons)
        for index, button in enumerate(self.buttons):
            angle = math.radians(self._angle_offset_deg - 90 + index * (360.0 / total))
            x = int(cx + radius_mid * math.cos(angle) - self.icon_size / 2)
            y = int(cy + radius_mid * math.sin(angle) - self.icon_size / 2)
            button.move(x, y)
        self.update()

        # Emit layout (centers and radii) so the renderer can use it.
        try:
            centers = []
            radii = []
            for button in self.buttons:
                geom = button.geometry()
                centers.append((geom.x() + geom.width() / 2.0, geom.y() + geom.height() / 2.0))
                radii.append(geom.width() / 2.0)
            # Emit as plain Python lists
            self.donutLayoutChanged.emit(centers, radii)
        except Exception:
            pass

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._position_all()

    # ------------------------------------------------------------------
    # Painting
    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # type: ignore[override]
        # Intentionally draw nothing: remove colored background, shadows and
        # white circles as requested. Keep the event minimal so the widget
        # remains transparent and the Java core (if any) shows through.
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.end()

    # ------------------------------------------------------------------
    # Java embedding
    def _start_java(self) -> None:
        if self.jar_path is None:
            return
        self.proc = subprocess.Popen(["java", "-jar", str(self.jar_path)])
        self._poll = QtCore.QTimer(self)
        self._poll.setInterval(150)
        self._poll.timeout.connect(self._try_embed)
        self._poll.start()

    def _try_embed(self) -> None:
        if win32gui is None or win32con is None:  # pragma: no cover - Windows only
            return
        hwnd = find_hwnd(TITLE)
        if not hwnd:
            return
        self._poll.stop()
        win32gui.SetParent(hwnd, int(self.core.winId()))
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        style &= ~(win32con.WS_POPUP | win32con.WS_CAPTION | win32con.WS_THICKFRAME)
        style |= win32con.WS_CHILD | win32con.WS_VISIBLE
        win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style)
        self._child = hwnd
        self._fit_child()

    def _fit_child(self) -> None:
        if win32gui is None:  # pragma: no cover - Windows only
            return
        if hasattr(self, "_child"):
            rect = self.core.rect()
            win32gui.SetWindowPos(
                self._child,
                None,
                0,
                0,
                rect.width(),
                rect.height(),
                win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE,
            )

    def event(self, event: QtCore.QEvent) -> bool:  # type: ignore[override]
        if event.type() == QtCore.QEvent.Resize:
            self._fit_child()
        return super().event(event)


def _resolve_icon(path: Path | str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    # Try resolving relative to repo root for convenience
    relative = ROOT / Path(path)
    return relative if relative.exists() else candidate


def _collect_png_icons() -> Dict[str, Path]:
    """Return a mapping of lowercase stem -> Path for all PNG files found in `PNG/`.

    This lets users drop images in the repository `PNG/` folder. Filenames without
    extension that match segment keys (e.g. "music.png") are used; otherwise the
    caller can assign images by order.
    """
    out: Dict[str, Path] = {}
    try:
        if not PNG_DIR.exists() or not PNG_DIR.is_dir():
            return out
    except Exception:
        return out

    for p in sorted(PNG_DIR.glob("*.png")):
        out[p.stem.lower()] = p
    return out


DEFAULT_ICONS: Dict[str, Path | str] = {}


def main(jar: Optional[str] = None) -> int:
    """Launch the donut hub as a stand-alone application."""

    app = QtWidgets.QApplication(sys.argv)
    widget = DonutHub(jar_path=jar)
    widget.show()
    return app.exec_()


if __name__ == "__main__":  # pragma: no cover - manual launch helper
    sys.exit(main())
