#!/usr/bin/env python3
"""Small desktop GUI for recording two kinds of office interruptions."""

import argparse
import sqlite3
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

from storage import add_event, database_path, export_csv, import_legacy, recent_events, totals, undo_last


class CounterApp(ttk.Frame):
    def __init__(self, master: tk.Tk, db_path: str | None = None) -> None:
        super().__init__(master, padding=18)
        self.db_path = db_path
        self.master = master
        self.master.title("Counter - Office Encounter Tracker")
        self.master.minsize(560, 420)
        self.pack(fill="both", expand=True)

        ttk.Label(self, text="Office Encounter Tracker", font=("Segoe UI", 17, "bold")).pack(anchor="w")
        ttk.Label(
            self,
            text="Two ways to interrupt someone. One very unofficial scoreboard.",
        ).pack(anchor="w", pady=(3, 14))

        buttons = ttk.Frame(self)
        buttons.pack(fill="x")
        left = ttk.LabelFrame(buttons, text="Direct approach", padding=12)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        right = ttk.LabelFrame(buttons, text="Stealth approach", padding=12)
        right.pack(side="left", fill="both", expand=True, padx=(6, 0))

        self.direct_total = tk.StringVar(value="0")
        self.stealth_total = tk.StringVar(value="0")
        for group, label, variable, kind in (
            (left, "Count", self.direct_total, "count"),
            (right, "Creap", self.stealth_total, "creap"),
        ):
            ttk.Label(group, textvariable=variable, font=("Segoe UI", 25, "bold")).pack()
            ttk.Button(
                group, text=f"+1 {label}", command=lambda value=kind: self.record(value)
            ).pack(fill="x", pady=(4, 0))

        self.overall = tk.StringVar()
        ttk.Label(self, textvariable=self.overall, font=("Segoe UI", 11, "bold")).pack(
            anchor="w", pady=(14, 7)
        )
        tools = ttk.Frame(self)
        tools.pack(fill="x", pady=(0, 10))
        ttk.Button(tools, text="Undo last click", command=self.undo).pack(side="left", padx=(0, 7))
        ttk.Button(tools, text="Export CSV", command=self.export).pack(side="left", padx=(0, 7))
        ttk.Button(tools, text="Import old DB", command=self.import_old).pack(side="left")

        ttk.Label(self, text="Recent encounters").pack(anchor="w")
        self.history = ttk.Treeview(
            self, columns=("when", "kind", "quantity", "source"), show="headings", height=8
        )
        for name, title, width in (
            ("when", "Date / Time", 175),
            ("kind", "Approach", 110),
            ("quantity", "Count", 55),
            ("source", "Source", 90),
        ):
            self.history.heading(name, text=title)
            self.history.column(name, width=width, stretch=(name == "when"))
        self.history.pack(fill="both", expand=True, pady=(3, 8))

        self.status = tk.StringVar(value=f"Database: {database_path(db_path)}")
        ttk.Label(self, textvariable=self.status, wraplength=510).pack(anchor="w")
        master.bind("<Control-1>", lambda _: self.record("count"))
        master.bind("<Control-2>", lambda _: self.record("creap"))
        master.bind("<Control-z>", lambda _: self.undo())
        self.refresh()

    def _handle(self, action) -> None:
        try:
            action()
        except (OSError, sqlite3.Error, ValueError) as exc:
            messagebox.showerror("Counter error", str(exc), parent=self.master)

    def refresh(self) -> None:
        def work() -> None:
            values = totals(self.db_path)
            self.direct_total.set(str(values["count"]))
            self.stealth_total.set(str(values["creap"]))
            self.overall.set(f"Total encounters: {sum(values.values())}")
            for item in self.history.get_children():
                self.history.delete(item)
            for event in recent_events(self.db_path):
                local = datetime.fromisoformat(event["occurred_at"]).astimezone()
                self.history.insert("", "end", values=(
                    local.strftime("%Y-%m-%d %H:%M:%S"),
                    "Direct" if event["kind"] == "count" else "Stealth",
                    event["quantity"],
                    "Imported" if event["source_path"] else "Manual",
                ))
        self._handle(work)

    def record(self, kind: str) -> None:
        def work() -> None:
            add_event(kind, self.db_path)
            self.refresh()
            self.status.set(f"Recorded {'direct' if kind == 'count' else 'stealth'} encounter.")
        self._handle(work)

    def undo(self) -> None:
        def work() -> None:
            kind = undo_last(self.db_path)
            self.refresh()
            self.status.set(f"Undid {kind} encounter." if kind else "No manual clicks to undo.")
        self._handle(work)

    def export(self) -> None:
        filename = filedialog.asksaveasfilename(
            parent=self.master, defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")], title="Export encounter history"
        )
        if filename:
            def work() -> None:
                count = export_csv(filename, self.db_path)
                self.status.set(f"Exported {count} rows to {filename}")
            self._handle(work)

    def import_old(self) -> None:
        filename = filedialog.askopenfilename(
            parent=self.master, filetypes=[("SQLite databases", "*.db *.sqlite *.*")],
            title="Select original Counter.db"
        )
        if filename:
            def work() -> None:
                count = import_legacy(filename, self.db_path)
                self.refresh()
                self.status.set(f"Imported {count} legacy records (duplicates skipped).")
            self._handle(work)


def main() -> None:
    parser = argparse.ArgumentParser(description="Counter desktop interface")
    parser.add_argument("--db", help="Override database location")
    args = parser.parse_args()
    root = tk.Tk()
    CounterApp(root, args.db)
    root.mainloop()


if __name__ == "__main__":
    main()
