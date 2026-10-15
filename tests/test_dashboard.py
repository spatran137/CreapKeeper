"""Dashboard tests: private-address restrictions, cumulative data and HTTP behavior."""

import json
import sqlite3
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Counter"))

from dashboard import DashboardServer, allowed_client, dashboard_snapshot
from storage import add_event, database


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "Counter.db"

    def insert(self, kind, quantity, moment):
        with database(self.db) as conn:
            conn.execute(
                "INSERT INTO events(kind, quantity, occurred_at) VALUES (?,?,?)",
                (kind, quantity, moment.isoformat(timespec="seconds")),
            )

    def test_local_only_ip_policy(self):
        for address in ("127.0.0.1", "10.1.2.3", "172.16.5.7", "172.31.255.254", "192.168.4.42", "169.254.1.2"):
            self.assertTrue(allowed_client(address), address)
        for address in ("8.8.8.8", "172.32.0.1", "192.0.2.1", "::1", "2001:4860::8888", "garbage"):
            self.assertFalse(allowed_client(address), address)

    def test_empty_dashboard_has_flat_lines(self):
        result = dashboard_snapshot(self.db)
        self.assertEqual(result["totals"], {"count": 0, "creap": 0})
        self.assertEqual(len(result["days"]), 30)
        self.assertEqual(result["days"][-1]["count"], 0)

    def test_daily_cumulative_and_history_only_totals(self):
        local_now = datetime.now().astimezone()
        self.insert("count", 4, local_now - timedelta(days=35))
        self.insert("creap", 2, local_now - timedelta(days=1))
        self.insert("count", 3, local_now)
        result = dashboard_snapshot(self.db)
        self.assertEqual(result["totals"], {"count": 7, "creap": 2})
        self.assertEqual(result["days"][0]["count"], 4)
        self.assertEqual(result["days"][-1]["count"], 7)
        self.assertEqual(result["days"][-2]["creap"], 2)
        self.assertNotIn("source_path", json.dumps(result))
        self.assertNotIn("occurred_at", json.dumps(result))

    def test_lan_http_is_read_only_and_no_store(self):
        add_event("count", self.db)
        server = DashboardServer(self.db, host="127.0.0.1", port=0)
        ok, message = server.start()
        self.assertTrue(ok, message)
        self.addCleanup(server.stop)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(server.local_url, timeout=5) as response:
            page = response.read().decode("utf-8")
            self.assertEqual(response.status, 200)
            self.assertIn("Counter Dashboard", page)
            self.assertIn("/counts.json", page)
            self.assertEqual(response.headers["Cache-Control"], "no-store, max-age=0")
        with opener.open(server.local_url + "counts.json", timeout=5) as response:
            data = json.load(response)
            self.assertEqual(data["totals"]["count"], 1)
            self.assertEqual(len(data["days"]), 30)
            self.assertEqual(response.headers["Content-Type"], "application/json; charset=utf-8")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            opener.open(
                urllib.request.Request(server.local_url + "counts.json", method="POST", data=b"{}"),
                timeout=5,
            )
        self.assertEqual(ctx.exception.code, 405)
        ctx.exception.close()
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            opener.open(server.local_url + "../Counter.db", timeout=5)
        self.assertEqual(ctx.exception.code, 404)
        ctx.exception.close()

    def test_restart_releases_port(self):
        server = DashboardServer(self.db, host="127.0.0.1", port=0)
        self.assertTrue(server.start()[0])
        port = server._server.server_port
        server.stop()
        reuse = DashboardServer(self.db, host="127.0.0.1", port=port)
        self.assertTrue(reuse.start()[0])
        reuse.stop()


if __name__ == "__main__":
    unittest.main()
