import importlib.util
import io
import json
from pathlib import Path
import tempfile
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "scripts/setup_runtime.py"
spec = importlib.util.spec_from_file_location("oc_setup", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SetupTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "linux", "Installer filesystem/lock test requires Linux")
    def test_failed_generation_preserves_previous_runtime_and_account(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "runtime"
            root.mkdir()
            (root / "storage").mkdir()
            manifest = root / "runtime.json"
            before = json.dumps({"commit": "old", "python": "old-python"})
            manifest.write_text(before)
            secret = root / "storage/octoeverywhere.secrets"
            secret.write_text("synthetic-test-identity")
            args = SimpleNamespace(runtime=root, moonraker_url="http://127.0.0.1:7125", ref=None, rebuild=False)
            def fail_clone(*args, **kwargs):
                Path(args[-1]).mkdir()
                raise RuntimeError("Simulated interrupted download")
            with patch.object(module, "OPENCREATOR_CONFIG", Path(tmp)), patch.object(module, "require_idle"), patch.object(module.shutil, "which", return_value="git"), patch.object(module, "run", side_effect=fail_clone):
                with self.assertRaisesRegex(RuntimeError, "interrupted"):
                    module.setup(args)
            self.assertEqual(manifest.read_text(), before)
            self.assertEqual(secret.read_text(), "synthetic-test-identity")
            self.assertEqual(list(root.glob("upstream-*")), [])

    @unittest.skipUnless(sys.platform == "linux", "Installer filesystem/lock test requires Linux")
    def test_repeat_setup_does_not_update_or_replace_existing_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "runtime"
            root.mkdir()
            manifest = root / "runtime.json"
            before = json.dumps({"schema": 2, "repo": "existing-upstream"})
            manifest.write_text(before)
            args = SimpleNamespace(runtime=root, moonraker_url="http://127.0.0.1:7125", ref=None, rebuild=False)
            with patch.object(module, "OPENCREATOR_CONFIG", Path(tmp)), patch.object(module, "require_idle"), patch.object(module, "run") as run:
                module.setup(args)
            run.assert_not_called()
            self.assertEqual(manifest.read_text(), before)

    def test_release_selection_is_numeric_and_excludes_prereleases(self):
        self.assertEqual(module.latest_release("5.9.0\n5.10.0\n6.0.0-rc1\n"), "5.10.0")
        with self.assertRaises(RuntimeError):
            module.latest_release("nightly\n")

    def test_busy_or_unreachable_printer_fails_closed(self):
        for state in ("printing", "paused", "unknown"):
            response = io.BytesIO(json.dumps({"result": {"status": {"print_stats": {"state": state}}}}).encode())
            with patch.object(module.urllib.request, "urlopen", return_value=response):
                with self.assertRaisesRegex(RuntimeError, "idle"):
                    module.require_idle("http://127.0.0.1:7125")
        with patch.object(module.urllib.request, "urlopen", side_effect=OSError("Offline")):
            with self.assertRaises(OSError):
                module.require_idle("http://127.0.0.1:7125")

    def test_non_loopback_setup_target_is_rejected(self):
        for url in ("http://printer.local:7125", "https://127.0.0.1", "http://user@localhost:7125", "http://127.0.0.1/path"):
            with self.subTest(url=url), self.assertRaises(RuntimeError):
                module.require_idle(url)

    def test_configuration_preserves_user_options_and_never_seeds_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            (root / "storage").mkdir()
            (root / "config/octoeverywhere.conf").write_text("[logging]\nmax_file_count=4\n[webcam]\nflip_horizontally=True\n")
            module.write_config(root, "http://127.0.0.1:7125", 80)
            config = module.configparser.ConfigParser()
            config.read(root / "config/octoeverywhere.conf")
            self.assertEqual(config.get("logging", "max_file_count"), "4")
            self.assertEqual(config.get("webcam", "flip_horizontally"), "True")
            self.assertEqual(config.get("companion", "ip_or_hostname"), "127.0.0.1")
            self.assertEqual(list((root / "storage").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
