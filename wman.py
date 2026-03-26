"""Window manager POC — list, move, and snap windows using Win32 APIs."""

import ctypes
import ctypes.wintypes as wintypes

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
SPI_GETWORKAREA = 0x0030


class Win32API:
    """Thin wrapper around ctypes Win32 calls so tests can mock them."""

    def __init__(self):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (OSError, AttributeError):
            pass

    def enum_windows(self, callback):
        @WNDENUMPROC
        def _cb(hwnd, _lparam):
            callback(hwnd)
            return True

        ctypes.windll.user32.EnumWindows(_cb, 0)

    def is_window_visible(self, hwnd):
        return bool(ctypes.windll.user32.IsWindowVisible(hwnd))

    def get_window_text(self, hwnd):
        buf = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, 256)
        return buf.value

    def get_window_rect(self, hwnd):
        rect = wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        return rect

    def move_window(self, hwnd, x, y, w, h):
        ctypes.windll.user32.MoveWindow(hwnd, x, y, w, h, True)

    def is_iconic(self, hwnd):
        return bool(ctypes.windll.user32.IsIconic(hwnd))

    def show_window(self, hwnd, cmd):
        ctypes.windll.user32.ShowWindow(hwnd, cmd)

    def get_work_area(self):
        rect = wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(
            SPI_GETWORKAREA, 0, ctypes.byref(rect), 0
        )
        return rect


def enumerate_windows(win32):
    """Return {hwnd: title} for all visible windows with non-empty titles."""
    windows = {}

    def _collect(hwnd):
        if win32.is_window_visible(hwnd) and win32.get_window_text(hwnd):
            windows[hwnd] = win32.get_window_text(hwnd)

    win32.enum_windows(_collect)
    return windows
