"""Persistent, per-user desktop options. Never stored inside the executable."""

from __future__ import annotations

import json
import os
from pathlib import Path

from storage import database_path

DEFAULTS = {
    "global_hotkeys": os.name == "nt",
    "system_tray": os.name == "nt",
    "lan_dashboard": False,  # Never expose network service without opting in.
    "auto_updates": os.name == "nt",  # User can opt out of GitHub checks.
}


def settings_path(db_path: str | Path | None = None) -> Path:
    return database_path(db_path).with_name("settings.json")


def load_settings(path: str | Path | None = None) -> dict[str, bool]:
    values = DEFAULTS.copy()
    location = Path(path) if path is not None else settings_path()
    try:
        data = json.loads(location.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            for key in DEFAULTS:
                if isinstance(data.get(key), bool):
                    values[key] = data[key]
    except (FileNotFoundError, ValueError, OSError):
        pass
    return values


def save_settings(values: dict[str, bool], path: str | Path | None = None) -> None:
    location = Path(path) if path is not None else settings_path()
    location.parent.mkdir(parents=True, exist_ok=True)
    validated = {
        key: values[key] if isinstance(values.get(key), bool) else DEFAULTS[key]
        for key in DEFAULTS
    }
    temporary = location.with_name(location.name + ".tmp")
    try:
        temporary.write_text(json.dumps(validated, indent=2) + "\n", encoding="utf-8")
        temporary.replace(location)
    finally:
        temporary.unlink(missing_ok=True)
