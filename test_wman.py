"""Tests for wman.py."""

import unittest
from unittest.mock import MagicMock, call

from wman import enumerate_windows, find_window, move_window


class TestEnumerateWindows(unittest.TestCase):
    """enumerate_windows() should return a dict of {hwnd: title} for visible windows."""

    def _make_win32(self, windows):
        """Create a mock Win32API that yields the given (hwnd, title, visible) tuples."""
        win32 = MagicMock()

        def fake_enum(callback):
            for hwnd, title, visible in windows:
                win32.is_window_visible.return_value = visible
                win32.get_window_text.return_value = title
                callback(hwnd)

        win32.enum_windows.side_effect = fake_enum
        return win32

    def test_returns_visible_windows_with_titles(self):
        win32 = self._make_win32([
            (100, "Notepad", True),
            (200, "Calculator", True),
        ])
        result = enumerate_windows(win32)
        self.assertEqual(result, {100: "Notepad", 200: "Calculator"})

    def test_skips_invisible_windows(self):
        win32 = self._make_win32([
            (100, "Notepad", True),
            (200, "Hidden", False),
        ])
        result = enumerate_windows(win32)
        self.assertEqual(result, {100: "Notepad"})

    def test_skips_windows_with_empty_titles(self):
        win32 = self._make_win32([
            (100, "", True),
            (200, "Calculator", True),
        ])
        result = enumerate_windows(win32)
        self.assertEqual(result, {200: "Calculator"})

    def test_returns_empty_dict_when_no_windows(self):
        win32 = self._make_win32([])
        result = enumerate_windows(win32)
        self.assertEqual(result, {})


class TestFindWindow(unittest.TestCase):
    """find_window() should locate a window by hwnd or title substring."""

    def _make_win32(self, windows):
        """Create a mock Win32API with given visible windows as {hwnd: title}."""
        win32 = MagicMock()

        def fake_enum(callback):
            for hwnd, title in windows.items():
                win32.is_window_visible.return_value = True
                win32.get_window_text.return_value = title
                callback(hwnd)

        win32.enum_windows.side_effect = fake_enum
        return win32

    def test_find_by_hwnd_int(self):
        win32 = self._make_win32({100: "Notepad", 200: "Calculator"})
        hwnd = find_window(win32, "100")
        self.assertEqual(hwnd, 100)

    def test_find_by_hwnd_hex(self):
        win32 = self._make_win32({0xFF: "Notepad"})
        hwnd = find_window(win32, "0xff")
        self.assertEqual(hwnd, 0xFF)

    def test_find_by_title_substring_case_insensitive(self):
        win32 = self._make_win32({100: "Untitled - Notepad", 200: "Calculator"})
        hwnd = find_window(win32, "notepad")
        self.assertEqual(hwnd, 100)

    def test_not_found_raises(self):
        win32 = self._make_win32({100: "Notepad"})
        with self.assertRaises(ValueError):
            find_window(win32, "Chrome")

    def test_hwnd_not_in_visible_windows_raises(self):
        win32 = self._make_win32({100: "Notepad"})
        with self.assertRaises(ValueError):
            find_window(win32, "999")


class TestMoveWindow(unittest.TestCase):
    """move_window() should move/resize a window, restoring it if minimized."""

    def _make_win32(self, is_minimized=False, current_rect=(10, 20, 810, 620)):
        win32 = MagicMock()
        win32.is_iconic.return_value = is_minimized
        rect = MagicMock()
        rect.left, rect.top, rect.right, rect.bottom = current_rect
        win32.get_window_rect.return_value = rect
        return win32

    def test_move_with_all_args(self):
        win32 = self._make_win32()
        move_window(win32, 100, x=50, y=60, width=400, height=300)
        win32.move_window.assert_called_once_with(100, 50, 60, 400, 300)

    def test_partial_args_keep_current_position(self):
        # current rect: left=10, top=20, right=810, bottom=620 → w=800, h=600
        win32 = self._make_win32(current_rect=(10, 20, 810, 620))
        move_window(win32, 100, x=50)
        win32.move_window.assert_called_once_with(100, 50, 20, 800, 600)

    def test_no_args_keeps_everything(self):
        win32 = self._make_win32(current_rect=(10, 20, 810, 620))
        move_window(win32, 100)
        win32.move_window.assert_called_once_with(100, 10, 20, 800, 600)

    def test_restores_minimized_window(self):
        win32 = self._make_win32(is_minimized=True)
        move_window(win32, 100, x=0, y=0, width=800, height=600)
        win32.show_window.assert_called_once_with(100, 9)  # SW_RESTORE = 9
        win32.move_window.assert_called_once()

    def test_does_not_restore_non_minimized_window(self):
        win32 = self._make_win32(is_minimized=False)
        move_window(win32, 100, x=0, y=0, width=800, height=600)
        win32.show_window.assert_not_called()


if __name__ == "__main__":
    unittest.main()
