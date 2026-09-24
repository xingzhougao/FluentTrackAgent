"""Regression checks for the packaged Soulseek account collision."""

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent_service"))

from providers.music.soulseek_provider import SoulseekMusicProvider
from services.slskd_daemon import SlskdDaemonManager


class SearchUnavailableRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_disconnected_soulseek_does_not_submit_search(self):
        provider = SoulseekMusicProvider()
        provider.check_availability = AsyncMock(return_value=True)
        provider.ensure_logged_in = AsyncMock(return_value=False)

        with patch("providers.music.soulseek_provider.httpx.AsyncClient") as client:
            result = await provider.search("稻香", "周杰伦")

        self.assertEqual(result, [])
        client.assert_not_called()
        provider.ensure_logged_in.assert_awaited_once()


class PackagingRegressionTests(unittest.TestCase):
    def test_slskd_runtime_account_is_not_packaged(self):
        spec = importlib.util.spec_from_file_location(
            "build_standalone_package", ROOT / "scripts" / "build_standalone_package.py"
        )
        package = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(package)

        source = ROOT / "tools" / "slskd"
        ignored = package.ignore_tools_cache(
            source, ["slskd.exe", "data", "config", "slskd.log"]
        )
        self.assertIn("data", ignored)
        self.assertIn("slskd.log", ignored)
        self.assertNotIn("slskd.exe", ignored)
        self.assertNotIn("config", ignored)


class SoulseekAccountTests(unittest.TestCase):
    def _manager(self, root: Path) -> SlskdDaemonManager:
        manager = SlskdDaemonManager()
        manager.data_dir = root / "tools" / "slskd" / "data"
        manager.config_path = manager.data_dir / "slskd.yml"
        manager.download_dir = root / "music"
        manager.incomplete_dir = root / "tools" / "slskd" / "incomplete"
        return manager

    def test_new_install_generates_stable_unique_credentials(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            self.assertTrue(Path(tmp).resolve().is_relative_to(ROOT.resolve()))
            manager = self._manager(Path(tmp))
            manager.ensure_configured()
            first = yaml.safe_load(manager.config_path.read_text(encoding="utf-8"))
            manager.ensure_configured()
            second = yaml.safe_load(manager.config_path.read_text(encoding="utf-8"))
            other_install = self._manager(Path(tmp) / "other-install")
            other_install.ensure_configured()
            other = yaml.safe_load(other_install.config_path.read_text(encoding="utf-8"))

            self.assertRegex(first["soulseek"]["username"], r"^ft_[0-9a-f]{16}$")
            self.assertRegex(first["soulseek"]["password"], r"^[0-9a-f]{32}$")
            self.assertEqual(first["soulseek"], second["soulseek"])
            self.assertNotEqual(first["soulseek"], other["soulseek"])

    def test_legacy_packaged_account_is_rotated_once(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            self.assertTrue(Path(tmp).resolve().is_relative_to(ROOT.resolve()))
            manager = self._manager(Path(tmp))
            manager.data_dir.mkdir(parents=True)
            manager.config_path.write_text(
                yaml.safe_dump({"soulseek": {"username": "fl_usr_1234abcd", "password": "old"}}),
                encoding="utf-8",
            )
            manager.ensure_configured()
            first = yaml.safe_load(manager.config_path.read_text(encoding="utf-8"))
            manager.ensure_configured()
            second = yaml.safe_load(manager.config_path.read_text(encoding="utf-8"))

            self.assertNotEqual(first["soulseek"]["username"], "fl_usr_1234abcd")
            self.assertNotEqual(first["soulseek"]["password"], "old")
            self.assertEqual(first["soulseek"], second["soulseek"])
            self.assertTrue(manager.config_path.with_name("slskd.yml.pre-account-migration.bak").is_file())

    def test_manual_account_is_preserved(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            self.assertTrue(Path(tmp).resolve().is_relative_to(ROOT.resolve()))
            manager = self._manager(Path(tmp))
            manager.data_dir.mkdir(parents=True)
            manager.config_path.write_text(
                yaml.safe_dump({"soulseek": {"username": "my-account", "password": "my-password"}}),
                encoding="utf-8",
            )
            manager.ensure_configured()
            result = yaml.safe_load(manager.config_path.read_text(encoding="utf-8"))

            self.assertEqual(result["soulseek"]["username"], "my-account")
            self.assertEqual(result["soulseek"]["password"], "my-password")


if __name__ == "__main__":
    unittest.main()
