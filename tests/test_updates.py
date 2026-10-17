"""Unit tests for opt-in GitHub release checks, download verification and safety."""
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Counter"))
import updates


class ReleaseTests(unittest.TestCase):
    def _payload(self, tag="v1.4.0", body=b"valid release", digest=None):
        checksum = digest if digest is not None else hashlib.sha256(body).hexdigest()
        return {
            "tag_name": tag, "draft": False, "prerelease": False,
            "assets": [{
                "name": "CreapKeeper.exe",
                "size": len(body),
                "digest": f"sha256:{checksum}",
                "browser_download_url":
                    f"https://github.com/spatran137/CreapKeeper/releases/download/{tag}/CreapKeeper.exe",
            }],
        }

    def _mock_release(self, payload):
        return patch("updates.urlopen", return_value=io.BytesIO(json.dumps(payload).encode()))

    def test_versions_are_numeric(self):
        self.assertEqual(updates.version_parts("v1.12.0"), (1, 12, 0))
        self.assertGreater(updates.version_parts("1.12.0"), updates.version_parts("v1.9.9"))
        for invalid in ("v1.2", "1.2.0-beta", "one.two.three"):
            with self.assertRaises(ValueError):
                updates.version_parts(invalid)

    def test_new_release_includes_verified_asset(self):
        with self._mock_release(self._payload()):
            release = updates.find_new_release()
        self.assertEqual(release.version, "1.4.0")
        self.assertEqual(release.size, len(b"valid release"))
        self.assertEqual(release.sha256, hashlib.sha256(b"valid release").hexdigest())

    def test_no_update_for_current_or_older_releases(self):
        for tag in ("v1.3.0", "v1.2.0"):
            with self.subTest(tag=tag), self._mock_release(self._payload(tag=tag)):
                self.assertIsNone(updates.find_new_release())

    def test_draft_prerelease_and_wrong_asset_rejected(self):
        for flag in ("draft", "prerelease"):
            payload = self._payload()
            payload[flag] = True
            with self._mock_release(payload):
                self.assertIsNone(updates.find_new_release())
        payload = self._payload()
        payload["assets"][0]["name"] = "unrelated.exe"
        with self._mock_release(payload), self.assertRaisesRegex(ValueError, "no CreapKeeper.exe"):
            updates.find_new_release()

    def test_forged_urls_and_missing_digest_rejected(self):
        payload = self._payload()
        payload["assets"][0]["browser_download_url"] = "https://example.com/fake.exe"
        with self._mock_release(payload), self.assertRaisesRegex(ValueError, "unexpected"):
            updates.find_new_release()
        payload = self._payload()
        payload["assets"][0]["digest"] = None
        with self._mock_release(payload), self.assertRaisesRegex(ValueError, "SHA-256"):
            updates.find_new_release()

    def test_download_sha_and_size_match(self):
        raw = b"secure test exe bytes"
        p = self._payload(body=raw)
        with self._mock_release(p):
            release = updates.find_new_release()
        with patch("updates.urlopen", return_value=io.BytesIO(raw)):
            path = updates.download_release(release)
        self.addCleanup(lambda: __import__("shutil").rmtree(path.parent, ignore_errors=True))
        self.assertEqual(path.read_bytes(), raw)

    def test_corrupted_download_is_not_installed(self):
        raw = b"secure test exe bytes"
        with self._mock_release(self._payload(body=raw)):
            release = updates.find_new_release()
        with patch("updates.urlopen", return_value=io.BytesIO(b"corrupted test value")):
            with self.assertRaisesRegex(ValueError, "integrity check"):
                updates.download_release(release)

    def test_check_cadence_and_source_install_guard(self):
        with tempfile.TemporaryDirectory() as tempdir:
            settings = Path(tempdir) / "data" / "settings.json"
            self.assertTrue(updates.should_auto_check(settings))
            updates.mark_auto_check(settings)
            self.assertFalse(updates.should_auto_check(settings))
        with patch("updates.supported_for_install", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "packaged Windows"):
                updates.start_installer(Path("nowhere.exe"), updates.Release("1.4.0", "", "", "", 1))

    def test_version_matches_documented_release(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github" / "workflows" / "publish-release.yml").read_text()
        self.assertIn(f"'v{updates.APP_VERSION}'", workflow)


if __name__ == "__main__":
    unittest.main()
