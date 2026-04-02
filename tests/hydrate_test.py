"""Tests for hydrate — snapshot and restore window layouts."""

import io
import unittest
from unittest.mock import MagicMock, patch

from layout import WindowEntry
from hydrate import snapshot, restore, diff_layout


class _HydrateTestBase(unittest.TestCase):
    """Shared helpers for hydrate tests."""

    def _make_win32(self, windows=None):
        """Create a mock Win32API.

        windows: list of (hwnd, title, path, rect) tuples.
        rect is (left, top, right, bottom).
        """
        if windows is None:
            windows = []
        win32 = MagicMock()

        rects = {}
        paths = {}
        titles = {}
        for hwnd, title, path, rect in windows:
            titles[hwnd] = title
            paths[hwnd] = path
            r = MagicMock()
            r.left, r.top, r.right, r.bottom = rect
            rects[hwnd] = r

        def fake_enum(callback):
            for hwnd, title, _path, _rect in windows:
                win32.is_window_visible.return_value = True
                win32.get_window_text.return_value = title
                callback(hwnd)

        win32.enum_windows.side_effect = fake_enum
        win32.get_window_rect.side_effect = lambda h: rects[h]
        win32.get_process_path.side_effect = lambda h: paths[h]
        return win32


class TestSnapshot(_HydrateTestBase):
    """snapshot() should capture all visible windows as WindowEntry list."""

    def test_returns_entry_per_visible_window(self):
        win32 = self._make_win32([
            (0x100, "Notepad", r"C:\Windows\notepad.exe", (10, 20, 810, 620)),
            (0x200, "Calculator", r"C:\Windows\calc.exe", (100, 100, 500, 400)),
        ])
        result = snapshot(win32)
        self.assertEqual(len(result), 2)

    def test_entry_has_correct_fields(self):
        win32 = self._make_win32([
            (0x100, "Notepad", r"C:\Windows\notepad.exe", (10, 20, 810, 620)),
        ])
        result = snapshot(win32)
        entry = result[0]
        self.assertEqual(entry.title, "Notepad")
        self.assertEqual(entry.path, r"C:\Windows\notepad.exe")
        self.assertEqual(entry.x, 10)
        self.assertEqual(entry.y, 20)
        self.assertEqual(entry.width, 800)
        self.assertEqual(entry.height, 600)

    def test_none_path_when_process_path_unavailable(self):
        win32 = self._make_win32([
            (0x100, "Mystery Window", None, (0, 0, 400, 300)),
        ])
        result = snapshot(win32)
        self.assertIsNone(result[0].path)

    def test_empty_desktop_returns_empty_list(self):
        win32 = self._make_win32([])
        result = snapshot(win32)
        self.assertEqual(result, [])


class TestRestore(_HydrateTestBase):
    """restore() should reposition running windows and launch missing ones."""

    def test_running_window_is_repositioned(self):
        win32 = self._make_win32([
            (0x100, "Notepad", r"C:\Windows\notepad.exe", (0, 0, 400, 300)),
        ])
        win32.is_iconic.return_value = False
        entries = [WindowEntry("Notepad", "notepad.exe", 50, 60, 800, 600)]
        restore(win32, entries)
        win32.move_window.assert_called_once_with(0x100, 50, 60, 800, 600)
        win32.shell_execute.assert_not_called()

    def test_missing_window_is_launched(self):
        win32 = self._make_win32([
            (0x100, "Notepad", r"C:\Windows\notepad.exe", (0, 0, 400, 300)),
        ])
        win32.shell_execute.return_value = 42
        entries = [WindowEntry("Outlook", "outlook.exe", 0, 0, 960, 1040)]
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            restore(win32, entries)
        win32.shell_execute.assert_called_once_with("outlook.exe")
        win32.move_window.assert_not_called()

    def test_missing_window_with_no_path_is_skipped(self):
        win32 = self._make_win32([])
        entries = [WindowEntry("Ghost", None, 0, 0, 100, 100)]
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            restore(win32, entries)
        win32.shell_execute.assert_not_called()
        win32.move_window.assert_not_called()
        self.assertIn("Skipping", buf.getvalue())

    def test_multiple_entries_handled_independently(self):
        win32 = self._make_win32([
            (0x100, "Notepad", r"C:\Windows\notepad.exe", (0, 0, 400, 300)),
        ])
        win32.is_iconic.return_value = False
        win32.shell_execute.return_value = 42
        entries = [
            WindowEntry("Notepad", "notepad.exe", 10, 20, 800, 600),
            WindowEntry("Outlook", "outlook.exe", 960, 0, 960, 1040),
        ]
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            restore(win32, entries)
        win32.move_window.assert_called_once_with(0x100, 10, 20, 800, 600)
        win32.shell_execute.assert_called_once_with("outlook.exe")

    def test_launch_failure_prints_warning(self):
        win32 = self._make_win32([])
        win32.shell_execute.return_value = 2
        entries = [WindowEntry("BadApp", "bad.exe", 0, 0, 100, 100)]
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            restore(win32, entries)
        output = buf.getvalue()
        self.assertIn("Warning", output)
        self.assertIn("2", output)

    def test_restore_empty_entries_does_nothing(self):
        win32 = self._make_win32([
            (0x100, "Notepad", r"C:\Windows\notepad.exe", (0, 0, 400, 300)),
        ])
        restore(win32, [])
        win32.move_window.assert_not_called()
        win32.shell_execute.assert_not_called()


class TestDiffLayout(_HydrateTestBase):
    """diff_layout() should match running windows to existing layout entries."""

    def test_single_match_updates_geometry(self):
        """Entry matched by path gets updated geometry from running window."""
        win32 = self._make_win32([
            (0x100, "Notepad - NewFile", r"C:\Windows\notepad.exe", (50, 60, 850, 660)),
        ])
        existing = [WindowEntry("Notepad - OldFile", r"C:\Windows\notepad.exe", 10, 20, 800, 600)]
        updated, added, removed = diff_layout(win32, existing)
        self.assertEqual(len(updated), 1)
        self.assertEqual(updated[0].x, 50)
        self.assertEqual(updated[0].y, 60)
        self.assertEqual(updated[0].width, 800)
        self.assertEqual(updated[0].height, 600)
        self.assertEqual(updated[0].title, "Notepad - NewFile")
        self.assertEqual(added, [])
        self.assertEqual(removed, [])

    def test_unmatched_entry_removed(self):
        """Entry with no matching running window goes to removed list."""
        win32 = self._make_win32([
            (0x100, "Notepad", r"C:\Windows\notepad.exe", (0, 0, 800, 600)),
        ])
        existing = [
            WindowEntry("Notepad", r"C:\Windows\notepad.exe", 0, 0, 800, 600),
            WindowEntry("Outlook", r"C:\outlook.exe", 0, 0, 960, 1040),
        ]
        updated, added, removed = diff_layout(win32, existing)
        self.assertEqual(len(updated), 1)
        self.assertEqual(len(removed), 1)
        self.assertEqual(removed[0].title, "Outlook")
        self.assertEqual(added, [])

    def test_unmatched_window_added_when_not_group_only(self):
        """Running window not matching any entry is added."""
        win32 = self._make_win32([
            (0x100, "Notepad", r"C:\Windows\notepad.exe", (10, 20, 810, 620)),
            (0x200, "Calculator", r"C:\calc.exe", (100, 100, 500, 400)),
        ])
        existing = [WindowEntry("Notepad", r"C:\Windows\notepad.exe", 0, 0, 800, 600)]
        updated, added, removed = diff_layout(win32, existing)
        self.assertEqual(len(updated), 1)
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0].title, "Calculator")
        self.assertEqual(added[0].path, r"C:\calc.exe")
        self.assertEqual(removed, [])

    def test_group_only_suppresses_additions(self):
        """With group_only=True, unmatched running windows are NOT added."""
        win32 = self._make_win32([
            (0x100, "Notepad", r"C:\Windows\notepad.exe", (10, 20, 810, 620)),
            (0x200, "Calculator", r"C:\calc.exe", (100, 100, 500, 400)),
        ])
        existing = [WindowEntry("Notepad", r"C:\Windows\notepad.exe", 0, 0, 800, 600)]
        updated, added, removed = diff_layout(win32, existing, group_only=True)
        self.assertEqual(len(updated), 1)
        self.assertEqual(added, [])
        self.assertEqual(removed, [])

    def test_title_tiebreaker_for_same_path(self):
        """Multiple windows with same path use title similarity for matching."""
        win32 = self._make_win32([
            (0x100, "Pull request 123 - Edge", r"C:\edge.exe", (0, 0, 800, 600)),
            (0x200, "GitHub Home - Edge", r"C:\edge.exe", (100, 0, 900, 600)),
        ])
        existing = [
            WindowEntry("Pull request 999 - Edge", r"C:\edge.exe", 10, 10, 700, 500),
            WindowEntry("GitHub Main - Edge", r"C:\edge.exe", 110, 10, 700, 500),
        ]
        updated, added, removed = diff_layout(win32, existing)
        self.assertEqual(len(updated), 2)
        self.assertEqual(added, [])
        self.assertEqual(removed, [])
        pr_entry = next(e for e in updated if "Pull request" in e.title)
        gh_entry = next(e for e in updated if "GitHub" in e.title)
        self.assertEqual(pr_entry.x, 0)
        self.assertEqual(gh_entry.x, 100)

    def test_empty_existing_adds_all(self):
        """No existing entries → all running windows are added."""
        win32 = self._make_win32([
            (0x100, "Notepad", r"C:\notepad.exe", (0, 0, 800, 600)),
            (0x200, "Calc", r"C:\calc.exe", (100, 100, 500, 400)),
        ])
        updated, added, removed = diff_layout(win32, [])
        self.assertEqual(updated, [])
        self.assertEqual(len(added), 2)
        self.assertEqual(removed, [])

    def test_no_running_windows_removes_all(self):
        """No running windows → all existing entries are removed."""
        win32 = self._make_win32([])
        existing = [WindowEntry("Notepad", r"C:\notepad.exe", 0, 0, 800, 600)]
        updated, added, removed = diff_layout(win32, existing)
        self.assertEqual(updated, [])
        self.assertEqual(added, [])
        self.assertEqual(len(removed), 1)

    def test_updated_entry_preserves_group_tag(self):
        """Updated entry keeps its original group tag."""
        win32 = self._make_win32([
            (0x100, "VS Code", r"C:\code.exe", (50, 50, 1010, 1090)),
        ])
        existing = [WindowEntry("VS Code", r"C:\code.exe", 0, 0, 960, 1040, group="dev")]
        updated, added, removed = diff_layout(win32, existing, group_only=True)
        self.assertEqual(len(updated), 1)
        self.assertEqual(updated[0].group, "dev")

    def test_none_path_entries_not_matched(self):
        """Entries with None path cannot be reliably matched."""
        win32 = self._make_win32([
            (0x100, "Mystery", None, (0, 0, 400, 300)),
        ])
        existing = [WindowEntry("Mystery", None, 0, 0, 400, 300)]
        updated, added, removed = diff_layout(win32, existing)
        self.assertEqual(len(removed), 1)
        self.assertEqual(len(added), 1)


if __name__ == "__main__":
    unittest.main()
