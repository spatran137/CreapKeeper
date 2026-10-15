"""Standard-library regression tests for the Counter event store."""

import csv
import io
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Counter"))

from cli import main as cli_main  # noqa: E402
from storage import (  # noqa: E402
    add_event,
    database_path,
    export_csv,
    import_legacy,
    recent_events,
    totals,
    undo_last,
)


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.db = self.folder / "nested" / "Counter.db"

    def test_first_run_creates_database_and_empty_totals(self):
        self.assertEqual(totals(self.db), {"count": 0, "creap": 0})
        self.assertTrue(self.db.is_file())

    def test_record_count_stealth_and_history(self):
        first = add_event("count", self.db)
        add_event("creap", self.db)
        add_event("count", self.db)
        self.assertEqual(totals(self.db), {"count": 2, "creap": 1})
        self.assertEqual([row["kind"] for row in recent_events(self.db)], ["count", "creap", "count"])
        self.assertEqual(recent_events(self.db)[-1]["id"], first)

    def test_undo_and_invalid_kind(self):
        with self.assertRaises(ValueError):
            add_event("other", self.db)
        self.assertIsNone(undo_last(self.db))
        add_event("count", self.db)
        add_event("creap", self.db)
        self.assertEqual(undo_last(self.db), "creap")
        self.assertEqual(totals(self.db), {"count": 1, "creap": 0})

    def test_export_csv(self):
        add_event("count", self.db)
        output = self.folder / "history.csv"
        self.assertEqual(export_csv(output, self.db), 1)
        with output.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["kind"], "count")
        with self.assertRaises(ValueError):
            export_csv(self.db, self.db)

    def test_import_legacy_is_idempotent_and_preserves_counts(self):
        legacy = self.folder / "old.db"
        with closing(sqlite3.connect(legacy)) as connection:
            connection.execute('CREATE TABLE tb_count ("COUNT" INTEGER, "CREAP" INTEGER, "DATE" TEXT)')
            connection.executemany(
                'INSERT INTO tb_count ("COUNT", "CREAP", "DATE") VALUES (?, ?, ?)',
                [
                    (1, None, "Tue Dec 12 12:00:00 2017"),
                    (None, 1, "Tue Dec 12 12:05:00 2017"),
                    (3, None, "Tue Dec 12 12:10:00 2017"),
                ],
            )
            connection.commit()
        self.assertEqual(import_legacy(legacy, self.db), 3)
        self.assertEqual(import_legacy(legacy, self.db), 0)
        self.assertEqual(totals(self.db), {"count": 4, "creap": 1})
        self.assertIsNone(undo_last(self.db))
        add_event("count", self.db)
        self.assertEqual(undo_last(self.db), "count")
        self.assertEqual(totals(self.db), {"count": 4, "creap": 1})

    def test_import_requires_correct_table_and_separate_file(self):
        self.assertEqual(totals(self.db)["count"], 0)
        with self.assertRaises(ValueError):
            import_legacy(self.db, self.db)
        other = self.folder / "empty.db"
        with closing(sqlite3.connect(other)):
            pass
        with self.assertRaises(ValueError):
            import_legacy(other, self.db)

    def test_database_path_override_and_environment(self):
        with patch.dict(os.environ, {"COUNTER_DB_PATH": str(self.db)}):
            self.assertEqual(database_path(), self.db.resolve())
        self.assertEqual(database_path(self.folder / "other.db"), (self.folder / "other.db").resolve())

    def test_cli_compatibility(self):
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(cli_main(["count", "--db", str(self.db)]), 0)
            self.assertEqual(cli_main(["creap", "--db", str(self.db)]), 0)
            self.assertEqual(cli_main(["stats", "--db", str(self.db)]), 0)
        self.assertIn("Direct: 1 | Stealth: 1 | Total: 2", output.getvalue())


if __name__ == "__main__":
    unittest.main()
