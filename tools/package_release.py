"""Package plugin source only; never include device runtime or credentials."""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    if output.is_relative_to(root):
        raise RuntimeError("Choose an output directory outside plugin source")
    output.mkdir(parents=True, exist_ok=True)
    paths = [root / name for name in ("README.md", "LICENSE", "NOTICE",
             "VALIDATION.md", ".gitignore", ".gitattributes", "install.sh", "opencreator-plugin.json")]
    # Explicit source allow-list excludes incidental logs, backups and runtime.
    for directory in ("config", "moonraker", "scripts", "tests", "tools", "docs", ".github/workflows"):
        paths.extend(p for p in (root / directory).rglob("*")
                     if p.is_file() and "__pycache__" not in p.parts and p.suffix in {".py", ".md", ".conf", ".yml", ".patch"})
    paths = sorted(set(paths))
    if any(not p.resolve().is_relative_to(root) or p.is_symlink() for p in paths):
        raise RuntimeError("Release sources must be ordinary files inside the plugin")
    manifest = root / "PACKAGE-SHA256.json"
    manifest.write_text(json.dumps({p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in paths}, indent=2) + "\n", newline="\n")
    version = json.loads((root / "opencreator-plugin.json").read_text())["version"]
    archive = output / ("opencreator-octoeverywhere-" + version + ".zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for path in paths + [manifest]:
            item = zipfile.ZipInfo("octoeverywhere/" + path.relative_to(root).as_posix(), (2026, 1, 1, 0, 0, 0))
            item.external_attr = 0o100644 << 16
            item.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(item, path.read_bytes())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(digest + "  " + archive.name + "\n", newline="\n")
    print(archive)
    print("SHA256 " + digest)


if __name__ == "__main__":
    main()
