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
_DEFAULT_RADIUS_RATIO = 0.35


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
        self._span_overrides: Optional[List[float]] = None
        self._coverage_gap_deg = 0.0
        self._coverage_offset_deg = 0.0
        self._equidistant = False
        self._manual_angles: Optional[List[float]] = None

        # Donut geometry - use default radius ratio
        self._radius_ratio = _DEFAULT_RADIUS_RATIO  # 0.35
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

    def configure_orbital_layout(
        self,
        diameters: Sequence[float],
        *,
        coverage_angle: float = 0.0,
        coverage_offset: float = 0.0,
        equidistant: bool = False,
        angles: Optional[Sequence[float]] = None,
    ) -> None:
        """Store tangency information provided by the indicator tab."""

        count = len(self.buttons)
        if count == 0:
            return
        self._equidistant = bool(equidistant)
        try:
            base_values = [float(value) for value in diameters]
        except Exception:
            base_values = []
        fallback = base_values[-1] if base_values else float(self.icon_size)
        values = []
        for idx in range(count):
            if idx < len(base_values):
                values.append(base_values[idx])
            else:
                values.append(fallback)
        manual_angles: Optional[List[float]] = None
        if angles is not None:
            manual_angles = []
            for idx in range(count):
                if idx < len(angles):
                    try:
                        manual_angles.append(float(angles[idx]) % 360.0)
                    except Exception:
                        manual_angles.append(0.0)
                elif manual_angles:
                    manual_angles.append(manual_angles[-1])
                else:
                    manual_angles.append(0.0)
            if manual_angles and not any(not math.isfinite(val) for val in manual_angles):
                self._manual_angles = manual_angles
            else:
                self._manual_angles = None
        else:
            self._manual_angles = None
        if not values or self._manual_angles is not None:
            self._span_overrides = None
        else:
            if self._equidistant:
                self._span_overrides = None
            else:
                spans: List[float] = []
                for idx in range(count):
                    current = max(0.0, values[idx])
                    nxt = max(0.0, values[(idx + 1) % count])
                    spans.append((current + nxt) * 0.5)
                self._span_overrides = spans
        try:
            self._coverage_gap_deg = max(0.0, min(360.0, float(coverage_angle)))
        except Exception:
            self._coverage_gap_deg = 0.0
        try:
            self._coverage_offset_deg = float(coverage_offset) % 360.0
        except Exception:
            self._coverage_offset_deg = 0.0
        self._position_all()

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

    def _compute_button_color(
        self, button: QtWidgets.QToolButton, fallback: QtGui.QColor
    ) -> QtGui.QColor:
        try:
            icon = button.icon()
        except Exception:
            return QtGui.QColor(fallback)
        if icon.isNull():
            return QtGui.QColor(fallback)
        try:
            size = button.iconSize()
            width = int(size.width()) or self.icon_size
            height = int(size.height()) or self.icon_size
        except Exception:
            width = self.icon_size
            height = self.icon_size
        width = max(1, width)
        height = max(1, height)
        pixmap = icon.pixmap(width, height)
        if pixmap.isNull():
            return QtGui.QColor(fallback)
        image = pixmap.toImage().convertToFormat(QtGui.QImage.Format_ARGB32)
        total_r = total_g = total_b = 0
        total_a = 0
        for y in range(image.height()):
            for x in range(image.width()):
                qcol = QtGui.QColor(image.pixel(x, y))
                alpha = qcol.alpha()
                if alpha == 0:
                    continue
                total_r += qcol.red() * alpha
                total_g += qcol.green() * alpha
                total_b += qcol.blue() * alpha
                total_a += alpha
        if total_a == 0:
            return QtGui.QColor(fallback)
        return QtGui.QColor(
            int(total_r / total_a),
            int(total_g / total_a),
            int(total_b / total_a),
        )

    def button_colors(self) -> List[QtGui.QColor]:
        colors: List[QtGui.QColor] = []
        for idx, button in enumerate(self.buttons):
            if idx < len(self.segments):
                _, seg_color = self.segments[idx]
                fallback = QtGui.QColor(seg_color)
            else:
                fallback = QtGui.QColor(255, 255, 255)
            color = self._compute_button_color(button, fallback)
            if not color.isValid():
                color = QtGui.QColor(fallback)
            colors.append(color)
        return colors

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
            radius_mid = float(min_dim) * float(self._radius_ratio)
        else:
            radius_mid = float(self.R_outer + self.R_inner) * 0.5

        # position buttons along the ring
        total = len(self.buttons)
        manual_angles = None
        if isinstance(self._manual_angles, list) and len(self._manual_angles) >= total:
            manual_angles = [float(self._manual_angles[idx % len(self._manual_angles)]) % 360.0 for idx in range(total)]
        spans = None
        if manual_angles is None and (not self._equidistant):
            if isinstance(self._span_overrides, list) and len(self._span_overrides) >= total:
                spans = self._span_overrides
        angle_steps: Optional[List[float]] = None
        angle_list: List[float] = []
        gap = 0.0
        if manual_angles is not None:
            angle_list = [((angle + self._angle_offset_deg) % 360.0) for angle in manual_angles]
        else:
            coverage_total = 0.0
            if spans and radius_mid > 1e-3:
                angle_steps = []
                for span in spans[:total]:
                    chord = max(0.0, min(float(span), (radius_mid * 2.0) * 0.999999))
                    if chord <= 1e-3:
                        angle_steps.append(0.0)
                        continue
                    ratio = max(0.0, min(1.0, chord / (2.0 * radius_mid)))
                    try:
                        angle_steps.append(math.degrees(2.0 * math.asin(ratio)))
                    except ValueError:
                        angle_steps.append(math.degrees(math.pi))
                coverage_total = sum(angle_steps)
                if not any(a > 1e-3 for a in angle_steps):
                    angle_steps = None
            if angle_steps:
                desired_gap = max(0.0, min(360.0, self._coverage_gap_deg))
                max_gap = max(0.0, 360.0 - min(360.0, coverage_total))
                gap = min(desired_gap, max_gap)
                start_angle = -90.0
                start_angle += (self._coverage_offset_deg + gap) % 360.0
                current = start_angle
                for idx in range(total):
                    angle_list.append((current + self._angle_offset_deg) % 360.0)
                    current += angle_steps[idx % len(angle_steps)]
            else:
                gap = max(0.0, min(360.0, self._coverage_gap_deg)) if self._equidistant else 0.0
                if gap >= 360.0:
                    gap = 0.0
                start_angle = -90.0
                if self._equidistant:
                    start_angle += (self._coverage_offset_deg + gap) % 360.0
                step = 360.0 / total if total else 0.0
                if self._equidistant and total:
                    step = (360.0 - gap) / total if total else 0.0
                current = start_angle
                for _ in range(total):
                    angle_list.append((current + self._angle_offset_deg) % 360.0)
                    current += step
        for idx, button in enumerate(self.buttons):
            angle = angle_list[idx] if idx < len(angle_list) else 0.0
            angle_rad = math.radians(angle)
            x = int(cx + radius_mid * math.cos(angle_rad) - self.icon_size / 2)
            y = int(cy + radius_mid * math.sin(angle_rad) - self.icon_size / 2)
            button.move(x, y)
            if manual_angles:
                angle += manual_angles[idx % len(manual_angles)]
            else:
                angle += step
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
