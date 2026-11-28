from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.config import Settings

FIXTURES = Path(__file__).parent / "fixtures"


def make_source_transport():
    calls = []

    def handle(request: httpx.Request):
        calls.append(request)
        params = parse_qs(request.url.query.decode())
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /admin/\nDisallow: /img/\n")
        if request.url.host == "1000kitap.com" and request.url.path == "/ara":
            return httpx.Response(
                200,
                text='<main class="govde-arama">Gösterilecek içerik bulunamadı.</main>',
                headers={"Content-Type": "text/html"},
            )
        if params.get("route") == ["product/list"]:
            name = params.get("filter_name", [""])[0]
            fixture = (
                "search-empty.html" if name in ("missing", "9786052957929") else "search-title.html"
            )
            return httpx.Response(
                200,
                text=(FIXTURES / fixture).read_text(encoding="utf-8"),
                headers={"Content-Type": "text/html; charset=utf-8"},
            )
        if params.get("product_id") == ["51855"]:
            return httpx.Response(
                200,
                text=(FIXTURES / "book-51855.html").read_text(encoding="utf-8"),
                headers={"Content-Type": "text/html"},
            )
        return httpx.Response(404)

    return httpx.MockTransport(handle), calls


@pytest.fixture
def source_transport():
    return make_source_transport()


@pytest.fixture
def client(source_transport):
    transport, calls = source_transport
    app = create_app(Settings(_env_file=None, source_interval_seconds=0), transport)
    with TestClient(app) as client:
        yield client, calls
