"""Unit tests for consent-based, idempotent Windows Firewall handling.

Mocks keep tests read-only on Windows and Linux build runners.
"""

import base64
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Counter"))

import firewall


class FirewallTests(unittest.TestCase):
    def test_script_uses_private_domain_and_local_subnet(self):
        script = base64.b64decode(
            firewall._encoded_command(True, r"C:\Counter\Counter.exe")
        ).decode("utf-16le")
        self.assertIn("-RemoteAddress LocalSubnet", script)
        self.assertIn("-Profile Private,Domain", script)
        self.assertIn("-LocalPort 8765", script)
        self.assertIn("Get-NetFirewallRule -PolicyStore ActiveStore", script)
        self.assertIn("FOUND:", script)
        self.assertIn("Get-NetFirewallApplicationFilter", script)
        self.assertNotIn("-Profile Any", script)
        # Executable paths must be encoded as data, not interpolated as code.
        self.assertNotIn(r"C:\Counter\Counter.exe", script)

    @patch.object(firewall.os, "name", "nt")
    @patch("firewall.subprocess.run")
    def test_detects_user_created_rule_without_elevation(self, mock_run):
        mock_run.return_value = SimpleNamespace(
            returncode=0, stdout="FOUND: Creap Counter Dashboard\n", stderr=""
        )
        state, name = firewall.firewall_status()
        self.assertEqual((state, name), ("present", "Creap Counter Dashboard"))
        self.assertEqual(mock_run.call_count, 1)
        args = mock_run.call_args.args[0]
        self.assertEqual(args[0], "powershell.exe")
        self.assertIn("-EncodedCommand", args)
        self.assertNotIn("runas", str(args))

    @patch.object(firewall.os, "name", "nt")
    @patch("firewall.subprocess.run")
    def test_missing_and_errors_are_distinct(self, mock_run):
        mock_run.return_value = SimpleNamespace(
            returncode=2, stdout="MISSING\n", stderr=""
        )
        self.assertEqual(firewall.firewall_status()[0], "missing")
        mock_run.return_value = SimpleNamespace(
            returncode=3, stdout="", stderr="Access denied"
        )
        state, detail = firewall.firewall_status()
        self.assertEqual(state, "error")
        self.assertIn("Access denied", detail)

    @patch.object(firewall.os, "name", "nt")
    @patch("firewall.subprocess.run")
    def test_no_false_positive_if_powershell_outputs_nothing(self, mock_run):
        mock_run.return_value = SimpleNamespace(
            returncode=0, stdout="", stderr=""
        )
        self.assertEqual(firewall.firewall_status()[0], "error")

    @patch.object(firewall.os, "name", "nt")
    @patch("firewall.subprocess.run", side_effect=OSError("no powershell"))
    def test_check_failure_is_reported(self, mock_run):
        state, detail = firewall.firewall_status()
        self.assertEqual(state, "error")
        self.assertIn("no powershell", detail)

    @patch.object(firewall.os, "name", "nt")
    @patch("firewall.ctypes.windll", create=True)
    def test_install_requests_uac_and_never_claims_created(self, shell):
        shell.shell32.ShellExecuteW.return_value = 42
        success, message = firewall.request_firewall_install()
        self.assertTrue(success)
        self.assertIn("requested", message.lower())
        self.assertNotIn("created", message.lower())
        args = shell.shell32.ShellExecuteW.call_args.args
        self.assertEqual(args[1], "runas")
        self.assertEqual(args[2], "powershell.exe")

    @patch.object(firewall.os, "name", "nt")
    @patch("firewall.ctypes.windll", create=True)
    def test_uac_denial_is_not_success(self, shell):
        shell.shell32.ShellExecuteW.return_value = 5
        self.assertFalse(firewall.request_firewall_install()[0])

    @unittest.skipIf(os.name == "nt", "Non-Windows test only")
    def test_other_platforms_do_not_launch_powershell(self):
        self.assertEqual(firewall.firewall_status()[0], "unsupported")
        self.assertFalse(firewall.request_firewall_install()[0])


if __name__ == "__main__":
    unittest.main()
