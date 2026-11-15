"""Supervise an external OctoEverywhere process; never run it inside Moonraker."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
import signal
import shutil
import subprocess

try:
    from moonraker.common import RequestType
    GET = RequestType.GET
except ImportError:
    GET = ["GET"]


class OCOctoEverywhere:
    def __init__(self, config):
        self.server = config.get_server()
        self.root = Path(config.get("runtime_directory", "/usr/data/opencreator/octoeverywhere"))
        self.delay = config.getint("restart_delay", 15, minval=5)
        self.process = None
        self.output_task = None
        self.task = None
        self.stopping = False
        self.restarts = 0
        self.last_error = None
        self.runtime = None
        self.update_error = None
        self.updater_registered = False
        self.upstream_commit = None
        self.plugin_root = Path(__file__).resolve().parents[1]
        self.config = config
        self.server.register_endpoint("/server/octoeverywhere", GET, self._status)
        # register_updater is Moonraker's native extension API. Register during
        # construction, before update_manager.component_init initializes it.
        try:
            runtime = self._read_runtime()
            if runtime.get("schema") == 2:
                manager = self.server.load_component(config, "update_manager")
                manager.register_updater("octoeverywhere", {
                    "type": "git_repo", "channel": "beta", "primary_branch": "master",
                    "path": runtime["repo"],
                    "origin": "https://github.com/QuinnDamerell/OctoPrint-OctoEverywhere.git",
                    "virtualenv": str(Path(runtime["python"]).parent.parent),
                    "requirements": "requirements.txt", "is_system_service": "False",
                    "managed_services": "moonraker",
                    "pip_environment_variables": (
                        "PIP_CONSTRAINT=" + runtime["constraints"] +
                        "\nPIP_ONLY_BINARY=:all:\nPIP_DISABLE_PIP_VERSION_CHECK=1"),
                })
                self.updater_registered = True
            else:
                self.update_error = "Run scripts/setup_runtime.py to enable native upstream updates."
        except Exception as error:
            # A missing runtime or unsupported update API must never prevent
            # Moonraker or the printer from starting.
            self.update_error = "Native updater unavailable: " + str(error)
            logging.warning("OpenCreator OctoEverywhere: %s", self.update_error)

    def _read_runtime(self):
        runtime = json.loads((self.root / "runtime.json").read_text())
        if not isinstance(runtime, dict):
            raise ValueError("Runtime manifest must be an object")
        if runtime.get("schema") not in (None, 2):
            raise ValueError("Unsupported runtime schema")
        names = ["python", "repo"]
        names += ["constraints"] if runtime.get("schema") == 2 else ["runner"]
        for name in names:
            raw = Path(runtime[name])
            if not raw.is_absolute():
                raise ValueError("Runtime paths must be absolute: " + name)
            # Only the final Python symlink may point outside the runtime.
            path = raw.parent.resolve() / raw.name if name == "python" else raw.resolve()
            if not path.is_relative_to(self.root.resolve()) or not path.exists():
                raise ValueError("Invalid runtime path: " + name)
        if runtime.get("schema") == 2 and not (Path(runtime["repo"]) / ".git").is_dir():
            raise ValueError("Native updates require an upstream Git checkout")
        return runtime

    async def component_init(self):
        try:
            self.runtime = self._read_runtime()
            if self.runtime.get("schema") == 2:
                self.upstream_commit = (await asyncio.to_thread(
                    subprocess.check_output,
                    [shutil.which("git") or "/opt/bin/git", "-C", self.runtime["repo"], "rev-parse", "HEAD"],
                    text=True, timeout=15)).strip()
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
            self.last_error = "Runtime missing or invalid. Run scripts/setup_runtime.py while idle."
            logging.exception("OpenCreator OctoEverywhere runtime is unavailable")
            return
        self.task = asyncio.create_task(self._supervise())

    async def _supervise(self):
        while not self.stopping:
            try:
                env = os.environ.copy()
                env.update(PYTHONNOUSERSITE="1", PYTHONUNBUFFERED="1",
                           HOME=str(self.root), MALLOC_ARENA_MAX="2",
                           MALLOC_TRIM_THRESHOLD_="65536")
                # The dedicated venv supplies dependencies; do not inherit ReForge's
                # or Moonraker's PYTHONPATH, PYTHONHOME or floating-point ABI.
                env.pop("PYTHONPATH", None)
                env.pop("PYTHONHOME", None)
                logs = self.root / "logs"
                logs.mkdir(exist_ok=True)
                output = logs / "supervisor.log"
                if output.exists() and output.stat().st_size > 2 * 1024 * 1024:
                    output.replace(logs / "supervisor.log.1")
                # nice is applied to the child, never to Moonraker or Klippy.
                spawn = asyncio.create_task(asyncio.create_subprocess_exec(
                    shutil.which("nice") or "/bin/nice", "-n", "10", self.runtime["python"],
                    "-u", str(self.plugin_root / "scripts/run_octoeverywhere.py")
                    if self.runtime.get("schema") == 2 else self.runtime["runner"], str(self.root),
                    cwd=self.runtime["repo"], env=env, stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT, start_new_session=True))
                try:
                    self.process = await asyncio.shield(spawn)
                except asyncio.CancelledError:
                    self.process = await spawn
                    raise
                if self.process.stdout is not None:
                    self.output_task = asyncio.create_task(self._drain_output(self.process.stdout, output))
                self.last_error = None
                code = await self.process.wait()
                if self.output_task is not None:
                    await self.output_task
                    self.output_task = None
                if self.stopping:
                    break
                self.last_error = "OctoEverywhere exited with status %s" % code
                self.restarts += 1
                logging.warning("%s; retrying in %s seconds", self.last_error, self.delay)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.last_error = "Could not launch OctoEverywhere; inspect Moonraker log."
                logging.exception("OctoEverywhere supervisor error")
            if not self.stopping:
                await asyncio.sleep(self.delay)

    async def _drain_output(self, reader, path):
        while True:
            chunk = await reader.read(16384)
            if not chunk:
                return
            try:
                if path.exists() and path.stat().st_size + len(chunk) > 2 * 1024 * 1024:
                    path.replace(path.with_name(path.name + ".1"))
                with path.open("ab") as stream:
                    stream.write(chunk)
            except OSError:
                # Keep draining if storage is full: a blocked stdout pipe must
                # not freeze the remote-access daemon or the Moonraker loop.
                self.last_error = "Cannot write supervisor log; check free storage."

    async def _status(self, web_request):
        running = self.process is not None and self.process.returncode is None
        return {"running": running, "pid": self.process.pid if running else None,
                "restart_count": self.restarts, "last_error": self.last_error,
                "upstream_commit": self.upstream_commit or (self.runtime or {}).get("commit"),
                "native_updater_registered": self.updater_registered,
                "update_error": self.update_error,
                "mode": "local Moonraker companion", "runtime_directory": str(self.root)}

    async def close(self):
        self.stopping = True
        if self.task is not None:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        # wait() cancellation does not terminate a subprocess. Explicitly stop
        # this process group only; never pkill Python or touch Klippy.
        if self.process is not None and self.process.returncode is None:
            try:
                os.killpg(self.process.pid, signal.SIGTERM)
                await asyncio.wait_for(self.process.wait(), 8)
            except ProcessLookupError:
                pass
            except asyncio.TimeoutError:
                try:
                    os.killpg(self.process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                await self.process.wait()
        if self.output_task is not None:
            self.output_task.cancel()
            try:
                await self.output_task
            except asyncio.CancelledError:
                pass
            self.output_task = None


def load_component(config):
    return OCOctoEverywhere(config)
