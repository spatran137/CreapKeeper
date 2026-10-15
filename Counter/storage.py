"""SQLite-backed event storage for the manual Counter application."""

from __future__ import annotations

import csv
import os
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

KINDS = ("count", "creap")


def database_path(override: str | Path | None = None) -> Path:
    """Use an explicit path, COUNTER_DB_PATH, or a per-user data directory."""
    chosen = override or os.environ.get("COUNTER_DB_PATH")
    if chosen:
        return Path(chosen).expanduser().resolve()
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return base / "Counter" / "Counter.db"
    base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "counter" / "Counter.db"


@contextmanager
def database(path: str | Path | None = None) -> Iterator[sqlite3.Connection]:
    target = database_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(target), timeout=5)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL CHECK (kind IN ('count', 'creap')),
                quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
                occurred_at TEXT NOT NULL,
                source_path TEXT,
                source_rowid INTEGER,
                UNIQUE (source_path, source_rowid, kind)
            )"""
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_time ON events(occurred_at)"
        )
        connection.commit()
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def add_event(kind: str, path: str | Path | None = None) -> int:
    if kind not in KINDS:
        raise ValueError(f"Unsupported kind: {kind!r}")
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with database(path) as connection:
        cursor = connection.execute(
            "INSERT INTO events (kind, occurred_at) VALUES (?, ?)", (kind, stamp)
        )
        return int(cursor.lastrowid)


def totals(path: str | Path | None = None) -> dict[str, int]:
    result = {"count": 0, "creap": 0}
    with database(path) as connection:
        for row in connection.execute(
            "SELECT kind, SUM(quantity) AS total FROM events GROUP BY kind"
        ):
            result[row["kind"]] = int(row["total"])
    return result


def recent_events(
    path: str | Path | None = None, limit: int = 20
) -> list[dict]:
    if not 1 <= limit <= 10000:
        raise ValueError("limit must be between 1 and 10,000")
    with database(path) as connection:
        rows = connection.execute(
            "SELECT id, kind, quantity, occurred_at, source_path "
            "FROM events ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


def undo_last(path: str | Path | None = None) -> str | None:
    """Undo the most recent manually added event, not imported history."""
    with database(path) as connection:
        row = connection.execute(
            "SELECT id, kind FROM events WHERE source_path IS NULL "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        connection.execute("DELETE FROM events WHERE id = ?", (row["id"],))
        return str(row["kind"])


def export_csv(output: str | Path, path: str | Path | None = None) -> int:
    destination = Path(output).expanduser()
    if destination.resolve() == database_path(path):
        raise ValueError("CSV destination cannot be the database file")
    with database(path) as connection:
        rows = connection.execute(
            "SELECT id, kind, quantity, occurred_at, source_path "
            "FROM events ORDER BY id ASC"
        ).fetchall()
        with destination.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow(("id", "kind", "quantity", "occurred_at", "source_path"))
            for row in rows:
                writer.writerow(tuple(row))
        return len(rows)


def _legacy_timestamp(value: object) -> str:
    text = str(value or "").strip()
    for parse in (
        lambda: datetime.strptime(text, "%a %b %d %H:%M:%S %Y"),
        lambda: datetime.fromisoformat(text),
    ):
        try:
            dt = parse()
            if dt.tzinfo is None:
                dt = dt.astimezone()  # Original time.ctime() strings were local time.
            return dt.astimezone(timezone.utc).isoformat(timespec="seconds")
        except ValueError:
            continue
    raise ValueError(f"Unrecognized legacy date: {text!r}")


def import_legacy(
    source: str | Path, path: str | Path | None = None
) -> int:
    """Import tb_count rows once; uniqueness prevents reimport duplicates."""
    legacy_path = Path(source).expanduser().resolve(strict=True)
    if legacy_path == database_path(path):
        raise ValueError("Legacy source and destination must be different files")
    with closing(sqlite3.connect(str(legacy_path))) as source_db:
        exists = source_db.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'tb_count'"
        ).fetchone()
        if not exists:
            raise ValueError("Legacy database does not contain a tb_count table")
        old_rows = source_db.execute(
            'SELECT rowid, "COUNT", "CREAP", "DATE" FROM tb_count'
        ).fetchall()

    prepared = []
    for row_id, direct, stealth, date in old_rows:
        for kind, quantity in (("count", direct), ("creap", stealth)):
            if quantity is None or int(quantity) <= 0:
                continue
            prepared.append(
                (kind, int(quantity), _legacy_timestamp(date), str(legacy_path), row_id)
            )

    with database(path) as destination:
        start = destination.total_changes
        destination.executemany(
            "INSERT OR IGNORE INTO events "
            "(kind, quantity, occurred_at, source_path, source_rowid) "
            "VALUES (?, ?, ?, ?, ?)",
            prepared,
        )
        return destination.total_changes - start
