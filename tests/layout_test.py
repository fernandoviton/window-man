"""Tests for layout persistence — WindowEntry, save_layout, load_layout."""

import os
import tempfile
import unittest

from layout import WindowEntry, load_layout, save_layout


class TestWindowEntry(unittest.TestCase):
    """WindowEntry dataclass should store window title, path, geometry, and optional group."""

    def test_construction_and_fields(self):
        entry = WindowEntry(
            title="Notepad", path=r"C:\Windows\notepad.exe",
            x=100, y=200, width=800, height=600,
        )
        self.assertEqual(entry.title, "Notepad")
        self.assertEqual(entry.path, r"C:\Windows\notepad.exe")
        self.assertEqual(entry.x, 100)
        self.assertEqual(entry.y, 200)
        self.assertEqual(entry.width, 800)
        self.assertEqual(entry.height, 600)
        self.assertIsNone(entry.group)

    def test_path_can_be_none(self):
        entry = WindowEntry(title="Unknown", path=None, x=0, y=0, width=100, height=100)
        self.assertIsNone(entry.path)

    def test_group_tag(self):
        entry = WindowEntry("Code", "code.exe", 0, 0, 960, 1040, group="dev")
        self.assertEqual(entry.group, "dev")

    def test_equality(self):
        a = WindowEntry("A", "a.exe", 0, 0, 100, 100)
        b = WindowEntry("A", "a.exe", 0, 0, 100, 100)
        self.assertEqual(a, b)

    def test_equality_with_group(self):
        a = WindowEntry("A", "a.exe", 0, 0, 100, 100, group="dev")
        b = WindowEntry("A", "a.exe", 0, 0, 100, 100, group="dev")
        self.assertEqual(a, b)

    def test_different_groups_not_equal(self):
        a = WindowEntry("A", "a.exe", 0, 0, 100, 100, group="dev")
        b = WindowEntry("A", "a.exe", 0, 0, 100, 100, group="comms")
        self.assertNotEqual(a, b)


class TestSaveLayout(unittest.TestCase):
    """save_layout should write entries to a YAML file as a flat list."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "layout.yml")

    def tearDown(self):
        if os.path.exists(self.path):
            os.remove(self.path)
        os.rmdir(self.tmpdir)

    def test_save_creates_file(self):
        entries = [WindowEntry("Notepad", "notepad.exe", 0, 0, 800, 600)]
        save_layout(self.path, entries)
        self.assertTrue(os.path.exists(self.path))

    def test_saved_file_is_valid_yaml_list(self):
        import yaml

        entries = [WindowEntry("Notepad", "notepad.exe", 0, 0, 800, 600)]
        save_layout(self.path, entries)
        with open(self.path) as f:
            data = yaml.safe_load(f)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)

    def test_save_multiple_entries(self):
        entries = [
            WindowEntry("Notepad", "notepad.exe", 0, 0, 800, 600),
            WindowEntry("Calculator", "calc.exe", 100, 100, 400, 300),
        ]
        save_layout(self.path, entries)
        result = load_layout(self.path)
        self.assertEqual(len(result), 2)

    def test_save_empty_entries_list(self):
        save_layout(self.path, [])
        result = load_layout(self.path)
        self.assertEqual(result, [])

    def test_save_with_group_tag(self):
        entries = [WindowEntry("Code", "code.exe", 0, 0, 960, 1040, group="dev")]
        save_layout(self.path, entries)
        result = load_layout(self.path)
        self.assertEqual(result[0].group, "dev")


class TestLoadLayout(unittest.TestCase):
    """load_layout should read a YAML file and return list[WindowEntry]."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "layout.yml")

    def tearDown(self):
        if os.path.exists(self.path):
            os.remove(self.path)
        os.rmdir(self.tmpdir)

    def test_missing_file_returns_empty_list(self):
        result = load_layout(os.path.join(self.tmpdir, "nonexistent.yml"))
        self.assertEqual(result, [])

    def test_round_trip(self):
        entries = [
            WindowEntry("Notepad", r"C:\Windows\notepad.exe", 10, 20, 800, 600),
            WindowEntry("Calc", "calc.exe", 100, 200, 400, 300),
        ]
        save_layout(self.path, entries)
        result = load_layout(self.path)
        self.assertEqual(result, entries)

    def test_round_trip_with_none_path(self):
        entries = [WindowEntry("Unknown", None, 0, 0, 100, 100)]
        save_layout(self.path, entries)
        result = load_layout(self.path)
        self.assertIsNone(result[0].path)

    def test_round_trip_with_group(self):
        entries = [
            WindowEntry("Code", "code.exe", 0, 0, 960, 1040, group="dev"),
            WindowEntry("Notepad", "notepad.exe", 0, 0, 800, 600),
        ]
        save_layout(self.path, entries)
        result = load_layout(self.path)
        self.assertEqual(result[0].group, "dev")
        self.assertIsNone(result[1].group)

    def test_special_chars_in_title(self):
        entries = [WindowEntry("File — «test» & <más>", "app.exe", 0, 0, 100, 100)]
        save_layout(self.path, entries)
        result = load_layout(self.path)
        self.assertEqual(result[0].title, "File — «test» & <más>")


class TestMergeBehavior(unittest.TestCase):
    """save_layout should replace entries with matching groups, keep others."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "layout.yml")

    def tearDown(self):
        if os.path.exists(self.path):
            os.remove(self.path)
        os.rmdir(self.tmpdir)

    def test_saving_new_group_preserves_existing(self):
        save_layout(self.path, [WindowEntry("Slack", "slack.exe", 0, 0, 800, 600, group="comms")])
        save_layout(self.path, [WindowEntry("Code", "code.exe", 0, 0, 960, 1040, group="dev")])
        result = load_layout(self.path)
        titles = {e.title for e in result}
        self.assertIn("Slack", titles)
        self.assertIn("Code", titles)
        self.assertEqual(len(result), 2)

    def test_saving_existing_group_replaces_it(self):
        save_layout(self.path, [WindowEntry("Old", "old.exe", 0, 0, 100, 100, group="dev")])
        save_layout(self.path, [WindowEntry("New", "new.exe", 0, 0, 200, 200, group="dev")])
        result = load_layout(self.path)
        dev_entries = [e for e in result if e.group == "dev"]
        self.assertEqual(len(dev_entries), 1)
        self.assertEqual(dev_entries[0].title, "New")

    def test_saving_untagged_replaces_only_untagged(self):
        save_layout(self.path, [WindowEntry("Code", "code.exe", 0, 0, 960, 1040, group="dev")])
        save_layout(self.path, [WindowEntry("Notepad", "notepad.exe", 0, 0, 800, 600)])
        result = load_layout(self.path)
        self.assertEqual(len(result), 2)
        groups = {e.group for e in result}
        self.assertEqual(groups, {"dev", None})


class TestEdgeCases(unittest.TestCase):
    """Edge cases and error handling for layout persistence."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "layout.yml")

    def tearDown(self):
        if os.path.exists(self.path):
            os.remove(self.path)
        os.rmdir(self.tmpdir)

    def test_corrupt_yaml_returns_empty_list(self):
        with open(self.path, "w") as f:
            f.write(":\n  - [invalid\n  yaml: {{{}}")
        result = load_layout(self.path)
        self.assertEqual(result, [])

    def test_save_over_corrupt_yaml_succeeds(self):
        with open(self.path, "w") as f:
            f.write(":\n  - [invalid\n  yaml: {{{}}")
        entries = [WindowEntry("Notepad", "notepad.exe", 0, 0, 800, 600)]
        save_layout(self.path, entries)
        result = load_layout(self.path)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].title, "Notepad")

    def test_empty_yaml_file_returns_empty_list(self):
        with open(self.path, "w") as f:
            f.write("")
        result = load_layout(self.path)
        self.assertEqual(result, [])

    def test_windows_backslash_paths_round_trip(self):
        entries = [WindowEntry("App", r"C:\Program Files\App\app.exe", 0, 0, 800, 600)]
        save_layout(self.path, entries)
        result = load_layout(self.path)
        self.assertEqual(result[0].path, r"C:\Program Files\App\app.exe")

    def test_load_layout_with_yaml_containing_only_scalars_returns_empty(self):
        with open(self.path, "w") as f:
            f.write("just a string\n")
        result = load_layout(self.path)
        self.assertEqual(result, [])


class TestReplaceAll(unittest.TestCase):
    """save_layout with replace_all=True should replace ALL entries regardless of group."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "layout.yml")

    def tearDown(self):
        if os.path.exists(self.path):
            os.remove(self.path)
        os.rmdir(self.tmpdir)

    def test_replace_all_removes_every_existing_entry(self):
        save_layout(self.path, [
            WindowEntry("Code", "code.exe", 0, 0, 960, 1040, group="dev"),
            WindowEntry("Slack", "slack.exe", 0, 0, 960, 1040, group="comms"),
        ])
        save_layout(self.path, [
            WindowEntry("Notepad", "notepad.exe", 0, 0, 800, 600),
        ], replace_all=True)
        result = load_layout(self.path)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].title, "Notepad")

    def test_replace_all_on_empty_file(self):
        save_layout(self.path, [
            WindowEntry("Notepad", "notepad.exe", 0, 0, 800, 600),
        ], replace_all=True)
        result = load_layout(self.path)
        self.assertEqual(len(result), 1)

    def test_replace_all_with_mixed_groups(self):
        save_layout(self.path, [
            WindowEntry("Code", "code.exe", 0, 0, 960, 1040, group="dev"),
            WindowEntry("Slack", "slack.exe", 0, 0, 960, 1040, group="comms"),
            WindowEntry("Notepad", "notepad.exe", 0, 0, 800, 600),
        ])
        save_layout(self.path, [
            WindowEntry("NewApp", "new.exe", 100, 100, 500, 400, group="dev"),
        ], replace_all=True)
        result = load_layout(self.path)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].title, "NewApp")


if __name__ == "__main__":
    unittest.main()
