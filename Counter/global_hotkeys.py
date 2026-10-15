"""Windows-wide keyboard shortcuts using RegisterHotKey, not a keylogger.

Runs a Win32 message pump on its own thread and publishes action names to a
thread-safe Queue. It never reads typed text or touches Tk from that thread.
"""

from __future__ import annotations

import ctypes
import os
import queue
import threading
from ctypes import wintypes

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
PM_NOREMOVE = 0x0000

SHORTCUTS = {
    101: ("count", ord("1")),
    102: ("creap", ord("2")),
    103: ("undo", ord("Z")),
}


def hotkey_action(hotkey_id: int) -> str | None:
    item = SHORTCUTS.get(hotkey_id)
    return item[0] if item else None


class GlobalHotkeys:
    """Owns Win32 hotkey registrations; all callbacks are delivered via Queue."""

    def __init__(self, events: queue.Queue[str]) -> None:
        self.events = events
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._ready = threading.Event()
        self._error: str | None = None
        self._registered: set[int] = set()

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and self._registered)

    def start(self) -> tuple[bool, str]:
        if os.name != "nt":
            return False, "Global keyboard shortcuts are currently supported on Windows only."
        if self.running:
            return True, "Global shortcuts active (Ctrl+Alt+1 / 2 / Z)."
        if self._thread and self._thread.is_alive():
            return False, "Hotkey listener is still shutting down."
        self._ready.clear()
        self._error = None
        self._registered = set()
        self._thread = threading.Thread(
            target=self._listen, daemon=True, name="CreapKeeperGlobalHotkeys"
        )
        self._thread.start()
        if not self._ready.wait(timeout=5):
            self.stop()
            return False, "Timed out registering Windows keyboard shortcuts."
        if self._error:
            return False, self._error
        return True, "Global shortcuts active (Ctrl+Alt+1 / 2 / Z)."

    def _listen(self) -> None:
        registered = set()
        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            user32.RegisterHotKey.argtypes = [
                wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT
            ]
            user32.RegisterHotKey.restype = wintypes.BOOL
            user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
            user32.UnregisterHotKey.restype = wintypes.BOOL
            user32.PeekMessageW.argtypes = [
                ctypes.POINTER(wintypes.MSG), wintypes.HWND,
                wintypes.UINT, wintypes.UINT, wintypes.UINT
            ]
            user32.PeekMessageW.restype = wintypes.BOOL
            user32.GetMessageW.argtypes = [
                ctypes.POINTER(wintypes.MSG), wintypes.HWND,
                wintypes.UINT, wintypes.UINT
            ]
            user32.GetMessageW.restype = ctypes.c_int
            kernel32.GetCurrentThreadId.restype = wintypes.DWORD
            self._thread_id = kernel32.GetCurrentThreadId()
            message = wintypes.MSG()
            # Ensure this thread has a message queue before start() can call stop().
            user32.PeekMessageW(ctypes.byref(message), None, 0, 0, PM_NOREMOVE)

            for identifier, (name, virtual_key) in SHORTCUTS.items():
                ok = user32.RegisterHotKey(
                    None, identifier, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, virtual_key
                )
                if not ok:
                    error_code = ctypes.get_last_error()
                    raise OSError(
                        f"Could not register Ctrl+Alt+{'1' if name == 'count' else '2' if name == 'creap' else 'Z'} "
                        f"(Windows error {error_code}); another app may own that shortcut."
                    )
                registered.add(identifier)
            self._registered = registered.copy()
            self._ready.set()

            while True:
                result = user32.GetMessageW(ctypes.byref(message), None, 0, 0)
                if result <= 0:  # WM_QUIT or message-loop error
                    break
                if message.message == WM_HOTKEY:
                    action = hotkey_action(int(message.wParam))
                    if action:
                        self.events.put(action)
        except (OSError, AttributeError) as exc:
            self._error = str(exc)
        finally:
            if "user32" in locals():
                for identifier in registered:
                    user32.UnregisterHotKey(None, identifier)
            self._registered.clear()
            self._thread_id = 0
            self._ready.set()

    def stop(self) -> None:
        thread = self._thread
        if thread and thread.is_alive() and self._thread_id and os.name == "nt":
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.PostThreadMessageW.argtypes = [
                wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
            ]
            user32.PostThreadMessageW.restype = wintypes.BOOL
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            if threading.current_thread() is not thread:
                thread.join(timeout=3)
        self._thread = None
