"""Optional, consent-based Windows Firewall setup for the read-only LAN dashboard.

Does NOT change the firewall while inspecting it. If an applicable rule is missing,
the GUI may ask permission before explicitly launching a UAC-elevated PowerShell
helper. No permanent administrator privileges are needed for Counter.
"""

from __future__ import annotations

import base64
import ctypes
import os
import subprocess
import sys

RULE_NAME = "Counter-LAN-Dashboard-8765"
PORT = 8765

# This logic is shared by both the unprivileged check and the elevated installer.
# It deliberately leaves existing user/admin rules untouched.
_PS_BODY = r"""
$ErrorActionPreference = 'Stop'
try {
    $rules = @(Get-NetFirewallRule -PolicyStore ActiveStore -Direction Inbound -Action Allow -Enabled True -ErrorAction Stop)
    foreach ($rule in $rules) {
        $ports = @($rule | Get-NetFirewallPortFilter -ErrorAction Stop)
        $apps = @($rule | Get-NetFirewallApplicationFilter -ErrorAction Stop)
        $profile = [string]$rule.Profile
        if ($profile -notmatch '(?i)Any|Domain|Private') { continue }
        $applicationOk = $false
        foreach ($app in $apps) {
            $program = [string]$app.Program
            if ([string]::IsNullOrWhiteSpace($program) -or
                $program -eq 'Any' -or
                $program -ieq $exePath) {
                $applicationOk = $true
                break
            }
        }
        if (-not $applicationOk) { continue }
        foreach ($filter in $ports) {
            $protocol = [string]$filter.Protocol
            $localPorts = @($filter.LocalPort)
            if ($protocol -in @('TCP', '6', 'Any', '256') -and
                ($localPorts -contains '8765' -or $localPorts -contains 'Any')) {
                Write-Output ('FOUND: ' + $rule.DisplayName)
                exit 0
            }
        }
    }

    if ($ensure) {
        # A disabled/misconfigured managed rule needs administrator inspection.
        # Never replace, enable or widen any rule without a separate explicit action.
        $managed = @(Get-NetFirewallRule -Name 'Counter-LAN-Dashboard-8765' -ErrorAction SilentlyContinue)
        if ($managed.Count -gt 0) {
            throw 'The Counter-managed rule already exists but is not applicable. Inspect it in Windows Defender Firewall.'
        }
        New-NetFirewallRule -Name 'Counter-LAN-Dashboard-8765' -DisplayName 'Counter LAN Dashboard' -Description 'Read-only Counter dashboard; TCP 8765 from the local subnet only.' -Direction Inbound -Action Allow -Enabled True -Protocol TCP -LocalPort 8765 -Profile Private,Domain -RemoteAddress LocalSubnet -ErrorAction Stop | Out-Null
        Write-Output 'CREATED: Counter LAN Dashboard'
        exit 0
    }
    Write-Output 'MISSING'
    exit 2
}
catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 3
}
"""


def _encoded_command(ensure: bool, executable: str | None = None) -> str:
    """Safely encode the executable path as data, never as PowerShell source."""
    app_path = os.path.abspath(executable or sys.executable)
    encoded_path = base64.b64encode(app_path.encode("utf-16le")).decode("ascii")
    script = (
        "$exePath = [Text.Encoding]::Unicode.GetString("
        "[Convert]::FromBase64String('" + encoded_path + "'))\n"
        + "$ensure = " + ("$true" if ensure else "$false") + "\n"
        + _PS_BODY
    )
    return base64.b64encode(script.encode("utf-16le")).decode("ascii")


def firewall_status() -> tuple[str, str]:
    """Return ('present'|'missing'|'error'|'unsupported', explanation).

    Existing enabled inbound allow rules must cover TCP 8765, be applicable
    to Counter (or all programs), and cover Private/Domain profiles.
    Windows/organization firewall policies may still restrict LAN traffic.
    """
    if os.name != "nt":
        return "unsupported", "Windows Firewall integration is available only on Windows."
    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive",
             "-EncodedCommand", _encoded_command(ensure=False)],
            capture_output=True,
            text=True,
            timeout=18,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "error", f"Could not check Windows Firewall: {exc}"

    message = (completed.stdout or "").strip()
    if completed.returncode == 0 and "FOUND:" in message:
        # The rule may be locally created or deployed centrally by IT.
        return "present", message.split("FOUND:", 1)[-1].strip()
    if completed.returncode == 2 and "MISSING" in message:
        return "missing", "No applicable enabled inbound rule for TCP 8765 was found."
    error_text = (completed.stderr or "").strip()
    return "error", (
        f"Firewall inspection failed (exit {completed.returncode}). "
        + (error_text[-350:] if error_text else message[-350:])
    )


def request_firewall_install() -> tuple[bool, str]:
    """Ask Windows to launch a separate elevated installer via the UAC prompt.

    The call only starts the helper. A successful return is NOT confirmation
    that the user approved elevation or the firewall rule was actually added.
    """
    if os.name != "nt":
        return False, "Windows Firewall integration is available only on Windows."
    try:
        parameters = (
            "-NoProfile -NonInteractive -EncodedCommand "
            + _encoded_command(ensure=True)
        )
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", "powershell.exe", parameters, None, 1
        )
        if result <= 32:
            return False, (
                "Windows declined the administrator request "
                f"(ShellExecute result {result})."
            )
        return True, (
            "Administrator approval requested. After responding to UAC, "
            "use Check firewall to verify the rule."
        )
    except (OSError, AttributeError) as exc:
        return False, f"Could not request administrator approval: {exc}"
