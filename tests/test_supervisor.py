import asyncio
import importlib.util
import json
import os
from pathlib import Path
import signal
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

SOURCE = Path(__file__).resolve().parents[1] / "moonraker/oc_octoeverywhere_impl.py"
spec = importlib.util.spec_from_file_location("oc_octoeverywhere", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Process:
    def __init__(self, pid):
        self.pid = pid
        self.returncode = None
        self.stdout = None
        self.done = asyncio.Event()

    async def wait(self):
        await self.done.wait()
        return self.returncode

    def exit(self, code):
        self.returncode = code
        self.done.set()


class Config:
    def __init__(self, root):
        self.root = root
        self.endpoint = None

    def get_server(self):
        return self

    def get(self, name, default):
        return str(self.root)

    def getint(self, *args, **kwargs):
        return 5

    def register_endpoint(self, path, methods, handler):
        self.endpoint = (path, handler)


class SupervisorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        for path in (self.root / "venv/bin/python", self.root / "runner.py"):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        (self.root / "source").mkdir()
        self.runtime = {"python": str(self.root / "venv/bin/python"),
                        "runner": str(self.root / "runner.py"),
                        "repo": str(self.root / "source"), "commit": "pinned"}
        (self.root / "runtime.json").write_text(json.dumps(self.runtime))
        self.plugin = module.OCOctoEverywhere(Config(self.root))

    async def asyncTearDown(self):
        await self.plugin.close()
        self.temp.cleanup()

    async def wait_for(self, predicate):
        async with asyncio.timeout(2):
            while not predicate():
                await asyncio.sleep(.005)

    async def test_missing_runtime_fails_without_disrupting_moonraker(self):
        (self.root / "runtime.json").unlink()
        with patch.object(module.asyncio, "create_subprocess_exec", new_callable=AsyncMock) as spawn:
            with self.assertLogs(level="ERROR"):
                await self.plugin.component_init()
        spawn.assert_not_called()
        self.assertFalse((await self.plugin._status(None))["running"])
        self.assertIn("Runtime missing", self.plugin.last_error)

    async def test_runner_outside_runtime_is_rejected(self):
        self.runtime["runner"] = str(SOURCE)
        (self.root / "runtime.json").write_text(json.dumps(self.runtime))
        with self.assertLogs(level="ERROR"):
            await self.plugin.component_init()
        self.assertIsNone(self.plugin.task)

    async def test_low_priority_environment_and_exact_child_cleanup(self):
        proc = Process(4321)
        with patch.object(module.shutil, "which", return_value="/test/bin/nice"), patch.object(module.asyncio, "create_subprocess_exec", new_callable=AsyncMock, return_value=proc) as spawn:
            with patch.dict(os.environ, {"PYTHONPATH": "/old-reforge", "PYTHONHOME": "/wrong-python"}):
                await self.plugin.component_init()
                await self.wait_for(lambda: self.plugin.process is proc)
            call = spawn.call_args
            self.assertEqual(call.args[:3], ("/test/bin/nice", "-n", "10"))
            self.assertNotIn("PYTHONPATH", call.kwargs["env"])
            self.assertNotIn("PYTHONHOME", call.kwargs["env"])
            self.assertTrue(call.kwargs["start_new_session"])
            def terminate(pid, sig):
                self.assertEqual((pid, sig), (4321, signal.SIGTERM))
                proc.exit(-15)
            with patch.object(module.os, "killpg", side_effect=terminate, create=True) as kill:
                await self.plugin.close()
            kill.assert_called_once()
            self.assertFalse((await self.plugin._status(None))["running"])

    async def test_unexpected_exit_restarts_once(self):
        first, second = Process(4321), Process(4322)
        self.plugin.delay = .01
        with patch.object(module.asyncio, "create_subprocess_exec", new_callable=AsyncMock, side_effect=[first, second]):
            await self.plugin.component_init()
            await self.wait_for(lambda: self.plugin.process is first)
            first.exit(7)
            await self.wait_for(lambda: self.plugin.process is second)
            self.assertEqual(self.plugin.restarts, 1)
            with patch.object(module.os, "killpg", side_effect=lambda *args: second.exit(-15), create=True):
                await self.plugin.close()

    async def test_stdout_is_bounded_without_restarting_process(self):
        reader = AsyncMock()
        reader.read.side_effect = [b"a" * (1024 * 1024), b"b" * (1024 * 1024), b"c", b""]
        path = self.root / "stdout.log"
        await self.plugin._drain_output(reader, path)
        self.assertEqual(path.read_bytes(), b"c")
        self.assertEqual(path.with_name("stdout.log.1").stat().st_size, 2 * 1024 * 1024)

    async def test_storage_error_does_not_stop_stdout_drain(self):
        reader = AsyncMock()
        reader.read.side_effect = [b"one", b"two", b""]
        with patch.object(Path, "open", side_effect=OSError("No space")):
            await self.plugin._drain_output(reader, self.root / "stdout.log")
        self.assertEqual(reader.read.await_count, 3)
        self.assertIn("storage", self.plugin.last_error)

    async def test_standard_venv_symlink_is_accepted(self):
        target = self.root.parent / (self.root.name + "-base-python")
        target.touch()
        python = self.root / "venv/bin/python"
        python.unlink()
        try:
            python.symlink_to(target)
        except OSError:
            target.unlink()
            self.skipTest("Creating symlinks requires permission on this host")
        try:
            proc = Process(4321)
            with patch.object(module.asyncio, "create_subprocess_exec", new_callable=AsyncMock, return_value=proc):
                await self.plugin.component_init()
                await self.wait_for(lambda: self.plugin.process is proc)
                with patch.object(module.os, "killpg", side_effect=lambda *args: proc.exit(-15), create=True):
                    await self.plugin.close()
            self.assertIsNone(self.plugin.last_error)
        finally:
            target.unlink()


if __name__ == "__main__":
    unittest.main()
