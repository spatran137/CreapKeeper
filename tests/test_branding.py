"""The name is new; Count, Creap and stored histories are not."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Counter"))

from storage import database_path, add_event, totals


class BrandingTests(unittest.TestCase):
    def test_old_database_env_variable_remains_supported(self):
        import tempfile
        with tempfile.TemporaryDirectory() as location:
            db = Path(location) / "Counter.db"
            with patch.dict("os.environ", {"COUNTER_DB_PATH": str(db)}):
                add_event("count")
                add_event("creap")
                self.assertEqual(database_path(), db.resolve())
                self.assertEqual(totals(), {"count": 1, "creap": 1})

    def test_existing_legacy_scripts_and_new_launcher_present(self):
        # The new entry point is additive; do not break old launch shortcuts.
        for filename in ("Counter.py", "CreapKeeper.py", "count.py", "creap.py"):
            self.assertTrue((ROOT / "Counter" / filename).is_file(), filename)

    def test_dashboard_name_changed_without_changing_data_route(self):
        page = (ROOT / "Counter" / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn("The Creap Report", page)
        self.assertIn("CreapKeeper", page)
        self.assertIn('fetch("/counts.json"', page)


if __name__ == "__main__":
    unittest.main()
