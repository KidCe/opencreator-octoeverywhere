import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest


class ComponentReloadTests(unittest.TestCase):
    def test_same_loaded_entry_reads_changed_source_on_next_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entry = root / "oc_octoeverywhere.py"
            shutil.copy2(Path(__file__).resolve().parents[1] / "moonraker/oc_octoeverywhere.py", entry)
            impl = root / "oc_octoeverywhere_impl.py"
            impl.write_text("def load_component(config): return 'version-1'\n")
            spec = importlib.util.spec_from_file_location("oc_stable_entry", entry)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.assertEqual(module.load_component(None), "version-1")
            # Same source size, process and already loaded entry; a cached
            # import or timestamp-based bytecode can miss this edit.
            impl.write_text("def load_component(config): return 'version-2'\n")
            self.assertEqual(module.load_component(None), "version-2")
