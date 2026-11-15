import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

SOURCE = Path(__file__).resolve().parents[1] / "moonraker/oc_octoeverywhere_impl.py"
spec = importlib.util.spec_from_file_location("oc_native_updates", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Config:
    def __init__(self, root):
        self.root = root
        self.manager = Mock()

    def get_server(self):
        return self

    def register_endpoint(self, *args):
        pass

    def get(self, name, default):
        return str(self.root)

    def getint(self, *args, **kwargs):
        return 15

    def load_component(self, config, name):
        assert name == "update_manager"
        return self.manager


class NativeUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        for rel in ("envs/current/bin/python", "native.txt"):
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        (self.root / "upstream/.git").mkdir(parents=True)
        self.runtime = {"schema": 2, "python": str(self.root / "envs/current/bin/python"),
                        "repo": str(self.root / "upstream"), "constraints": str(self.root / "native.txt")}
        self.config = Config(self.root)

    def create(self):
        (self.root / "runtime.json").write_text(json.dumps(self.runtime))
        return module.OCOctoEverywhere(self.config)

    def test_upstream_owns_releases_and_dependencies(self):
        plugin = self.create()
        self.assertTrue(plugin.updater_registered)
        name, settings = self.config.manager.register_updater.call_args.args
        self.assertEqual(name, "octoeverywhere")
        self.assertEqual(settings["channel"], "beta")
        self.assertEqual(settings["requirements"], "requirements.txt")
        self.assertEqual(settings["managed_services"], "moonraker")
        self.assertEqual(settings["origin"], "https://github.com/QuinnDamerell/OctoPrint-OctoEverywhere.git")
        self.assertIn("PIP_CONSTRAINT=" + self.runtime["constraints"], settings["pip_environment_variables"])
        self.assertIn("PIP_ONLY_BINARY=:all:", settings["pip_environment_variables"])
        self.assertNotIn("install_script", settings)
        self.assertNotIn("system_dependencies", settings)

    def test_archive_checkout_cannot_claim_native_updates(self):
        (self.root / "upstream/.git").rmdir()
        plugin = self.create()
        self.assertFalse(plugin.updater_registered)
        self.config.manager.register_updater.assert_not_called()

    def test_path_traversal_and_relative_paths_are_rejected(self):
        for python in (str(self.root / "envs/../../../external-python"), "relative/python"):
            with self.subTest(python=python):
                self.runtime["python"] = python
                self.assertFalse(self.create().updater_registered)

    def test_update_api_failure_keeps_component_available(self):
        self.config.manager.register_updater.side_effect = RuntimeError("Unsupported API")
        plugin = self.create()
        self.assertFalse(plugin.updater_registered)
        self.assertIn("Unsupported API", plugin.update_error)
        self.assertIsNotNone(plugin._read_runtime())


if __name__ == "__main__":
    unittest.main()
