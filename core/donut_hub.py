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

try:  # pragma: no cover - only available on Windows
    from win32 import win32con, win32gui
except ImportError:  # pragma: no cover - the widget only works on Windows
    win32con = None  # type: ignore[assignment]
    win32gui = None  # type: ignore[assignment]


TITLE = "DyxtenJavaView"
ROOT = Path(__file__).resolve().parents[1]


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

        # Donut geometry
        self.R_outer = 260
        self.R_inner = 160
        self.core_diam = 360
        self.icon_size = 40

        # Core widget that will host the Java window
        self.core = QtWidgets.QWidget(self)
        self.core.setAttribute(QtCore.Qt.WA_NativeWindow, True)
        self.core.resize(self.core_diam, self.core_diam)

        # Segments (colors) and default icon mapping
        self.segments: Sequence[Tuple[str, QtGui.QColor]] = [
            ("music", QtGui.QColor("#E53935")),
            ("games", QtGui.QColor("#2E7D32")),
            ("mail", QtGui.QColor("#66BB6A")),
            ("secure", QtGui.QColor("#C0CA33")),
            ("bulb", QtGui.QColor("#FBC02D")),
            ("doc", QtGui.QColor("#FB8C00")),
            ("laptop", QtGui.QColor("#F4511E")),
            ("gauge", QtGui.QColor("#9E9E9E")),
        ]

        self.icon_map: Dict[str, Path | str] = (
            {key: _resolve_icon(path) for key, path in (icon_map or DEFAULT_ICONS).items()}
        )

        self.buttons: List[QtWidgets.QToolButton] = []
        self._build_buttons()

        # Java embedding
        self.jar_path = Path(jar_path) if jar_path else None
        self.proc: Optional[subprocess.Popen[str]] = None
        if self.jar_path is not None:
            QtCore.QTimer.singleShot(200, self._start_java)

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
            button.setStyleSheet(
                f"""
                QToolButton {{
                  background: rgba(0,0,0,0.45);
                  border: 1px solid rgba(255,255,255,0.18);
                  border-radius: {self.icon_size // 2}px;
                }}
                QToolButton:hover {{ background: rgba(0,0,0,0.62); }}
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

        # position buttons along the ring
        total = len(self.buttons)
        radius_mid = (self.R_outer + self.R_inner) // 2
        for index, button in enumerate(self.buttons):
            angle = math.radians(-90 + index * (360.0 / total))
            x = int(cx + radius_mid * math.cos(angle) - self.icon_size / 2)
            y = int(cy + radius_mid * math.sin(angle) - self.icon_size / 2)
            button.move(x, y)
        self.update()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._position_all()

    # ------------------------------------------------------------------
    # Painting
    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # type: ignore[override]
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        cx, cy = self.width() / 2, self.height() / 2

        shadow = QtGui.QRadialGradient(QtCore.QPointF(cx, cy), self.R_outer + 24)
        shadow.setColorAt(0.8, QtGui.QColor(0, 0, 0, 60))
        shadow.setColorAt(1.0, QtGui.QColor(0, 0, 0, 0))
        painter.setBrush(shadow)
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawEllipse(
            QtCore.QRectF(
                cx - (self.R_outer + 24),
                cy - (self.R_outer + 24),
                2 * (self.R_outer + 24),
                2 * (self.R_outer + 24),
            )
        )

        total = len(self.segments)
        for index, (key, color) in enumerate(self.segments):
            start = -90 + index * (360.0 / total)
            span = 360.0 / total
            path = QtGui.QPainterPath()
            rect_outer = QtCore.QRectF(
                cx - self.R_outer, cy - self.R_outer, 2 * self.R_outer, 2 * self.R_outer
            )
            rect_inner = QtCore.QRectF(
                cx - self.R_inner, cy - self.R_inner, 2 * self.R_inner, 2 * self.R_inner
            )
            path.moveTo(cx, cy)
            path.arcMoveTo(rect_outer, start)
            path.arcTo(rect_outer, start, span)
            path.lineTo(
                cx + self.R_inner * math.cos(math.radians(start + span)),
                cy + self.R_inner * math.sin(math.radians(start + span)),
            )
            path.arcTo(rect_inner, start + span, -span)
            path.closeSubpath()

            grad = QtGui.QLinearGradient(
                QtCore.QPointF(
                    cx + self.R_outer * math.cos(math.radians(start)),
                    cy + self.R_outer * math.sin(math.radians(start)),
                ),
                QtCore.QPointF(cx, cy),
            )
            base = QtGui.QColor(color)
            base.setAlpha(220)
            grad.setColorAt(0.0, base.lighter(120))
            grad.setColorAt(1.0, base.darker(120))
            painter.fillPath(path, grad)

        pen = QtGui.QPen(QtGui.QColor(255, 255, 255, 30), 2)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawEllipse(QtCore.QRectF(cx - self.R_outer, cy - self.R_outer, 2 * self.R_outer, 2 * self.R_outer))
        painter.drawEllipse(QtCore.QRectF(cx - self.R_inner, cy - self.R_inner, 2 * self.R_inner, 2 * self.R_inner))

        for radius, width, alpha in [(self.R_inner - 34, 8, 200), (self.R_inner - 18, 10, 230)]:
            pen = QtGui.QPen(QtGui.QColor(255, 255, 255, alpha), width)
            painter.setPen(pen)
            painter.drawEllipse(QtCore.QRectF(cx - radius, cy - radius, 2 * radius, 2 * radius))
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


DEFAULT_ICONS: Dict[str, Path | str] = {
    "music": Path("assets/icons/music.png"),
    "games": Path("assets/icons/gamepad.png"),
    "mail": Path("assets/icons/mail.png"),
    "secure": Path("assets/icons/lock.png"),
    "bulb": Path("assets/icons/bulb.png"),
    "doc": Path("assets/icons/doc.png"),
    "laptop": Path("assets/icons/laptop.png"),
    "gauge": Path("assets/icons/gauge.png"),
}


def main(jar: Optional[str] = None) -> int:
    """Launch the donut hub as a stand-alone application."""

    app = QtWidgets.QApplication(sys.argv)
    widget = DonutHub(jar_path=jar)
    widget.show()
    return app.exec_()


if __name__ == "__main__":  # pragma: no cover - manual launch helper
    sys.exit(main())
