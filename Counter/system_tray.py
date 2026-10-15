"""Optional Windows desktop notification-area icon using pystray/Pillow."""

from __future__ import annotations

import queue
import threading


class SystemTray:
    def __init__(self, events: queue.Queue[str]) -> None:
        self.events = events
        self._icon = None
        self._thread: threading.Thread | None = None
        self.error: str | None = None

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> tuple[bool, str]:
        if self.running:
            return True, "System tray icon active."
        if self._thread and self._thread.is_alive():
            return False, "System tray is still stopping."
        try:
            import pystray
            from PIL import Image, ImageDraw
        except ImportError:
            return False, "Tray support needs pystray and Pillow. Install requirements-gui.txt."

        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((3, 3, 60, 60), radius=14, fill="#243147")
        draw.text((17, 20), "CK", fill="#F0FAFF", stroke_width=1)

        def publish(action: str):
            return lambda icon, item: self.events.put(action)

        menu = pystray.Menu(
            pystray.MenuItem("Show CreapKeeper", publish("show"), default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("+1 Count (direct)", publish("count")),
            pystray.MenuItem("+1 Creap (stealth)", publish("creap")),
            pystray.MenuItem("Undo last click", publish("undo")),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit CreapKeeper", publish("exit")),
        )
        self.error = None
        self._icon = pystray.Icon("CreapKeeper", image, "CreapKeeper — Office Encounter Tracker", menu)
        self._thread = threading.Thread(
            target=self._run, name="CreapKeeperTray", daemon=True
        )
        self._thread.start()
        return True, "System tray enabled. Close the window to hide it; use the tray menu to reopen."

    def _run(self) -> None:
        try:
            self._icon.run()
        except Exception as exc:
            self.error = str(exc)
            self.events.put("tray-error")

    def stop(self) -> None:
        icon, thread = self._icon, self._thread
        if icon is not None:
            try:
                icon.stop()
            except RuntimeError:
                pass
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=3)
        self._icon = None
        self._thread = None
