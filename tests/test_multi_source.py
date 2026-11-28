"""Combined BookOrbit search, source isolation, and stable saved book IDs."""

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.cache import MetadataCache
from app.config import Settings
from app.models import Book, SearchRequest, SearchResult
from app.service import ProviderService
from app.sources.base import SourceRegistry
from tests.conftest import make_source_transport
from tests.test_binkitap import fixture_book
from tests.test_epub_editor import HEADERS

PARAMS = {
    "query": "Otomatik Portakal",
    "author": "Anthony Burgess",
    "isbn": "9786052957929",
    "limit": 3,
}
IDS = ["kitapyurdu:51855", "1000kitap:488817"]


def both_transport(failed_hosts=None):
    kitapyurdu, _ = make_source_transport()
    failed_hosts = failed_hosts if failed_hosts is not None else set()
    calls = []

    async def handle(request):
        calls.append(request)
        if request.url.host in failed_hosts and request.url.path != "/robots.txt":
            return httpx.Response(503)
        if request.url.host != "1000kitap.com":
            return await kitapyurdu.handle_async_request(request)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        if request.url.path == "/ara":
            body = '<main class="govde-arama"><a href="/kitap/deneme--488817">Kitap</a></main>'
        elif request.url.path == "/kitap/488817":
            body = fixture_book(isbn=PARAMS["isbn"], author=PARAMS["author"])
            body = body.replace("Deneme Kitab", "Otomatik Portakal Kitab")
        else:
            return httpx.Response(404)
        return httpx.Response(200, text=body, headers={"Content-Type": "text/html"})

    return httpx.MockTransport(handle), calls


def test_same_bookorbit_endpoint_searches_both_sources_and_keeps_both_edition_ids():
    transport, calls = both_transport()
    with TestClient(
        create_app(Settings(_env_file=None, source_interval_seconds=0), transport)
    ) as api:
        info = api.get("/provider/info").json()
        assert info["key"] == "turkish-metadata"
        assert info["lookup"] and info["idMaxLength"] == 32
        response = api.get("/search", params=PARAMS)
        assert response.status_code == 200, response.text
        assert [book["providerId"] for book in response.json()["matches"]] == IDS
        assert response.json()["partial"] is False
        assert all(book["isbn13"] == PARAMS["isbn"] for book in response.json()["matches"])
        assert {r.url.host for r in calls} == {"www.kitapyurdu.com", "1000kitap.com"}
        before = len(calls)
        assert api.get("/search", params=PARAMS).json() == response.json()
        assert len(calls) == before


@pytest.mark.parametrize("failed_host", ["www.kitapyurdu.com", "1000kitap.com"])
def test_either_source_failure_keeps_other_results_and_recovery_is_not_cached(failed_host):
    failed = {failed_host}
    transport, _ = both_transport(failed)
    with TestClient(
        create_app(Settings(_env_file=None, source_interval_seconds=0), transport)
    ) as api:
        response = api.get("/search", params=PARAMS)
        assert response.status_code == 200, response.text
        assert response.json()["partial"] is True
        assert len(response.json()["matches"]) == 1
        expected = "1000kitap:" if failed_host == "www.kitapyurdu.com" else "kitapyurdu:"
        assert response.json()["matches"][0]["providerId"].startswith(expected)
        failed.clear()
        recovered = api.get("/search", params=PARAMS).json()
        assert [book["providerId"] for book in recovered["matches"]] == IDS
        assert recovered["partial"] is False


def test_saved_ids_from_both_sources_work_after_restart_without_search():
    settings = Settings(_env_file=None, source_interval_seconds=0)
    transport, _ = both_transport()
    with TestClient(create_app(settings, transport)) as api:
        books = api.get("/search", params=PARAMS).json()["matches"]
    restarted_transport, calls = both_transport()
    with TestClient(create_app(settings, restarted_transport)) as restarted:
        for book in books:
            response = restarted.get("/book/" + book["providerId"])
            assert response.status_code == 200, response.text
            assert response.json() == book
    assert not any(r.url.path == "/ara" or "filter_name" in r.url.params for r in calls)


def test_single_source_web_searches_and_combined_api_cache_cannot_contaminate_each_other():
    transport, calls = both_transport()
    with TestClient(
        create_app(Settings(_env_file=None, source_interval_seconds=0), transport)
    ) as api:
        first = api.get(
            "/web/search", params={**PARAMS, "source": "kitapyurdu"}, headers=HEADERS
        ).json()
        assert [book["providerId"] for book in first["matches"]] == IDS[:1]
        assert not any(r.url.host == "1000kitap.com" for r in calls)
        combined = api.get("/search", params=PARAMS).json()
        assert [book["providerId"] for book in combined["matches"]] == IDS
        second = api.get(
            "/web/search", params={**PARAMS, "source": "1000kitap"}, headers=HEADERS
        ).json()
        assert [book["providerId"] for book in second["matches"]] == IDS[1:]
        assert (
            api.get("/web/search", params={**PARAMS, "source": "all"}, headers=HEADERS).json()
            == combined
        )


async def test_both_sources_get_room_in_a_limited_result_list():
    class Source:
        def __init__(self, key):
            self.key = key

        async def search(self, request, deadline):
            return SearchResult(
                matches=[
                    Book(providerId=f"{self.key}:{i}", title="Book", url="https://example.org")
                    for i in range(5)
                ]
            )

    service = ProviderService(
        Settings(_env_file=None),
        SourceRegistry([Source("kitapyurdu"), Source("1000kitap")]),
        MetadataCache(102400, 60, 60),
    )
    result = await service.search(SearchRequest(query="Book", limit=3))
    assert [book.providerId for book in result.matches] == [
        "kitapyurdu:0",
        "1000kitap:0",
        "kitapyurdu:1",
    ]


@pytest.mark.parametrize("slow_key", ["kitapyurdu", "1000kitap"])
async def test_slow_source_cannot_prevent_other_source_from_searching(slow_key):
    fast_ran = asyncio.Event()
    cancelled = asyncio.Event()

    class Source:
        def __init__(self, key):
            self.key = key

        async def search(self, request, deadline):
            if self.key == slow_key:
                try:
                    async with asyncio.timeout_at(deadline):
                        await asyncio.Event().wait()
                finally:
                    cancelled.set()
            fast_ran.set()
            return SearchResult(
                matches=[Book(providerId=self.key + ":1", title="Book", url="https://example.org")]
            )

    service = ProviderService(
        Settings(_env_file=None, deadline_seconds=0.05),
        SourceRegistry([Source("kitapyurdu"), Source("1000kitap")]),
        MetadataCache(102400, 60, 60),
    )
    result = await asyncio.wait_for(service.search(SearchRequest(query="Book")), timeout=1)
    assert fast_ran.is_set() and cancelled.is_set()
    assert result.partial and len(result.matches) == 1
    assert not result.matches[0].providerId.startswith(slow_key + ":")


def test_real_source_keeps_matches_collected_before_its_deadline():
    normal, _ = both_transport()

    async def handle(request):
        if request.url.host == "www.kitapyurdu.com" and request.url.params.get(
            "product_id"
        ) not in (None, "51855"):
            await asyncio.sleep(1)
        return await normal.handle_async_request(request)

    with TestClient(
        create_app(
            Settings(_env_file=None, source_interval_seconds=0, deadline_seconds=0.1),
            httpx.MockTransport(handle),
        )
    ) as api:
        assert api.get("/book/kitapyurdu:51855").status_code == 200
        response = api.get("/search", params={"query": "Otomatik Portakal (Ciltsiz)", "limit": 5})
        assert response.status_code == 200, response.text
        assert response.json()["partial"] is True
        assert {book["providerId"] for book in response.json()["matches"]} == set(IDS)
