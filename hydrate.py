"""Hydrate — snapshot live windows and restore saved layouts."""

from difflib import SequenceMatcher

from layout import WindowEntry
from wman import enumerate_windows, move_window, SW_RESTORE


def snapshot(win32, group=None, ignore=None) -> list[WindowEntry]:
    """Capture all visible windows as a list of WindowEntry.

    ignore: optional callable(path, title) → bool.  When it returns True
    the window is silently skipped.
    """
    windows = enumerate_windows(win32)
    entries = []
    for hwnd, title in windows.items():
        rect = win32.get_window_rect(hwnd)
        path = win32.get_process_path(hwnd)
        if ignore and ignore(path, title):
            continue
        entries.append(WindowEntry(
            title=title, path=path,
            x=rect.left, y=rect.top,
            width=rect.right - rect.left, height=rect.bottom - rect.top,
            group=group,
        ))
    return entries


def restore(win32, entries: list[WindowEntry]) -> None:
    """Restore a list of window entries — reposition running windows, launch missing ones."""
    windows = enumerate_windows(win32)
    for entry in entries:
        # Find a running window whose title contains the entry's title (case-insensitive)
        needle = entry.title.lower()
        hwnd = None
        for h, t in windows.items():
            if needle in t.lower():
                hwnd = h
                break

        if hwnd is not None:
            move_window(win32, hwnd, x=entry.x, y=entry.y,
                        width=entry.width, height=entry.height)
        elif entry.path:
            print(f"Launching: {entry.path}")
            result = win32.shell_execute(entry.path)
            if result <= 32:
                print(f"Warning: launch may have failed (error code {result})")
        else:
            print(f"Skipping '{entry.title}': not running and no path to launch")


def diff_layout(win32, existing_entries, group_only=False, ignore=None):
    """Compare running windows against existing layout entries.

    Matches by executable path, using title similarity as tiebreaker
    when multiple windows share the same path.

    Returns (updated, added, removed) lists of WindowEntry.
    - updated: entries matched to a running window with refreshed geometry
    - added: running windows not matching any entry (empty if group_only)
    - removed: entries with no matching running window
    """
    current = snapshot(win32, ignore=ignore)

    # Group existing entries and current windows by path
    # Skip None-path entries (can't be reliably matched)
    existing_by_path = {}
    unmatched_existing = []
    for entry in existing_entries:
        if entry.path is None:
            unmatched_existing.append(entry)
        else:
            existing_by_path.setdefault(entry.path, []).append(entry)

    current_by_path = {}
    none_path_current = []
    for win in current:
        if win.path is None:
            none_path_current.append(win)
        else:
            current_by_path.setdefault(win.path, []).append(win)

    updated = []
    removed = []
    matched_current_windows = set()

    for path, entries in existing_by_path.items():
        windows = current_by_path.get(path, [])
        if not windows:
            removed.extend(entries)
            continue

        # Match entries to windows by title similarity
        remaining_entries = list(entries)
        remaining_windows = list(windows)

        while remaining_entries and remaining_windows:
            best_score = -1
            best_entry_idx = 0
            best_window_idx = 0

            for ei, entry in enumerate(remaining_entries):
                for wi, win in enumerate(remaining_windows):
                    score = SequenceMatcher(None, entry.title, win.title).ratio()
                    if score > best_score:
                        best_score = score
                        best_entry_idx = ei
                        best_window_idx = wi

            entry = remaining_entries.pop(best_entry_idx)
            win = remaining_windows.pop(best_window_idx)
            updated.append(WindowEntry(
                title=win.title, path=win.path,
                x=win.x, y=win.y, width=win.width, height=win.height,
                group=entry.group,
            ))
            matched_current_windows.add(id(win))

        # Leftover entries with no matching window → removed
        removed.extend(remaining_entries)
        # Leftover windows tracked for potential addition below

    # None-path existing entries are always removed
    removed.extend(unmatched_existing)

    # Collect unmatched running windows for addition
    added = []
    if not group_only:
        for path, windows in current_by_path.items():
            for win in windows:
                if id(win) not in matched_current_windows:
                    added.append(win)
        added.extend(none_path_current)

    return updated, added, removed
