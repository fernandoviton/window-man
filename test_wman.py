"""Tests for wman.py — Round 1: enumerate_windows()."""

import unittest
from unittest.mock import MagicMock

from wman import enumerate_windows


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


if __name__ == "__main__":
    unittest.main()
