"""Set up upstream-owned updates on OpenCreator's Creator 5 Pro SoC.

Run with OpenCreator's hard-float Python while idle, before restarting Moonraker.
The old environment and account identity are retained when upgrading from 0.1.
"""
from pathlib import Path
import argparse
import configparser
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
import uuid

ORIGIN = "https://github.com/QuinnDamerell/OctoPrint-OctoEverywhere.git"
BRANCH = "master"
IDLE_STATES = {"standby", "complete", "cancelled", "error"}
OPENCREATOR_CONFIG = Path("/usr/data/opencreator/klipper/config")


def require_idle(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1"} or parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.username:
        raise RuntimeError("Moonraker must be a loopback HTTP URL")
    with urllib.request.urlopen(url.rstrip("/") + "/printer/objects/query?print_stats", timeout=10) as response:
        state = json.load(response)["result"]["status"]["print_stats"]["state"]
    if state not in IDLE_STATES:
        raise RuntimeError("Printer must be idle; state=" + state)


def clean_environment():
    env = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME", "PIP_TARGET", "PIP_PREFIX", "PIP_USER"):
        env.pop(key, None)
    env.update(PYTHONNOUSERSITE="1", PIP_DISABLE_PIP_VERSION_CHECK="1",
               PIP_ONLY_BINARY=":all:", GIT_TERMINAL_PROMPT="0")
    env["PATH"] = env.get("PATH", "") + ":/opt/bin"
    return env


def run(*args, cwd=None, env=None, capture=False):
    return subprocess.run(list(map(str, args)), cwd=cwd, env=env, check=True,
                          text=True, stdout=subprocess.PIPE if capture else None).stdout


def atomic_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)


def latest_release(tags):
    versions = [tag for tag in tags.splitlines() if re.fullmatch(r"\d+\.\d+\.\d+", tag)]
    if not versions:
        raise RuntimeError("Upstream has no numeric release tag")
    return max(versions, key=lambda v: tuple(map(int, v.split("."))))


def write_config(root, moonraker_url, frontend_port):
    path = root / "config/octoeverywhere.conf"
    config = configparser.ConfigParser(interpolation=None)
    config.read(path)
    for name in ("companion", "relay", "logging"):
        if not config.has_section(name):
            config.add_section(name)
    config.set("companion", "ip_or_hostname", "127.0.0.1")
    config.set("companion", "port", str(urllib.parse.urlsplit(moonraker_url).port or 80))
    config.set("relay", "frontend_port", str(frontend_port))
    config.set("relay", "frontend_type_hint", "Fluidd")
    # Preserve user choices on repeat setup.
    for key, value in (("max_file_size_mb", "2"), ("max_file_count", "2")):
        if not config.has_option("logging", key):
            config.set("logging", key, value)
    temporary = path.with_suffix(".tmp")
    with temporary.open("w") as stream:
        config.write(stream)
    temporary.chmod(0o600)
    temporary.replace(path)


def setup(args):
    if sys.platform != "linux" or sys.version_info < (3, 11):
        raise RuntimeError("Use OpenCreator's Linux hard-float Python 3.11+ on the printer")
    if not OPENCREATOR_CONFIG.is_dir():
        raise RuntimeError("This release supports OpenCreator on the Creator 5 Pro SoC only")
    import fcntl
    require_idle(args.moonraker_url)
    os.umask(0o077)
    root = args.runtime.expanduser().resolve()
    if any(char.isspace() for char in str(root)):
        raise RuntimeError("Use a runtime path without whitespace for native Moonraker updates")
    if root in (Path("/"), Path("/usr"), Path("/usr/data"), Path("/usr/data/opencreator")):
        raise RuntimeError("Select a dedicated runtime directory")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (root / "setup.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = root / "runtime.json"
        old = json.loads(manifest.read_text()) if manifest.exists() else {}
        if old.get("schema") == 2 and not args.rebuild:
            # Setup isn't a second updater. Repeated installs retain the current
            # upstream checkout, dependencies, private config and account.
            if args.ref:
                raise RuntimeError("--ref applies to first setup only; use Moonraker for updates")
            print("Runtime already configured; use Fluidd's octoeverywhere update entry.")
            return
        for name in ("config", "storage", "logs", "envs"):
            (root / name).mkdir(exist_ok=True, mode=0o700)
        env = clean_environment()
        git = shutil.which("git", path=env["PATH"])
        if not git:
            raise RuntimeError("OpenCreator git is missing; repair OpenCreator before installing")
        # Build in permanent, unique paths: venv scripts contain absolute paths.
        generation = uuid.uuid4().hex[:12]
        repo = root / ("upstream-" + generation)
        venv = root / "envs" / generation
        constraints = root / ("native-" + generation + ".txt")
        committed = False
        try:
            run(git, "-c", "pack.threads=1", "clone", "--single-branch", "--branch", BRANCH, ORIGIN, repo, env=env)
            tags = run(git, "tag", "--list", cwd=repo, env=env, capture=True)
            release = args.ref or latest_release(tags)
            if not re.fullmatch(r"\d+\.\d+\.\d+", release) or release not in tags.splitlines():
                raise RuntimeError("Initial release must be an existing upstream numeric tag")
            run(git, "checkout", "-B", BRANCH, "refs/tags/" + release, cwd=repo, env=env)
            run(git, "branch", "--set-upstream-to=origin/" + BRANCH, BRANCH, cwd=repo, env=env)
            run(sys.executable, "-m", "venv", venv, env=env)
            python = venv / "bin/python"
            # Match both the base interpreter and its native Pillow ABI.
            probe = "import json,sys,sysconfig,PIL,PIL._imaging; print(json.dumps([sys.base_prefix,sysconfig.get_paths()['purelib'],PIL.__version__]))"
            base, source, pillow = json.loads(run(args.moonraker_python, "-c", probe, env=env, capture=True))
            if Path(base).resolve() != Path(sys.base_prefix).resolve():
                raise RuntimeError("Run setup with the same base Python used by Moonraker")
            site = Path(run(python, "-c", "import sysconfig;print(sysconfig.get_paths()['purelib'])", env=env, capture=True).strip())
            source = Path(source)
            packages = [source / "PIL", *source.glob("[Pp]illow-*.dist-info"), *source.glob("[Pp]illow.libs")]
            if not any(p.name.lower().endswith(".dist-info") for p in packages):
                raise RuntimeError("Moonraker's native Pillow distribution metadata is missing")
            for package in packages:
                shutil.copytree(package, site / package.name)
            constraints.write_text("# Native ABI supplied by OpenCreator, not by this plugin.\nPillow==" + pillow + "\n")
            env["PIP_CONSTRAINT"] = str(constraints)
            # Upstream owns all requirements. No copied/pinned wheel list is
            # needed for future releases; compiled source builds are forbidden.
            run(python, "-m", "pip", "install", "-r", repo / "requirements.txt", env=env)
            run(python, "-m", "pip", "check", env=env)
            run(python, Path(__file__).with_name("check_runtime.py"), repo, env=env)
            require_idle(args.moonraker_url)
            if args.migrate_from:
                if old or any((root / "storage").iterdir()):
                    raise RuntimeError("Identity migration is only allowed into a new empty runtime")
                previous = args.migrate_from.resolve()
                secret = previous / "storage/octoeverywhere.secrets"
                if previous == root or not secret.is_file():
                    raise RuntimeError("Migration requires a separate runtime containing an identity")
                shutil.copy2(secret, root / "storage/octoeverywhere.secrets")
                (root / "storage/octoeverywhere.secrets").chmod(0o600)
            write_config(root, args.moonraker_url, args.frontend_port)
            if old:
                # Keep the last working manifest alongside its original source
                # and venv; no account files are copied to the distributable.
                backup = root / ("runtime-before-setup-" + generation + ".json")
                atomic_json(backup, old)
            atomic_json(manifest, {"schema": 2, "python": str(python), "repo": str(repo),
                                   "constraints": str(constraints), "initial_release": release})
            committed = True
            print("Runtime prepared. Restart Moonraker while idle to activate it.")
            print("Account linking instructions are in logs/octoeverywhere.log after startup.")
        except BaseException:
            # Only this setup's uniquely-created scratch paths may be removed.
            # Never remove an old generation or the user's storage/config.
            if not committed:
                for path in (repo, venv):
                    if path.exists():
                        shutil.rmtree(path)
                constraints.unlink(missing_ok=True)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, default=Path("/usr/data/opencreator/octoeverywhere"))
    parser.add_argument("--moonraker-url", default="http://127.0.0.1:7125")
    parser.add_argument("--moonraker-python", default="/usr/prog/moonraker/moonraker-env/bin/python")
    parser.add_argument("--frontend-port", type=int, choices=range(1, 65536), default=80, metavar="PORT")
    parser.add_argument("--migrate-from", type=Path, help="Explicitly copy this printer's existing identity; never needed for new users")
    parser.add_argument("--ref", help="Initial upstream release tag for controlled compatibility testing")
    parser.add_argument("--rebuild", action="store_true", help="Explicitly rebuild a fresh environment after an OpenCreator Python/ABI change")
    setup(parser.parse_args())


if __name__ == "__main__":
    main()
