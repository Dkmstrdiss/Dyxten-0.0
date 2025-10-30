"""Helper that keeps a Windows window as a borderless, click-through overlay.

The script was tailored for the PyQt view opened by ``python core/main.py`` whose
window title defaults to ``"Python 3"``. By default it forces the chosen window
into a borderless (frameless) fullscreen mode on the requested monitor, makes it
click-through, and keeps it always-on-top while it is visible. When the window is
minimised it drops the *always on top* flag so the desktop immediately takes the
focus back ("background +1"). Use ``--windowed`` to keep the overlay in a
centered windowed layout instead of stretching it to the monitor.

Usage (run from a Windows Python environment):

    python click_through_overlay.py --monitor 1

Optional arguments allow you to target a different window title or monitor and
to switch to a windowed layout. Press Ctrl+C in the terminal to exit.
"""

from __future__ import annotations

import argparse
import ctypes
import sys
import time
from ctypes import POINTER, Structure, WINFUNCTYPE, c_bool, c_void_p, create_unicode_buffer, windll
from ctypes import wintypes

user32 = windll.user32

GWL_STYLE = -16
GWL_EXSTYLE = -20
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_MAXIMIZEBOX = 0x00010000
WS_SYSMENU = 0x00080000
WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
LWA_ALPHA = 0x00000002
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SWP_FRAMECHANGED = 0x0020
SWP_NOOWNERZORDER = 0x0200


class RECT(Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class MONITORINFO(Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", wintypes.DWORD),
    ]

WNDENUMPROC = WINFUNCTYPE(c_bool, wintypes.HWND, c_void_p)
MONITORENUMPROC = WINFUNCTYPE(c_bool, wintypes.HMONITOR, wintypes.HDC, POINTER(RECT), c_void_p)


class ClickThroughController:
    def __init__(
        self,
        title_substring: str,
        monitor_index: int,
        poll_interval: float = 0.3,
        *,
        windowed: bool = False,
        window_size: tuple[int, int] | None = None,
    ) -> None:
        self.title_substring = title_substring.lower()
        self.monitor_index = monitor_index
        self.poll_interval = poll_interval
        self.hwnd: int | None = None
        self.click_through_enabled = False
        self.topmost_enabled = False
        self.prepared = False
        self.monitor_rect: RECT | None = None
        self.windowed = windowed
        size = window_size or (1280, 720)
        width, height = size
        self.window_width = max(100, int(width))
        self.window_height = max(100, int(height))

    def run(self) -> None:
        while True:
            try:
                if not self.hwnd or not user32.IsWindow(self.hwnd):
                    self.hwnd = self._find_window()
                    if not self.hwnd:
                        self.prepared = False
                        time.sleep(self.poll_interval)
                        continue

                if not self.prepared:
                    self._prepare_window()

                minimized = bool(user32.IsIconic(self.hwnd))
                desired_topmost = not minimized

                if not self.click_through_enabled:
                    self._apply_click_through()

                if desired_topmost != self.topmost_enabled:
                    self._set_topmost(desired_topmost)

                time.sleep(self.poll_interval)
            except KeyboardInterrupt:
                break

    def _find_window(self) -> int | None:
        matches: list[int] = []

        @WNDENUMPROC
        def enum_callback(hwnd: int, lparam: c_void_p) -> bool:
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length:
                    buffer = create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buffer, length + 1)
                    title = buffer.value
                    if self.title_substring in title.lower():
                        matches.append(hwnd)
                        return False
            return True

        user32.EnumWindows(enum_callback, 0)
        return matches[0] if matches else None

    def _prepare_window(self) -> None:
        if not self.hwnd:
            return
        self.monitor_rect = self.monitor_rect or self._get_monitor_rect()
        self._make_borderless()
        self._resize_to_monitor()
        self._apply_click_through()
        self.prepared = True

    def _apply_click_through(self) -> None:
        if not self.hwnd:
            return
        ex_style = user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
        ex_style |= WS_EX_LAYERED | WS_EX_TRANSPARENT
        user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE, ex_style)
        user32.SetLayeredWindowAttributes(self.hwnd, 0, 255, LWA_ALPHA)
        self.click_through_enabled = True

    def _make_borderless(self) -> None:
        if not self.hwnd:
            return
        style = user32.GetWindowLongW(self.hwnd, GWL_STYLE)
        style &= ~(WS_CAPTION | WS_THICKFRAME | WS_SYSMENU | WS_MAXIMIZEBOX)
        style |= WS_POPUP | WS_VISIBLE
        user32.SetWindowLongW(self.hwnd, GWL_STYLE, style)
        user32.SetWindowPos(
            self.hwnd,
            0,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED | SWP_NOOWNERZORDER,
        )

    def _resize_to_monitor(self) -> None:
        if not self.hwnd:
            return
        rect = self.monitor_rect or self._get_monitor_rect()
        if not rect:
            return
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        left = rect.left
        top = rect.top
        if self.windowed:
            width = max(1, min(width, self.window_width))
            height = max(1, min(height, self.window_height))
            horizontal_space = (rect.right - rect.left) - width
            vertical_space = (rect.bottom - rect.top) - height
            left = rect.left + max(0, horizontal_space // 2)
            top = rect.top + max(0, vertical_space // 2)
        user32.SetWindowPos(
            self.hwnd,
            HWND_TOPMOST,
            left,
            top,
            width,
            height,
            SWP_NOACTIVATE | SWP_SHOWWINDOW,
        )
        self.topmost_enabled = True

    def _set_topmost(self, enable: bool) -> None:
        if not self.hwnd:
            return
        insert_after = HWND_TOPMOST if enable else HWND_NOTOPMOST
        user32.SetWindowPos(
            self.hwnd,
            insert_after,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
        )
        self.topmost_enabled = enable

    def _get_monitor_rect(self) -> RECT | None:
        monitors: list[RECT] = []

        @MONITORENUMPROC
        def enum_proc(hmonitor, _hdc, _rect_ptr, _lparam) -> bool:
            info = MONITORINFO()
            info.cbSize = wintypes.DWORD(ctypes.sizeof(MONITORINFO))
            if user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
                monitors.append(info.rcMonitor)
            return True

        user32.EnumDisplayMonitors(0, 0, enum_proc, 0)
        if not monitors:
            return None

        index = min(max(self.monitor_index, 0), len(monitors) - 1)
        return monitors[index]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Force a window into a borderless click-through overlay on Windows."
    )
    parser.add_argument(
        "--title",
        default="python 3",
        help="Substring of the window title to watch (case insensitive).",
    )
    parser.add_argument(
        "--monitor",
        type=int,
        default=1,
        help="Monitor index to use for fullscreen (0 = primary).",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.3,
        help="Polling interval in seconds (default: 0.3).",
    )
    parser.add_argument(
        "--windowed",
        action="store_true",
        help="Keep the window borderless but windowed (centered on the monitor).",
    )
    parser.add_argument(
        "--window-width",
        type=int,
        default=1280,
        help="Window width when --windowed is set (default: 1280).",
    )
    parser.add_argument(
        "--window-height",
        type=int,
        default=720,
        help="Window height when --windowed is set (default: 720).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    controller = ClickThroughController(
        args.title,
        monitor_index=args.monitor,
        poll_interval=args.interval,
        windowed=args.windowed,
        window_size=(args.window_width, args.window_height),
    )
    controller.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
