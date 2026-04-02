"""Tests for ensure functionality — launch app if not already running."""

import io
import sys
import unittest
from unittest.mock import MagicMock, patch

from ensure import ensure_window
from wman import main


class _EnsureTestBase(unittest.TestCase):
    """Shared helpers for ensure tests."""

    def _make_win32(self, windows=None):
        """Create a mock Win32API with given visible windows as {hwnd: title}."""
        if windows is None:
            windows = {}
        win32 = MagicMock()

        def fake_enum(callback):
            for hwnd, title in windows.items():
                win32.is_window_visible.return_value = True
                win32.get_window_text.return_value = title
                callback(hwnd)

        win32.enum_windows.side_effect = fake_enum
        win32.shell_execute.return_value = 42
        return win32


class TestEnsureWindow(_EnsureTestBase):
    """ensure_window() should launch an app only if no matching window is found."""

    def test_already_running_returns_hwnd_and_does_not_launch(self):
        win32 = self._make_win32({0x100: "Microsoft Outlook"})
        result = ensure_window(win32, "Outlook", path="outlook.exe")
        self.assertEqual(result, 0x100)
        win32.shell_execute.assert_not_called()

    def test_not_running_calls_shell_execute(self):
        win32 = self._make_win32({0x100: "Notepad"})
        result = ensure_window(win32, "Outlook", path="outlook.exe")
        win32.shell_execute.assert_called_once_with("outlook.exe")
        self.assertIsNone(result)

    def test_multiple_matches_does_not_launch(self):
        win32 = self._make_win32({
            0x100: "Inbox - Outlook",
            0x200: "Calendar - Outlook",
        })
        result = ensure_window(win32, "Outlook", path="outlook.exe")
        self.assertIn(result, (0x100, 0x200))
        win32.shell_execute.assert_not_called()

    def test_numeric_title_not_treated_as_hwnd(self):
        win32 = self._make_win32({0x100: "Notepad"})
        result = ensure_window(win32, "12345", path="app.exe")
        win32.shell_execute.assert_called_once_with("app.exe")
        self.assertIsNone(result)

    def test_prints_already_running_message_with_process_path(self):
        win32 = self._make_win32({0x100: "Microsoft Outlook"})
        win32.get_process_path.return_value = r"C:\Program Files\Microsoft Office\outlook.exe"
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            ensure_window(win32, "Outlook", path="outlook.exe")
        output = buf.getvalue()
        self.assertIn("Already running", output)
        self.assertIn(r"C:\Program Files\Microsoft Office\outlook.exe", output)

    def test_prints_already_running_without_path_on_failure(self):
        win32 = self._make_win32({0x100: "Microsoft Outlook"})
        win32.get_process_path.return_value = None
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            ensure_window(win32, "Outlook", path="outlook.exe")
        output = buf.getvalue()
        self.assertIn("Already running", output)
        self.assertNotIn("None", output)

    def test_prints_launching_message(self):
        win32 = self._make_win32({})
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            ensure_window(win32, "Outlook", path="outlook.exe")
        self.assertIn("Launching", buf.getvalue())

    def test_prints_warning_on_launch_failure(self):
        win32 = self._make_win32({})
        win32.shell_execute.return_value = 2
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            ensure_window(win32, "Outlook", path="outlook.exe")
        self.assertIn("Warning", buf.getvalue())


class TestEnsureCLI(unittest.TestCase):
    """CLI integration tests for the ensure subcommand."""

    def _make_win32(self, windows=None):
        if windows is None:
            windows = {}
        win32 = MagicMock()

        def fake_enum(callback):
            for hwnd, title in windows.items():
                win32.is_window_visible.return_value = True
                win32.get_window_text.return_value = title
                callback(hwnd)

        win32.enum_windows.side_effect = fake_enum
        win32.is_iconic.return_value = False
        win32.shell_execute.return_value = 42
        return win32

    @patch("wman.Win32API")
    def test_ensure_launches_when_not_found(self, MockWin32API):
        win32 = self._make_win32({0x100: "Notepad"})
        MockWin32API.return_value = win32
        with patch("sys.argv", ["wman.py", "ensure", "Outlook", "--path", "outlook.exe"]):
            buf = io.StringIO()
            with patch("sys.stdout", buf):
                main()
        win32.shell_execute.assert_called_once_with("outlook.exe")

    @patch("wman.Win32API")
    @patch("builtins.input")
    def test_ensure_interactive_not_running_asks_for_path(self, mock_input, MockWin32API):
        """When app is not running, should prompt for path and launch."""
        win32 = self._make_win32({0x100: "Notepad"})
        MockWin32API.return_value = win32
        # choice, title, then path prompt, quit
        mock_input.side_effect = ["4", "Outlook", "outlook.exe", "q"]
        with patch("sys.argv", ["wman.py"]):
            buf = io.StringIO()
            with patch("sys.stdout", buf):
                main()
        win32.shell_execute.assert_called_once_with("outlook.exe")

    @patch("wman.Win32API")
    @patch("builtins.input")
    def test_ensure_interactive_already_running_does_not_ask_for_path(self, mock_input, MockWin32API):
        """When app is already running, should NOT prompt for path."""
        win32 = self._make_win32({0x100: "Microsoft Outlook"})
        win32.get_process_path.return_value = r"C:\Program Files\outlook.exe"
        MockWin32API.return_value = win32
        # Only: choice, title, quit — no path prompt
        mock_input.side_effect = ["4", "Outlook", "q"]
        with patch("sys.argv", ["wman.py"]):
            buf = io.StringIO()
            with patch("sys.stdout", buf):
                main()
        output = buf.getvalue()
        self.assertIn("Already running", output)
        self.assertIn(r"C:\Program Files\outlook.exe", output)
        win32.shell_execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
