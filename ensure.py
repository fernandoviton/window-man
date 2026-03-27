"""Ensure a window is running — launch the app if no matching window is found."""

from wman import enumerate_windows


def ensure_window(win32, title, path=None):
    """Launch an app if no window matching title is found. Returns hwnd or None."""
    windows = enumerate_windows(win32)
    needle = title.lower()
    matches = {h: t for h, t in windows.items() if needle in t.lower()}
    if matches:
        hwnd = next(iter(matches))
        exe_path = win32.get_process_path(hwnd)
        detail = f" [{exe_path}]" if exe_path else ""
        print(f"Already running: {matches[hwnd]} (hwnd {hwnd:#x}){detail}")
        return hwnd
    if not path:
        raise ValueError(f"No window matching '{title}' and no --path provided to launch")
    print(f"Launching: {path}")
    result = win32.shell_execute(path)
    if result <= 32:
        print(f"Warning: launch may have failed (error code {result})")
    return None
