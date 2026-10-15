# Counter — Office Encounter Tracker

A tiny, slightly ridiculous utility for keeping score when a coworker interrupts your desk. The project started in **2017**, inspired by a colleague with two very distinct habits:

- **Count (direct):** walking over to ask a question, whether it had anything to do with work or IT.
- **Creap (stealth):** silently approaching and standing behind someone until they notice.

The spelling **Creap** is deliberately preserved from the original scripts. This application tracks manual button presses, **not people**. No cameras, microphones, surveillance, networking, or automated detection are involved.

## What's new

- Python 3 desktop GUI with two buttons and running totals
- Date/time-stamped SQLite history
- Undo for accidental manual clicks
- CSV export and idempotent import of the old 2017 database format
- Headless command-line interface for shortcuts and scripts
- Automatic database creation, data validation, and standard-library tests

## Requirements

- **Python 3.10+**; no pip dependencies
- GUI: Tkinter (included with the standard Windows Python installer; on some Linux systems install python3-tk)
- Windows, Linux, or macOS

## Run the desktop application

From the repository root:

    python Counter/Counter.py

Click **+1 Count** for a direct interruption, or **+1 Creap** for a stealth encounter.

Keyboard shortcuts: **Ctrl+1** (Count), **Ctrl+2** (Creap), **Ctrl+Z** (Undo).

The GUI shows totals and 20 recent entries. **Undo last click** removes only the most recent manually recorded event. Imported history is left untouched.

## Command-line usage

The original one-shot entry points are preserved:

    python Counter/count.py
    python Counter/creap.py

Or use the consolidated interface:

    python Counter/cli.py count
    python Counter/cli.py creap
    python Counter/cli.py stats
    python Counter/cli.py history --limit 10
    python Counter/cli.py undo
    python Counter/cli.py export encounters.csv

To choose a specific database, add **--db PATH** after a command:

    python Counter/cli.py stats --db C:\Temp\Counter.db
    python Counter/Counter.py --db C:\Temp\Counter.db

You can also set the **COUNTER_DB_PATH** environment variable to a file path. That setting works with the GUI, CLI, and original scripts.

## Where data lives

By default, the SQLite file is stored outside your Git checkout:

| System | Default |
| --- | --- |
| Windows | %LOCALAPPDATA%\Counter\Counter.db |
| Linux | ~/.local/share/counter/Counter.db |
| macOS | ~/.local/share/counter/Counter.db |

On Linux, XDG_DATA_HOME is respected. The application doesn't connect to the network or share its data.

## Import your original 2017 database

The old scripts wrote a local Counter.db with a tb_count table containing COUNT, CREAP, and DATE columns.

**Make a backup** of your original database first. Then import it:

    python Counter/cli.py import-legacy "C:\path\to\old\Counter.db"

Or select **Import old DB** in the GUI. The importer reads the old database without changing it, retains per-row quantities and timestamps, and skips previously imported rows when you run it again with the same source path.

Historical time.ctime() timestamps are interpreted using the computer's current local time zone. If the logs were captured in a different time zone, account for that before importing.

You can also choose the new destination explicitly:

    python Counter/cli.py import-legacy "C:\old\Counter.db" --db "C:\new\Counter.db"

## Tests

From the repository root:

    python -m unittest discover -s tests -v

The automated tests cover data creation, counts, undo, CSV export, legacy import, environment configuration, and basic CLI operation. The desktop UI additionally requires a manual smoke test.

## Original project

The Visual Studio solution (Counter.sln) and Python project are retained. A normal terminal is sufficient to run the app.

This is intended as a good-natured personal counter; avoid adding names or using it to single out coworkers.
