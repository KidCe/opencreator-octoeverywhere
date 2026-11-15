"""Runtime adapter for the independently updated upstream (no source files modified)."""
from pathlib import Path
import base64
import ctypes
import copy
import fcntl
import json
import os
import runpy
import signal
import sys


def main():
    root = Path(sys.argv[1]).resolve()
    # Also fail closed if Moonraker is killed without calling component.close().
    # Linux releases the advisory lock when this process exits.
    lock = (root / "service.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    parent = os.getppid()
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGTERM, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "Could not set parent-death signal")
    if parent == 1 or os.getppid() != parent:
        raise RuntimeError("Moonraker parent exited before startup")
    settings = json.loads((root / "runtime.json").read_text())
    if settings.get("schema") == 2:
        from check_runtime import check
        check(settings["repo"])
    sys.path.insert(0, settings["repo"])
    # Upstream's UI injector scans sibling/front-end directories and modifies
    # their HTML. OpenCreator owns those files: this integration uses its own
    # status endpoint instead. The pinned upstream has no other Init consumers.
    from moonraker_octoeverywhere.uiinjector import UiInjector
    UiInjector.Init = staticmethod(lambda logger, repo_root: None)
    # OpenCreator redirects /webcam[N]/ to dedicated mjpg-streamer ports.
    # Upstream's snapshot path does not reliably follow that redirect. Resolve
    # only these local routes, retaining automatic camera discovery/transforms.
    from opencreator_webcam import normalize_camera_url, patch_http_requests
    from octoeverywhere.octohttprequest import OctoHttpRequest, PathTypes
    patch_http_requests(OctoHttpRequest, PathTypes)
    from moonraker_octoeverywhere.moonrakerwebcamhelper import MoonrakerWebcamHelper
    original_cameras = MoonrakerWebcamHelper.GetWebcamConfig

    def opencreator_cameras(helper):
        cameras = original_cameras(helper)
        if cameras is None:
            return None
        result = [copy.copy(camera) for camera in cameras]
        for camera in result:
            camera.SnapshotUrl = normalize_camera_url(camera.SnapshotUrl)
            camera.StreamUrl = normalize_camera_url(camera.StreamUrl)
        return result

    MoonrakerWebcamHelper.GetWebcamConfig = opencreator_cameras
    arguments = {
        "ServiceName": "oc-octoeverywhere",
        "VirtualEnvPath": str(root / "venv"),
        "RepoRootFolder": settings["repo"],
        "LocalFileStoragePath": str(root / "storage"),
        "ConfigFolder": str(root / "config"),
        "LogFolder": str(root / "logs"),
        # Companion mode is local to this printer, avoids upstream's unsupported
        # systemd setup and never edits OpenCreator's Moonraker configuration.
        "IsCompanion": True,
    }
    encoded = base64.urlsafe_b64encode(json.dumps(arguments).encode()).decode()
    sys.argv = ["moonraker_octoeverywhere", encoded]
    runpy.run_module("moonraker_octoeverywhere", run_name="__main__")


if __name__ == "__main__":
    main()
