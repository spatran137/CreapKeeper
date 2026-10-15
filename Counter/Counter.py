#!/usr/bin/env python3
"""Counter GUI: manual event tracking with opt-in background controls."""

import argparse
import os
import queue
import sqlite3
import webbrowser
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

from dashboard import DashboardServer
from global_hotkeys import GlobalHotkeys
from preferences import load_settings, save_settings, settings_path
from storage import add_event, database_path, export_csv, import_legacy, recent_events, totals, undo_last
from system_tray import SystemTray


class CounterApp(ttk.Frame):
    def __init__(self, master: tk.Tk, db_path: str | None = None) -> None:
        super().__init__(master, padding=16)
        self.db_path = db_path
        self.master = master
        self._events = queue.Queue()
        self._hotkeys = GlobalHotkeys(self._events)
        self._tray = SystemTray(self._events)
        self._dashboard = DashboardServer(db_path)
        self._closed = False
        self._settings_file = settings_path(db_path)
        self._settings = load_settings(self._settings_file)
        self.hotkeys_enabled = tk.BooleanVar(value=self._settings["global_hotkeys"])
        self.tray_enabled = tk.BooleanVar(value=self._settings["system_tray"])
        self.dashboard_enabled = tk.BooleanVar(value=self._settings["lan_dashboard"])
        self.dashboard_address = tk.StringVar(value="LAN dashboard off")

        master.title("Counter - Office Encounter Tracker")
        master.minsize(650, 600)
        self.pack(fill="both", expand=True)

        ttk.Label(self, text="Office Encounter Tracker", font=("Segoe UI", 17, "bold")).pack(anchor="w")
        ttk.Label(
            self, text="Two ways to interrupt someone. One very unofficial scoreboard."
        ).pack(anchor="w", pady=(3, 12))

        buttons = ttk.Frame(self)
        buttons.pack(fill="x")
        self.direct_total = tk.StringVar(value="0")
        self.stealth_total = tk.StringVar(value="0")
        for label, group_name, variable, kind, margin in (
            ("Count", "Direct approach", self.direct_total, "count", (0, 6)),
            ("Creap", "Stealth approach", self.stealth_total, "creap", (6, 0)),
        ):
            group = ttk.LabelFrame(buttons, text=group_name, padding=12)
            group.pack(side="left", fill="both", expand=True, padx=margin)
            ttk.Label(group, textvariable=variable, font=("Segoe UI", 25, "bold")).pack()
            ttk.Button(
                group, text=f"+1 {label}", command=lambda value=kind: self.record(value)
            ).pack(fill="x", pady=(4, 0))

        self.overall = tk.StringVar()
        ttk.Label(self, textvariable=self.overall, font=("Segoe UI", 11, "bold")).pack(
            anchor="w", pady=(12, 7)
        )
        tools = ttk.Frame(self)
        tools.pack(fill="x", pady=(0, 9))
        ttk.Button(tools, text="Undo last click", command=self.undo).pack(side="left", padx=(0, 7))
        ttk.Button(tools, text="Export CSV", command=self.export).pack(side="left", padx=(0, 7))
        ttk.Button(tools, text="Import old DB", command=self.import_old).pack(side="left")

        ttk.Label(self, text="Recent encounters").pack(anchor="w")
        self.history = ttk.Treeview(
            self, columns=("when", "kind", "quantity", "source"), show="headings", height=7
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

        settings = ttk.LabelFrame(self, text="Background controls", padding=9)
        settings.pack(fill="x", pady=(3, 7))
        hotkey_check = ttk.Checkbutton(
            settings, text="Global: Ctrl+Alt+1 (Count), Ctrl+Alt+2 (Creap), Ctrl+Alt+Z (Undo)",
            variable=self.hotkeys_enabled, command=self.configure_background,
        )
        hotkey_check.pack(anchor="w")
        tray_check = ttk.Checkbutton(
            settings, text="Show system tray icon; close the window to hide it",
            variable=self.tray_enabled, command=self.configure_background,
        )
        tray_check.pack(anchor="w")
        if os.name != "nt":
            hotkey_check.configure(state="disabled")
            tray_check.configure(state="disabled")
        dashboard_check = ttk.Checkbutton(
            settings,
            text="Share read-only chart on local LAN (HTTP port 8765)",
            variable=self.dashboard_enabled,
            command=self.configure_background,
        )
        dashboard_check.pack(anchor="w", pady=(7, 0))
        ttk.Label(
            settings, textvariable=self.dashboard_address, wraplength=590
        ).pack(anchor="w", padx=(22, 0), pady=(1, 4))
        tools_row = ttk.Frame(settings)
        tools_row.pack(fill="x")
        ttk.Button(
            tools_row, text="Open dashboard", command=self.open_dashboard
        ).pack(side="left")
        ttk.Button(
            tools_row, text="Copy LAN link", command=self.copy_dashboard_link
        ).pack(side="left", padx=8)
        ttk.Button(
            tools_row, text="Hide to tray", command=self.hide_to_tray
        ).pack(side="right")

        self.status = tk.StringVar(value=f"Database: {database_path(db_path)}")
        ttk.Label(self, textvariable=self.status, wraplength=580).pack(anchor="w")

        # Legacy shortcuts continue to work when this window is focused.
        # Do not also fire them for Ctrl+Alt shortcuts handled by RegisterHotKey.
        master.bind("<Control-1>", lambda e: self.record("count") if not e.state & 0x0008 else None)
        master.bind("<Control-2>", lambda e: self.record("creap") if not e.state & 0x0008 else None)
        master.bind("<Control-z>", lambda e: self.undo() if not e.state & 0x0008 else None)
        master.protocol("WM_DELETE_WINDOW", self.on_close)
        self.refresh()
        self.configure_background(startup=True)
        self._poll_job = master.after(75, self._drain_events)

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
            filetypes=[("CSV files", "*.csv")], title="Export encounter history",
        )
        if filename:
            def work() -> None:
                count = export_csv(filename, self.db_path)
                self.status.set(f"Exported {count} rows to {filename}")
            self._handle(work)

    def import_old(self) -> None:
        filename = filedialog.askopenfilename(
            parent=self.master, filetypes=[("SQLite databases", "*.db *.sqlite *.*")],
            title="Select original Counter.db",
        )
        if filename:
            def work() -> None:
                count = import_legacy(filename, self.db_path)
                self.refresh()
                self.status.set(f"Imported {count} legacy records (duplicates skipped).")
            self._handle(work)

    def configure_background(self, startup: bool = False) -> None:
        """Apply and persist only successfully activated user preferences."""
        feedback = []
        if self.hotkeys_enabled.get():
            ok, result = self._hotkeys.start()
            if not ok:
                self.hotkeys_enabled.set(False)
                feedback.append(result)
            elif not startup:
                feedback.append(result)
        else:
            self._hotkeys.stop()

        if self.tray_enabled.get():
            if os.name != "nt":
                self.tray_enabled.set(False)
                feedback.append("System tray is currently Windows-only.")
            else:
                ok, result = self._tray.start()
                if not ok:
                    self.tray_enabled.set(False)
                    feedback.append(result)
                elif not startup:
                    feedback.append(result)
        else:
            self._tray.stop()

        if self.dashboard_enabled.get():
            ok, result = self._dashboard.start()
            if not ok:
                self.dashboard_enabled.set(False)
                feedback.append(result)
                self.dashboard_address.set("LAN dashboard off")
            else:
                self.dashboard_address.set(
                    "LAN address: " + self._dashboard.share_url +
                    " (use your PC IPv4 address if its name does not resolve)"
                )
                if not startup:
                    feedback.append(result)
        else:
            self._dashboard.stop()
            self.dashboard_address.set("LAN dashboard off")

        effective = {
            "global_hotkeys": self.hotkeys_enabled.get(),
            "system_tray": self.tray_enabled.get(),
            "lan_dashboard": self.dashboard_enabled.get(),
        }
        if effective != self._settings:
            try:
                save_settings(effective, self._settings_file)
                self._settings = effective
            except OSError as exc:
                feedback.append(f"Could not save settings: {exc}")
        if feedback:
            self.status.set("  ".join(feedback))

    def open_dashboard(self) -> None:
        if self._dashboard.running:
            webbrowser.open(self._dashboard.local_url)
        else:
            self.status.set("Enable LAN dashboard first.")

    def copy_dashboard_link(self) -> None:
        if self._dashboard.running:
            self.master.clipboard_clear()
            self.master.clipboard_append(self._dashboard.share_url)
            self.status.set("Copied LAN dashboard link to clipboard.")
        else:
            self.status.set("Enable LAN dashboard first.")

    def _drain_events(self) -> None:
        """Receive hotkeys/tray menu clicks only on the Tk main thread."""
        if self._closed:
            return
        for _ in range(50):
            try:
                action = self._events.get_nowait()
            except queue.Empty:
                break
            if action in ("count", "creap"):
                self.record(action)
            elif action == "undo":
                self.undo()
            elif action == "show":
                self.master.deiconify()
                self.master.lift()
            elif action == "exit":
                self.exit_app()
                return
            elif action == "tray-error":
                self.tray_enabled.set(False)
                self.configure_background()
                self.status.set("System tray stopped unexpectedly.")
        self._poll_job = self.master.after(75, self._drain_events)

    def hide_to_tray(self) -> None:
        if self.tray_enabled.get() and self._tray.running:
            self.master.withdraw()
        else:
            self.status.set("Enable the tray icon before hiding the window.")

    def on_close(self) -> None:
        """Close-to-tray if enabled, otherwise exit."""
        if self.tray_enabled.get() and self._tray.running:
            self.hide_to_tray()
        else:
            self.exit_app()

    def exit_app(self) -> None:
        if self._closed:
            return
        self._closed = True
        if hasattr(self, "_poll_job"):
            self.master.after_cancel(self._poll_job)
        self._hotkeys.stop()
        self._dashboard.stop()
        self._tray.stop()
        self.master.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(description="Counter desktop interface")
    parser.add_argument("--db", help="Override database location")
    args = parser.parse_args()
    root = tk.Tk()
    CounterApp(root, args.db)
    root.mainloop()


if __name__ == "__main__":
    main()
