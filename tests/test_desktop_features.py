"""Regression tests that do not need an interactive desktop."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Counter"))

from global_hotkeys import GlobalHotkeys, SHORTCUTS, hotkey_action
from preferences import DEFAULTS, load_settings, save_settings, settings_path
from queue import Queue


class PreferencesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.file = Path(self.tmp.name) / "sub" / "settings.json"

    def test_default_preferences(self):
        self.assertEqual(load_settings(self.file), DEFAULTS)

    def test_roundtrip_and_boolean_validation(self):
        save_settings({"global_hotkeys": True, "system_tray": False}, self.file)
        self.assertEqual(
            load_settings(self.file),
            {"global_hotkeys": True, "system_tray": False},
        )
        self.assertEqual(
            json.loads(self.file.read_text(encoding="utf-8"))["system_tray"], False
        )
        self.file.write_text(
            '{"global_hotkeys":"not a bool","system_tray":true}', encoding="utf-8"
        )
        result = load_settings(self.file)
        self.assertEqual(result["global_hotkeys"], DEFAULTS["global_hotkeys"])
        self.assertTrue(result["system_tray"])

    def test_corrupt_json_falls_back_to_defaults(self):
        self.file.parent.mkdir(parents=True)
        self.file.write_text("not json", encoding="utf-8")
        self.assertEqual(load_settings(self.file), DEFAULTS)

    def test_settings_path_tracks_selected_database(self):
        with patch.dict(os.environ, {"COUNTER_DB_PATH": ""}):
            db = Path(self.tmp.name) / "data" / "manual.db"
            self.assertEqual(settings_path(db), db.with_name("settings.json").resolve())


class HotkeyTests(unittest.TestCase):
    def test_hotkey_id_mapping(self):
        self.assertEqual(set(SHORTCUTS), {101, 102, 103})
        self.assertEqual(hotkey_action(101), "count")
        self.assertEqual(hotkey_action(102), "creap")
        self.assertEqual(hotkey_action(103), "undo")
        self.assertIsNone(hotkey_action(999))

    @unittest.skipIf(os.name == "nt", "Windows requires an interactive message session")
    def test_nonwindows_hotkeys_rejected_without_hooks(self):
        hotkeys = GlobalHotkeys(Queue())
        ok, result = hotkeys.start()
        self.assertFalse(ok)
        self.assertIn("Windows", result)
        self.assertFalse(hotkeys.running)
        hotkeys.stop()


if __name__ == "__main__":
    unittest.main()
