"""Check dependencies and the adapter's upstream interfaces without starting a daemon."""
import importlib
import inspect
from pathlib import Path
import subprocess
import sys


def check(repo):
    sys.path.insert(0, str(Path(repo).resolve()))
    for name in ("PIL._imaging", "octowebsocket", "octoflatbuffers", "requests", "httpx", "rsa", "dns", "sentry_sdk", "qrcode"):
        importlib.import_module(name)
    from moonraker_octoeverywhere.uiinjector import UiInjector
    from moonraker_octoeverywhere.moonrakerwebcamhelper import MoonrakerWebcamHelper
    from octoeverywhere.octohttprequest import OctoHttpRequest, PathTypes
    from linux_host.config import Config
    checks = (
        (callable(UiInjector.Init), "Upstream UI compatibility interface changed"),
        (callable(MoonrakerWebcamHelper.GetWebcamConfig), "Upstream webcam interface changed"),
        (list(inspect.signature(OctoHttpRequest.MakeHttpCall).parameters)[:3] == ["logger", "pathOrUrl", "pathOrUrlType"], "Upstream relay interface changed"),
        (hasattr(PathTypes, "Absolute"), "Upstream URL type interface changed"),
        (hasattr(Config, "GeneralSection"), "Upstream config interface changed"),
    )
    for valid, error in checks:
        if not valid:
            raise RuntimeError(error)
    subprocess.run([sys.executable, "-m", "pip", "check"], check=True)


if __name__ == "__main__":
    check(sys.argv[1])
    print("Dependencies and upstream adapter interfaces OK")
