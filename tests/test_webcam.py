from pathlib import Path
import importlib.util
import unittest
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location("opencreator_webcam", Path(__file__).resolve().parents[1] / "scripts/opencreator_webcam.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CameraTests(unittest.TestCase):
    def test_default_snapshot_and_stream_bypass_redirect(self):
        for action in ("snapshot", "stream"):
            self.assertEqual(module.normalize_camera_url("/webcam/?action=" + action), "http://127.0.0.1:8080/?action=" + action)

    def test_additional_opencreator_ports(self):
        for index in (2, 3, 4):
            self.assertEqual(module.normalize_camera_url("/webcam%d/?action=snapshot" % index), "http://127.0.0.1:%d/?action=snapshot" % (8079 + index))

    def test_localhost_form_and_empty_urls(self):
        self.assertEqual(module.normalize_camera_url("http://localhost/webcam/?action=snapshot"), "http://127.0.0.1:8080/?action=snapshot")
        self.assertIsNone(module.normalize_camera_url(None))
        self.assertEqual(module.normalize_camera_url(""), "")

    def test_explicit_other_cameras_are_preserved(self):
        for url in ("http://camera.lan/webcam/?action=snapshot", "rtsp://camera.lan/stream", "http://127.0.0.1:9999/webcam/", "/custom-camera/?action=snapshot"):
            self.assertEqual(module.normalize_camera_url(url), url)

    def test_fluidd_camera_relay_uses_direct_port(self):
        http = SimpleNamespace(MakeHttpCall=lambda *args, **kwargs: (args, kwargs))
        module.patch_http_requests(http, SimpleNamespace(Absolute=2))
        args, kwargs = http.MakeHttpCall(None, "/webcam/?action=snapshot", 1, "GET", headers={"X-Test": "preserved"})
        self.assertEqual(args, (None, "http://127.0.0.1:8080/?action=snapshot", 2, "GET"))
        self.assertEqual(kwargs["headers"], {"X-Test": "preserved"})

    def test_non_camera_relay_requests_are_unchanged(self):
        http = SimpleNamespace(MakeHttpCall=lambda *args, **kwargs: args)
        module.patch_http_requests(http, SimpleNamespace(Absolute=2))
        self.assertEqual(http.MakeHttpCall(None, "/server/info", 1, "GET"), (None, "/server/info", 1, "GET"))
