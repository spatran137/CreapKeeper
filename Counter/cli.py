#!/usr/bin/env python3
"""Command-line interface for CreapKeeper; works without a graphical desktop."""

import argparse
import sqlite3
from datetime import datetime

from storage import add_event, export_csv, import_legacy, recent_events, totals, undo_last


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Track direct and stealth office encounters")
    commands = parser.add_subparsers(dest="command", required=True)
    for action in ("count", "creap", "stats", "history", "undo", "export", "import-legacy"):
        sub = commands.add_parser(action)
        sub.add_argument("--db", help="Database path (also accepts COUNTER_DB_PATH)")
        if action == "history":
            sub.add_argument("--limit", type=int, default=20, help="Most recent entries")
        if action in ("export", "import-legacy"):
            sub.add_argument("file", help="CSV output path or legacy SQLite database")
    args = parser.parse_args(argv)
    try:
        if args.command in ("count", "creap"):
            add_event(args.command, args.db)
            print(f"Recorded {args.command} encounter.")
        elif args.command == "stats":
            values = totals(args.db)
            print(f"Direct: {values['count']} | Stealth: {values['creap']} | Total: {sum(values.values())}")
        elif args.command == "history":
            for event in recent_events(args.db, args.limit):
                local = datetime.fromisoformat(event["occurred_at"]).astimezone()
                print(f"{local:%Y-%m-%d %H:%M:%S}  {event['kind']:<5} x{event['quantity']}")
        elif args.command == "undo":
            kind = undo_last(args.db)
            print(f"Undid {kind} encounter." if kind else "No manual encounters to undo.")
        elif args.command == "export":
            count = export_csv(args.file, args.db)
            print(f"Exported {count} records to {args.file}")
        else:
            count = import_legacy(args.file, args.db)
            print(f"Imported {count} legacy records (existing ones skipped).")
    except (OSError, sqlite3.Error, ValueError) as exc:
        parser.exit(1, f"CreapKeeper error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
