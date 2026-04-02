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

    def get_process_path(self, hwnd):
        """Return the full executable path for the process owning hwnd, or None."""
        pid = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return None
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        ctypes.windll.kernel32.OpenProcess.restype = wintypes.HANDLE
        handle = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value
        )
        if not handle:
            return None
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            ok = ctypes.windll.kernel32.QueryFullProcessImageNameW(
                handle, 0, buf, ctypes.byref(size)
            )
            return buf.value if ok else None
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)

    def shell_execute(self, path):
        ctypes.windll.shell32.ShellExecuteW.restype = wintypes.HINSTANCE
        result = ctypes.windll.shell32.ShellExecuteW(None, "open", path, None, None, 1)
        return int(result) if result else 0


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
    matches = {h: t for h, t in windows.items() if needle in t.lower()}
    if len(matches) == 1:
        return next(iter(matches))
    if len(matches) > 1:
        lines = [f"  {h:#x}  {t}" for h, t in matches.items()]
        raise ValueError(
            f"'{value}' matches {len(matches)} windows:\n" + "\n".join(lines)
        )
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


def _print_update_preview(updated, added, removed, group=None):
    """Print a summary of what update will do."""
    label = f"Group '{group}' update" if group else "Update"
    print(f"\n{label} preview:")
    if updated:
        print(f"  Updated ({len(updated)}):")
        for e in updated:
            print(f"    - {e.title}")
    if added:
        print(f"  Added ({len(added)}):")
        for e in added:
            print(f"    - {e.title}")
    if removed:
        print(f"  Removed ({len(removed)}):")
        for e in removed:
            print(f"    - {e.title}")
    print()


def _interactive(win32):
    """Interactive menu loop."""
    while True:
        print()
        print("Window Manager")
        print("==============")
        print("1. List windows")
        print("2. Move a window")
        print("3. Snap a window")
        print("4. Ensure a window (launch if needed)")
        print("5. Update layout")
        print("6. Load layout")
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
        elif choice == "4":
            from ensure import ensure_window
            title = input("Window title to find: ").strip()
            try:
                ensure_window(win32, title)
            except ValueError:
                path = input("Path to launch: ").strip()
                if path:
                    ensure_window(win32, title, path=path)
        elif choice == "5":
            from hydrate import diff_layout
            from layout import load_layout, save_layout
            file_path = input("File (enter for layout.yml): ").strip() or "layout.yml"
            group = input("Group name (enter to update all): ").strip() or None
            all_entries = load_layout(file_path)
            if group is not None:
                existing = [e for e in all_entries if e.group == group]
                if not existing:
                    print(f"No entries for group '{group}' to update.")
                    continue
                updated, added, removed = diff_layout(win32, existing, group_only=True)
            else:
                updated, added, removed = diff_layout(win32, all_entries)

            if not updated and not added and not removed:
                print("Nothing to update.")
                continue

            _print_update_preview(updated, added, removed, group=group)
            answer = input("Proceed? [y/N]: ").strip().lower()
            if answer != "y":
                print("Aborted.")
                continue

            if group is not None:
                others = [e for e in all_entries if e.group != group]
                save_layout(file_path, others + updated + added, replace_all=True)
            else:
                save_layout(file_path, updated + added, replace_all=True)
            print(f"Updated '{file_path}' ({len(updated)} updated, {len(added)} added, {len(removed)} removed)")
        elif choice == "6":
            from hydrate import restore
            from layout import load_layout
            file_path = input("File (enter for layout.yml): ").strip() or "layout.yml"
            all_entries = load_layout(file_path)
            if not all_entries:
                print(f"No layout found in '{file_path}'")
                continue
            groups = sorted({e.group for e in all_entries if e.group})
            if groups:
                print("Available groups:", ", ".join(groups))
                group = input("Group name (enter to load all): ").strip() or None
            else:
                group = None
            if group:
                entries = [e for e in all_entries if e.group == group]
                if not entries:
                    print(f"Group '{group}' not found.")
                else:
                    restore(win32, entries)
            else:
                restore(win32, all_entries)


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

        ensure_p = sub.add_parser("ensure", help="Launch app if not already running")
        ensure_p.add_argument("title", help="Window title substring to search for")
        ensure_p.add_argument("--path", default=None, help="Path to launch if not found")

        save_p = sub.add_parser("update", help="Update window layout YAML (diff + confirm)")
        save_p.add_argument("--file", default="layout.yml", help="YAML file path")
        save_p.add_argument("--group", default=None, help="Only update entries with this group")

        load_p = sub.add_parser("load", help="Load and restore a window layout from YAML")
        load_p.add_argument("--file", default="layout.yml", help="YAML file path")
        load_p.add_argument("--group", default=None, help="Load only entries with this group")

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
        elif args.command == "ensure":
            from ensure import ensure_window
            ensure_window(win32, args.title, args.path)
        elif args.command == "update":
            from hydrate import diff_layout
            from layout import load_layout, save_layout
            all_entries = load_layout(args.file)
            if args.group is not None:
                existing = [e for e in all_entries if e.group == args.group]
                if not existing:
                    print(f"No entries for group '{args.group}' to update.")
                    return
                updated, added, removed = diff_layout(win32, existing, group_only=True)
            else:
                updated, added, removed = diff_layout(win32, all_entries)

            if not updated and not added and not removed:
                print("Nothing to update.")
                return

            _print_update_preview(updated, added, removed, group=args.group)
            answer = input("Proceed? [y/N]: ").strip().lower()
            if answer != "y":
                print("Aborted.")
                return

            if args.group is not None:
                # Replace only this group's entries, keep others
                others = [e for e in all_entries if e.group != args.group]
                save_layout(args.file, others + updated + added, replace_all=True)
            else:
                save_layout(args.file, updated + added, replace_all=True)
            print(f"Updated '{args.file}' ({len(updated)} updated, {len(added)} added, {len(removed)} removed)")
        elif args.command == "load":
            from hydrate import restore
            from layout import load_layout
            all_entries = load_layout(args.file)
            if not all_entries:
                print(f"No layout found in '{args.file}'")
            elif args.group is not None:
                entries = [e for e in all_entries if e.group == args.group]
                if not entries:
                    groups = sorted({e.group for e in all_entries if e.group})
                    print(f"Group '{args.group}' not found in '{args.file}'. Available: {', '.join(groups) or '(none)'}")
                else:
                    restore(win32, entries)
            else:
                restore(win32, all_entries)
    else:
        _interactive(win32)


if __name__ == "__main__":
    main()
