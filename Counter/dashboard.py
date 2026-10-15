"""Read-only LAN dashboard served by the Counter desktop process.

No internet/CDN, extra server, data uploads, or write endpoints are needed.
Only localhost and private IPv4 LAN clients can read the aggregate JSON.
"""

from __future__ import annotations

import ipaddress
import json
import socket
import sys
import threading
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from storage import database

DASHBOARD_PORT = 8765
DAYS_VISIBLE = 30
ALLOWED_NETWORKS = tuple(
    ipaddress.ip_network(block)
    for block in (
        "127.0.0.0/8",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "169.254.0.0/16",
    )
)


def allowed_client(remote_ip: str) -> bool:
    """Reject public IPv4 and IPv6 peers even if a port is accidentally forwarded."""
    try:
        address = ipaddress.ip_address(remote_ip)
    except ValueError:
        return False
    return isinstance(address, ipaddress.IPv4Address) and any(
        address in network for network in ALLOWED_NETWORKS
    )


def dashboard_snapshot(db_path: str | Path | None = None, days: int = DAYS_VISIBLE) -> dict:
    """Cumulative daily totals; expose no raw event timestamps or database paths."""
    if not 1 <= days <= 366:
        raise ValueError("days must be between 1 and 366")

    today = datetime.now().astimezone().date()
    first = today - timedelta(days=days - 1)
    before = {"count": 0, "creap": 0}
    daily: dict[date, dict[str, int]] = {}

    with database(db_path) as connection:
        rows = connection.execute(
            "SELECT kind, quantity, occurred_at FROM events ORDER BY id"
        )
        for row in rows:
            moment = datetime.fromisoformat(row["occurred_at"])
            # All modern entries use timezone-aware UTC; historical imports also do.
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=timezone.utc)
            day = moment.astimezone().date()
            kind, quantity = row["kind"], int(row["quantity"])
            if day < first:
                before[kind] += quantity
            elif day <= today:
                current = daily.setdefault(day, {"count": 0, "creap": 0})
                current[kind] += quantity

    running = before.copy()
    points = []
    for offset in range(days):
        day = first + timedelta(days=offset)
        changes = daily.get(day, {})
        running["count"] += changes.get("count", 0)
        running["creap"] += changes.get("creap", 0)
        points.append({"date": day.isoformat(), **running})

    return {
        "totals": running.copy(),
        "days": points,
        "window_days": days,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def dashboard_html() -> bytes:
    """Locate bundled webpage both in source checkout and one-file PyInstaller."""
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return (root / "web" / "index.html").read_bytes()


def lan_url(port: int = DASHBOARD_PORT) -> str:
    """Show a practical LAN URL; IP address is an alternative if DNS is unavailable."""
    return f"http://{socket.gethostname()}:{port}/"


def make_handler(db_path: str | Path | None):
    """One instance for the server: no filesystem browsing or write routes."""
    class Handler(BaseHTTPRequestHandler):
        server_version = "CounterLAN/1.0"
        sys_version = ""

        def log_message(self, format: str, *args: object) -> None:
            # The dashboard does not record visitor IPs.
            return

        def setup(self) -> None:
            super().setup()
            self.connection.settimeout(5)

        def _respond(self, head_only: bool = False) -> None:
            if not allowed_client(self.client_address[0]):
                self.send_error(403, "Private LAN clients only")
                return

            request_path = urlsplit(self.path).path
            try:
                if request_path in ("/", "/index.html"):
                    payload = dashboard_html()
                    mime = "text/html; charset=utf-8"
                elif request_path == "/counts.json":
                    payload = json.dumps(
                        dashboard_snapshot(db_path), separators=(",", ":")
                    ).encode("utf-8")
                    mime = "application/json; charset=utf-8"
                else:
                    self.send_error(404, "Page not found")
                    return
            except (OSError, ValueError, RuntimeError) as error:
                # Never leak filesystem or database details to a browser.
                self.send_error(503, "Dashboard data temporarily unavailable")
                return

            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; connect-src 'self'; "
                "img-src 'self'; base-uri 'none'; frame-ancestors 'none'",
            )
            self.end_headers()
            if not head_only:
                self.wfile.write(payload)

        def do_GET(self) -> None:
            self._respond()

        def do_HEAD(self) -> None:
            self._respond(head_only=True)

        def do_POST(self) -> None:
            self.send_error(405, "Read-only dashboard")

    return Handler


class DashboardServer:
    """Small read-only server that starts and stops with Counter."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        host: str = "0.0.0.0",
        port: int = DASHBOARD_PORT,
    ) -> None:
        self.db_path = db_path
        self.host = host
        self.port = port
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return bool(self._server and self._thread and self._thread.is_alive())

    @property
    def local_url(self) -> str:
        port = self._server.server_port if self._server is not None else self.port
        return f"http://127.0.0.1:{port}/"

    @property
    def share_url(self) -> str:
        port = self._server.server_port if self._server is not None else self.port
        return lan_url(port)

    def start(self) -> tuple[bool, str]:
        if self.running:
            return True, f"LAN dashboard: {self.share_url}"
        try:
            # Catch packaging errors before exposing any HTTP listener.
            dashboard_html()
            server = ThreadingHTTPServer((self.host, self.port), make_handler(self.db_path))
            server.daemon_threads = True
            self._server = server
            self._thread = threading.Thread(
                target=server.serve_forever,
                kwargs={"poll_interval": 0.1},
                daemon=True,
                name="CounterDashboard",
            )
            self._thread.start()
            return True, f"LAN dashboard: {self.share_url}"
        except (OSError, ValueError) as error:
            self.stop()
            return False, f"Could not start LAN dashboard on port {self.port}: {error}"

    def stop(self) -> None:
        if self._server is not None:
            if self._thread and self._thread.is_alive():
                self._server.shutdown()
                self._thread.join(timeout=4)
            self._server.server_close()
        self._server = None
        self._thread = None
