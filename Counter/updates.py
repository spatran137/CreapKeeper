"""GitHub release discovery and integrity-checked Windows portable-EXE updates.

No updater service, credentials, or database access is required.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

APP_VERSION = "1.3.0"
REPO = "spatran137/CreapKeeper"
RELEASE_API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASE_PAGE = f"https://github.com/{REPO}/releases/latest"
ASSET_NAME = "CreapKeeper.exe"
MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024
CHECK_INTERVAL_SECONDS = 24 * 60 * 60


@dataclass(frozen=True)
class Release:
    version: str
    url: str
    page: str
    sha256: str
    size: int


def version_parts(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", value)
    if not match:
        raise ValueError(f"Invalid release version: {value!r}")
    return tuple(map(int, match.groups()))


def find_new_release(timeout: int = 8) -> Release | None:
    """Only stable, newer public releases with a verifiable executable qualify."""
    request = Request(
        RELEASE_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"CreapKeeper/{APP_VERSION}",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    if not isinstance(payload, dict) or payload.get("draft") or payload.get("prerelease"):
        return None
    tag = payload.get("tag_name", "")
    if not isinstance(tag, str) or version_parts(tag) <= version_parts(APP_VERSION):
        return None
    for asset in payload.get("assets", []):
        if asset.get("name") != ASSET_NAME:
            continue
        url = asset.get("browser_download_url", "")
        parsed = urlsplit(url)
        expected = f"/{REPO}/releases/download/{tag}/{ASSET_NAME}"
        if parsed.scheme != "https" or parsed.netloc != "github.com" or parsed.path != expected:
            raise ValueError("The release executable has an unexpected download URL.")
        size = asset.get("size")
        if type(size) is not int or not 0 < size <= MAX_DOWNLOAD_BYTES:
            raise ValueError("The release executable has an invalid size.")
        digest = asset.get("digest", "")
        if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest):
            raise ValueError("This release has no trusted SHA-256 digest. Use GitHub to update manually.")
        return Release(tag.lstrip("v"), url, RELEASE_PAGE, digest.split(":", 1)[1].lower(), size)
    raise ValueError("The latest GitHub release has no CreapKeeper.exe asset.")


def should_auto_check(settings_file: Path) -> bool:
    stamp = settings_file.with_name("last-update-check")
    try:
        return time.time() - stamp.stat().st_mtime >= CHECK_INTERVAL_SECONDS
    except OSError:
        return True


def mark_auto_check(settings_file: Path) -> None:
    stamp = settings_file.with_name("last-update-check")
    try:
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.touch()
    except OSError:
        pass  # Lack of a cache should not interfere with the app.


def _hash_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def download_release(release: Release, timeout: int = 30) -> Path:
    """Verify both the exact release size and GitHub-provided SHA-256 digest."""
    folder = Path(tempfile.mkdtemp(prefix="creapkeeper-update-"))
    partial = folder / (ASSET_NAME + ".part")
    destination = folder / ASSET_NAME
    try:
        request = Request(release.url, headers={"User-Agent": f"CreapKeeper/{APP_VERSION}"})
        with urlopen(request, timeout=timeout) as response, partial.open("wb") as handle:
            read_bytes = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                read_bytes += len(chunk)
                if read_bytes > MAX_DOWNLOAD_BYTES or read_bytes > release.size:
                    raise ValueError("Update download exceeded the advertised size.")
                handle.write(chunk)
        if read_bytes != release.size or _hash_file(partial) != release.sha256:
            raise ValueError("Update integrity check failed (file size or SHA-256).")
        partial.replace(destination)
        return destination
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise


# A separate Windows process must replace the running executable after it exits.
# All command arguments are passed as discrete values (never shell-interpolated).
_HELPER_SCRIPT = r"""
param(
    [Parameter(Mandatory=$true)][int]$ParentProcessId,
    [Parameter(Mandatory=$true)][string]$InstalledPath,
    [Parameter(Mandatory=$true)][string]$NewPath,
    [Parameter(Mandatory=$true)][string]$ExpectedSha256
)
$ErrorActionPreference = 'Stop'
$backup = "$InstalledPath.previous"
try {
    for ($i = 0; $i -lt 120; $i++) {
        if (-not (Get-Process -Id $ParentProcessId -ErrorAction SilentlyContinue)) { break }
        Start-Sleep -Milliseconds 500
    }
    if (Get-Process -Id $ParentProcessId -ErrorAction SilentlyContinue) {
        throw 'CreapKeeper did not exit; installation cancelled.'
    }
    if ((Get-FileHash -LiteralPath $NewPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ExpectedSha256) {
        throw 'The staged update did not pass SHA-256 verification.'
    }
    Copy-Item -LiteralPath $InstalledPath -Destination $backup -Force
    Copy-Item -LiteralPath $NewPath -Destination $InstalledPath -Force
    Start-Process -FilePath $InstalledPath
    Remove-Item -LiteralPath $NewPath -Force -ErrorAction SilentlyContinue
} catch {
    $errorText = $_.Exception.Message
    try {
        if (Test-Path -LiteralPath $backup) {
            Copy-Item -LiteralPath $backup -Destination $InstalledPath -Force
            Start-Process -FilePath $InstalledPath
        }
    } catch { $errorText += "; restore failed: $($_.Exception.Message)" }
    try {
        $log = Join-Path $env:LOCALAPPDATA 'Counter\updater-error.txt'
        $errorText | Out-File -LiteralPath $log -Encoding utf8
    } catch {}
}
"""


def supported_for_install() -> bool:
    return os.name == "nt" and bool(getattr(sys, "frozen", False))


def start_installer(downloaded: Path, release: Release) -> None:
    """Stage beside the installed portable app before closing it.

    If installation is blocked by permissions, this raises while the old app
    still runs. The user may instead install the verified download manually.
    """
    if not supported_for_install():
        raise RuntimeError("Automatic installation requires the packaged Windows executable.")
    target = Path(sys.executable).resolve()
    if target.suffix.lower() != ".exe":
        raise ValueError("The current executable is not a Windows .exe file.")
    if _hash_file(downloaded) != release.sha256:
        raise ValueError("Downloaded update failed final integrity verification.")
    staged = target.with_name(f".{target.stem}-{release.version}.new.exe")
    shutil.copyfile(downloaded, staged)
    if _hash_file(staged) != release.sha256:
        staged.unlink(missing_ok=True)
        raise ValueError("Staged update failed integrity verification.")
    helper = downloaded.parent / "install-update.ps1"
    helper.write_text(_HELPER_SCRIPT, encoding="utf-8-sig")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        subprocess.Popen(
            [
                "powershell.exe", "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden",
                "-File", str(helper), "-ParentProcessId", str(os.getpid()),
                "-InstalledPath", str(target), "-NewPath", str(staged),
                "-ExpectedSha256", release.sha256,
            ],
            creationflags=flags,
            close_fds=True,
        )
    except Exception:
        staged.unlink(missing_ok=True)
        raise
