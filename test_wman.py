"""Tests for wman.py."""

import io
import sys
import unittest
from unittest.mock import MagicMock, call, patch

from wman import enumerate_windows, find_window, move_window, snap_window, main


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


class TestSnapWindow(unittest.TestCase):
    """snap_window() should snap a window to the left or right half of the work area."""

    def _make_win32(self, work_area=(0, 0, 1920, 1040), is_minimized=False):
        win32 = MagicMock()
        wa = MagicMock()
        wa.left, wa.top, wa.right, wa.bottom = work_area
        win32.get_work_area.return_value = wa
        win32.is_iconic.return_value = is_minimized
        rect = MagicMock()
        rect.left, rect.top, rect.right, rect.bottom = (100, 100, 500, 400)
        win32.get_window_rect.return_value = rect
        return win32

    def test_snap_left(self):
        win32 = self._make_win32(work_area=(0, 0, 1920, 1040))
        snap_window(win32, 100, "left")
        win32.move_window.assert_called_once_with(100, 0, 0, 960, 1040)

    def test_snap_right(self):
        win32 = self._make_win32(work_area=(0, 0, 1920, 1040))
        snap_window(win32, 100, "right")
        win32.move_window.assert_called_once_with(100, 960, 0, 960, 1040)

    def test_snap_right_odd_width(self):
        # wa_width=1921: left gets 960, right gets 961 (no 1-pixel gap)
        win32 = self._make_win32(work_area=(0, 0, 1921, 1040))
        snap_window(win32, 100, "right")
        win32.move_window.assert_called_once_with(100, 960, 0, 961, 1040)

    def test_snap_with_nonzero_work_area_origin(self):
        # Taskbar on left, work area starts at x=60
        win32 = self._make_win32(work_area=(60, 0, 1920, 1040))
        snap_window(win32, 100, "left")
        win32.move_window.assert_called_once_with(100, 60, 0, 930, 1040)

    def test_snap_restores_minimized_window(self):
        win32 = self._make_win32(is_minimized=True)
        snap_window(win32, 100, "left")
        win32.show_window.assert_called_once_with(100, 9)


class _CLITestBase(unittest.TestCase):
    """Shared helpers for CLI tests."""

    def _make_win32(self, windows=None, work_area=(0, 0, 1920, 1040)):
        if windows is None:
            windows = {100: "Notepad", 200: "Calculator"}
        win32 = MagicMock()

        def fake_enum(callback):
            for hwnd, title in windows.items():
                win32.is_window_visible.return_value = True
                win32.get_window_text.return_value = title
                callback(hwnd)

        win32.enum_windows.side_effect = fake_enum
        win32.is_iconic.return_value = False
        rect = MagicMock()
        rect.left, rect.top, rect.right, rect.bottom = (10, 20, 810, 620)
        win32.get_window_rect.return_value = rect
        wa = MagicMock()
        wa.left, wa.top, wa.right, wa.bottom = work_area
        win32.get_work_area.return_value = wa
        return win32


class TestDirectCLI(_CLITestBase):
    """Direct-mode CLI: python wman.py list|move|snap ..."""

    @patch("wman.Win32API")
    def test_list(self, MockWin32API):
        win32 = self._make_win32()
        MockWin32API.return_value = win32
        with patch("sys.argv", ["wman.py", "list"]):
            buf = io.StringIO()
            with patch("sys.stdout", buf):
                main()
            output = buf.getvalue()
        self.assertIn("Notepad", output)
        self.assertIn("100", output)

    @patch("wman.Win32API")
    def test_move_with_args(self, MockWin32API):
        win32 = self._make_win32()
        MockWin32API.return_value = win32
        with patch("sys.argv", ["wman.py", "move", "Notepad", "--x", "50", "--y", "60"]):
            main()
        win32.move_window.assert_called_once_with(100, 50, 60, 800, 600)

    @patch("wman.Win32API")
    def test_snap_left(self, MockWin32API):
        win32 = self._make_win32()
        MockWin32API.return_value = win32
        with patch("sys.argv", ["wman.py", "snap", "Notepad", "--direction", "left"]):
            main()
        win32.move_window.assert_called_once_with(100, 0, 0, 960, 1040)


class TestInteractiveCLI(_CLITestBase):
    """Interactive menu mode: python wman.py (no args)."""

    @patch("wman.Win32API")
    @patch("builtins.input")
    def test_list_then_quit(self, mock_input, MockWin32API):
        win32 = self._make_win32()
        MockWin32API.return_value = win32
        mock_input.side_effect = ["1", "q"]
        with patch("sys.argv", ["wman.py"]):
            buf = io.StringIO()
            with patch("sys.stdout", buf):
                main()
            output = buf.getvalue()
        self.assertIn("Notepad", output)

    @patch("wman.Win32API")
    @patch("builtins.input")
    def test_move_interactive(self, mock_input, MockWin32API):
        win32 = self._make_win32()
        MockWin32API.return_value = win32
        # Choose move, enter window title, x=50, y empty, width empty, height empty, then quit
        mock_input.side_effect = ["2", "Notepad", "50", "", "", "", "q"]
        with patch("sys.argv", ["wman.py"]):
            buf = io.StringIO()
            with patch("sys.stdout", buf):
                main()
        win32.move_window.assert_called_once_with(100, 50, 20, 800, 600)

    @patch("wman.Win32API")
    @patch("builtins.input")
    def test_snap_interactive(self, mock_input, MockWin32API):
        win32 = self._make_win32()
        MockWin32API.return_value = win32
        # Choose snap, enter window title, direction left, then quit
        mock_input.side_effect = ["3", "Notepad", "left", "q"]
        with patch("sys.argv", ["wman.py"]):
            buf = io.StringIO()
            with patch("sys.stdout", buf):
                main()
        win32.move_window.assert_called_once_with(100, 0, 0, 960, 1040)


if __name__ == "__main__":
    unittest.main()
