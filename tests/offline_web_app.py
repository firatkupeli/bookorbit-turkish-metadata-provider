"""Local UI verification using fixture metadata and an original generated cover.

Never copied into the production Docker image. No requests leave this process.
"""

import struct
import zlib

import httpx

from app.api import create_app
from app.config import Settings
from tests.conftest import make_source_transport


def fixture_cover():
    def chunk(kind, payload):
        return (
            struct.pack("!I", len(payload))
            + kind
            + payload
            + struct.pack("!I", zlib.crc32(kind + payload))
        )

    pixels = b"".join(b"\x00" + bytes((23, 99, 78)) * 64 for _ in range(96))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack("!2I5B", 64, 96, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(pixels))
        + chunk(b"IEND", b"")
    )


source, _calls = make_source_transport()


def handle(request):
    if request.url.host == "img.kitapyurdu.com":
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        return httpx.Response(200, content=fixture_cover(), headers={"content-type": "image/png"})
    return source.handle_request(request)


app = create_app(Settings(_env_file=None, source_interval_seconds=0), httpx.MockTransport(handle))
