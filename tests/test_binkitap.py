import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.cache import MetadataCache
from app.config import Settings
from app.errors import ProviderError
from app.http import SourceHttpClient
from app.models import SearchRequest
from app.sources.binkitap import BinKitapSource, candidates, parse_book
from tests.test_epub_editor import HEADERS
from tests.test_manual_cover import cover_image


def fixture_book(identifier="488817", isbn="9786257440820", author="Deneme Yazar"):
    data = {
        "@type": "Book",
        "name": "Deneme Kitabı",
        "url": "https://1000kitap.com/kitap/deneme--" + identifier,
        "author": {"name": author},
        "publisher": {"name": "Deneme Yayınları"},
        "image": "https://1k-cdn.com/resimler/kitaplar/test.jpg",
        "isbn": isbn,
        "description": "Üretilmiş deneme metni.",
        "numberOfPages": 232,
        "inLanguage": "Türkçe",
        "datePublished": "2023-07-01",
    }
    return '<script type="application/ld+json">' + json.dumps(data) + "</script>"


def fixture_transport():
    calls = []

    def handle(request):
        calls.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        if request.url.host == "1k-cdn.com":
            return httpx.Response(
                200, content=cover_image(), headers={"content-type": "image/jpeg"}
            )
        if request.url.path == "/ara":
            return httpx.Response(
                200,
                text='<main class="govde-arama"><a href="/kitap/deneme--488817">Deneme</a></main>',
                headers={"content-type": "text/html"},
            )
        if request.url.path == "/kitap/488817":
            return httpx.Response(200, text=fixture_book(), headers={"content-type": "text/html"})
        return httpx.Response(404)

    return httpx.MockTransport(handle), calls


def test_jsonld_and_candidate_identity_are_verified():
    book = parse_book(fixture_book(), "488817")
    assert book.isbn13 == "9786257440820" and book.languageCode == "tr"
    assert book.providerId == "1000kitap:488817"
    with pytest.raises(ProviderError):
        parse_book(fixture_book(), "1")
    assert (
        candidates(
            '<main class="govde-arama"><a href="https://evil.example/kitap/test--1">wrong</a>'
            "Gösterilecek içerik bulunamadı.</main>"
        )
        == []
    )


@pytest.mark.asyncio
async def test_exact_isbn_wrong_author_and_cold_lookup():
    transport, _ = fixture_transport()
    async with httpx.AsyncClient(transport=transport) as client:
        source = BinKitapSource(
            SourceHttpClient(
                Settings(_env_file=None, source_interval_seconds=0),
                client,
                site="https://1000kitap.com",
            ),
            MetadataCache(1000000, 100, 100),
        )
        assert (await source.lookup("488817")).isbn13 == "9786257440820"
        found = await source.search(
            SearchRequest(query="Deneme", isbn="9786257440820"), time.monotonic() + 5
        )
        assert len(found.matches) == 1
        assert not (
            await source.search(
                SearchRequest(query="Deneme", isbn="9786255539007"), time.monotonic() + 5
            )
        ).matches
        assert not (
            await source.search(
                SearchRequest(query="Deneme", author="Farklı Yazar"), time.monotonic() + 5
            )
        ).matches


def test_web_selection_keeps_bookorbit_identity_and_both_api_sources():
    transport, calls = fixture_transport()
    with TestClient(
        create_app(Settings(_env_file=None, source_interval_seconds=0), transport)
    ) as api:
        result = api.get(
            "/web/search",
            params={"source": "1000kitap", "query": "Deneme", "isbn": "9786257440820"},
            headers=HEADERS,
        )
        assert result.status_code == 200, result.text
        assert result.json()["matches"][0]["providerId"] == "1000kitap:488817"
        assert list(api.app.state.service.registry.sources) == ["kitapyurdu", "1000kitap"]
        assert api.get("/provider/info").json()["key"] == "turkish-metadata"
        image = api.get("/web/cover/1000kitap:488817", headers=HEADERS)
        assert image.status_code == 200
        assert image.headers["x-image-width"] == "120"
        assert all("evil.example" not in url for url in calls)


def test_unknown_source_and_missing_guard_do_not_silently_fall_back(client):
    api, _ = client
    assert api.get("/web/search?source=amazon&query=x", headers=HEADERS).status_code == 400
    assert api.get("/web/search?source=1000kitap&query=x").status_code == 403
