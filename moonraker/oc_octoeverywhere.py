"""Stable Moonraker entry: reload implementation even after an in-process restart."""
from pathlib import Path
import runpy


def load_component(config):
    # OpenCreator may restart Server without replacing its Python process.
    # run_path compiles current source on each load, without .pyc reuse.
    source = Path(__file__).resolve().with_name("oc_octoeverywhere_impl.py")
    namespace = runpy.run_path(str(source))
    return namespace["load_component"](config)
