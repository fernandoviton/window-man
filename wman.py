"""Window manager POC — list, move, and snap windows using Win32 APIs."""

import argparse
import ctypes
import ctypes.wintypes as wintypes
import sys

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


SW_RESTORE = 9


def find_window(win32, value):
    """Find a window by hwnd (int or hex string) or title substring (case-insensitive).

    Returns the hwnd. Raises ValueError if not found.
    """
    windows = enumerate_windows(win32)

    # Try as integer hwnd first
    try:
        hwnd = int(value, 0)
        if hwnd in windows:
            return hwnd
        raise ValueError(f"No visible window with hwnd {hwnd}")
    except ValueError as e:
        if "No visible window" in str(e):
            raise

    # Treat as title substring (case-insensitive)
    needle = value.lower()
    for hwnd, title in windows.items():
        if needle in title.lower():
            return hwnd
    raise ValueError(f"No window matching '{value}'")


def move_window(win32, hwnd, x=None, y=None, width=None, height=None):
    """Move/resize a window. Unspecified params keep current values. Restores if minimized."""
    if win32.is_iconic(hwnd):
        win32.show_window(hwnd, SW_RESTORE)

    rect = win32.get_window_rect(hwnd)
    cur_x, cur_y = rect.left, rect.top
    cur_w, cur_h = rect.right - rect.left, rect.bottom - rect.top

    win32.move_window(
        hwnd,
        x if x is not None else cur_x,
        y if y is not None else cur_y,
        width if width is not None else cur_w,
        height if height is not None else cur_h,
    )


def snap_window(win32, hwnd, direction):
    """Snap a window to the left or right half of the primary monitor's work area."""
    if win32.is_iconic(hwnd):
        win32.show_window(hwnd, SW_RESTORE)

    wa = win32.get_work_area()
    wa_width = wa.right - wa.left
    wa_height = wa.bottom - wa.top

    if direction == "left":
        win32.move_window(hwnd, wa.left, wa.top, wa_width // 2, wa_height)
    else:
        win32.move_window(
            hwnd, wa.left + wa_width // 2, wa.top, wa_width - wa_width // 2, wa_height
        )


def _print_windows(win32):
    """Print a table of visible windows."""
    windows = enumerate_windows(win32)
    print(f"{'HWND':>10}  {'Title'}")
    print(f"{'----':>10}  {'-----'}")
    for hwnd, title in windows.items():
        print(f"{hwnd:>10}  {title}")


def _interactive(win32):
    """Interactive menu loop."""
    while True:
        print()
        print("Window Manager")
        print("==============")
        print("1. List windows")
        print("2. Move a window")
        print("3. Snap a window")
        print("q. Quit")
        print()
        choice = input("Choose: ").strip()

        if choice == "q":
            break
        elif choice == "1":
            _print_windows(win32)
        elif choice == "2":
            window = input("Window (title or hwnd): ").strip()
            try:
                hwnd = find_window(win32, window)
            except ValueError as e:
                print(f"Error: {e}")
                continue
            x_s = input("X (enter to skip): ").strip()
            y_s = input("Y (enter to skip): ").strip()
            w_s = input("Width (enter to skip): ").strip()
            h_s = input("Height (enter to skip): ").strip()
            move_window(
                win32, hwnd,
                x=int(x_s) if x_s else None,
                y=int(y_s) if y_s else None,
                width=int(w_s) if w_s else None,
                height=int(h_s) if h_s else None,
            )
            print("Moved.")
        elif choice == "3":
            window = input("Window (title or hwnd): ").strip()
            try:
                hwnd = find_window(win32, window)
            except ValueError as e:
                print(f"Error: {e}")
                continue
            direction = input("Direction (left/right): ").strip()
            snap_window(win32, hwnd, direction)
            print("Snapped.")


def main():
    """Entry point — direct mode if subcommand given, otherwise interactive."""
    win32 = Win32API()

    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(prog="wman.py", description="Window Manager")
        sub = parser.add_subparsers(dest="command")

        sub.add_parser("list", help="List visible windows")

        move_p = sub.add_parser("move", help="Move/resize a window")
        move_p.add_argument("window", help="Window title substring or hwnd")
        move_p.add_argument("--x", type=int, default=None)
        move_p.add_argument("--y", type=int, default=None)
        move_p.add_argument("--width", type=int, default=None)
        move_p.add_argument("--height", type=int, default=None)

        snap_p = sub.add_parser("snap", help="Snap a window to half screen")
        snap_p.add_argument("window", help="Window title substring or hwnd")
        snap_p.add_argument("--direction", required=True, choices=["left", "right"])

        args = parser.parse_args()

        if args.command == "list":
            _print_windows(win32)
        elif args.command == "move":
            hwnd = find_window(win32, args.window)
            move_window(win32, hwnd, x=args.x, y=args.y, width=args.width, height=args.height)
            print("Moved.")
        elif args.command == "snap":
            hwnd = find_window(win32, args.window)
            snap_window(win32, hwnd, args.direction)
            print("Snapped.")
    else:
        _interactive(win32)


if __name__ == "__main__":
    main()
