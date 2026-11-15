"""Resolve OpenCreator's local camera redirects without changing its web UI."""
import re
from urllib.parse import urlsplit, urlunsplit


def normalize_camera_url(url):
    if not url:
        return url
    parts = urlsplit(url)
    # Preserve explicit remote/RTSP/other-camera URLs. Only OpenCreator's
    # relative routes or their localhost port-80 forms belong to this adapter.
    if parts.netloc:
        if parts.scheme != "http" or parts.hostname not in ("127.0.0.1", "localhost") or parts.port not in (None, 80):
            return url
    elif parts.scheme:
        return url
    match = re.fullmatch(r"/webcam([234])?/?", parts.path)
    if not match:
        return url
    index = int(match.group(1) or 1)
    return urlunsplit(("http", "127.0.0.1:%d" % (8079 + index), "/", parts.query, ""))


def patch_http_requests(http_class, path_types):
    """Apply the same route fix to Fluidd's requests through the web relay."""
    original = http_class.MakeHttpCall

    def opencreator_http(logger, pathOrUrl, pathOrUrlType, *args, **kwargs):
        normalized = normalize_camera_url(pathOrUrl)
        if normalized != pathOrUrl:
            pathOrUrlType = path_types.Absolute
        return original(logger, normalized, pathOrUrlType, *args, **kwargs)

    http_class.MakeHttpCall = staticmethod(opencreator_http)
