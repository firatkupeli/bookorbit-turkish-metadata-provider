import asyncio
import time
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest

from app.cache import MetadataCache
from app.config import Settings
from app.errors import ProviderError
from app.http import SITE, SourceHttpClient, retry_seconds
from app.models import Book, SearchRequest, SearchResult
from app.service import ProviderService
from app.sources.base import SourceRegistry
from app.sources.kitapyurdu import KitapyurduSource, clean_book_url, parse_book, parse_search
from app.text import fold, isbn13, normalize_isbn, plain_text
from tests.conftest import FIXTURES


@pytest.mark.parametrize(
    "text,want",
    [
        ("978-605-295-792-9", "9786052957929"),
        ("0-306-40615-2", "0306406152"),
        ("080442957X", "080442957X"),
        ("9786052957920", None),
        ("0000000000000", None),
        ("invalid", None),
        ("9786052957929<script>", None),
    ],
)
def test_isbn_validation(text, want):
    assert normalize_isbn(text) == want


def test_isbn10_conversion_and_turkish_fold():
    assert isbn13("0306406152") == "9780306406157"
    assert fold("ÇIĞ İŞIK öyküsü") == fold("cig isik oykusu")
    assert (
        plain_text("<p>Türkçe açıklama.</p><script>bad()</script><p>İkinci paragraf.</p>")
        == "Türkçe açıklama.\n\nİkinci paragraf."
    )


def test_real_search_fixture_has_unique_books_only():
    links = parse_search((FIXTURES / "search-title.html").read_text(encoding="utf-8"))
    assert links[0].endswith("/51855.html")
    assert len(links) == len(set(links))
    assert all("?" not in url and "/kitap/" in url for url in links)


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/kitap/a/1.html",
        "http://www.kitapyurdu.com/kitap/a/1.html",
        "//127.0.0.1/kitap/a/1.html",
        "/urun/a/1.html",
        "https://www.kitapyurdu.com.evil.example/kitap/a/1.html",
    ],
)
def test_untrusted_links_are_discarded(url):
    assert clean_book_url(url) is None


def test_wrong_book_identity_is_failure():
    with pytest.raises(ProviderError, match="identity_mismatch"):
        parse_book((FIXTURES / "book-51855.html").read_text(encoding="utf-8"), "999")


async def test_429_pauses_all_subsequent_source_requests():
    calls = []

    def handle(request):
        calls.append(request)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(429, headers={"Retry-After": "30"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        source = SourceHttpClient(Settings(_env_file=None, source_interval_seconds=0), client)
        for _ in range(2):
            with pytest.raises(ProviderError) as error:
                await source.get(SITE + "/index.php")
            assert error.value.status == 429
            assert 1 <= error.value.retry_after <= 30
    assert len(calls) == 2


@pytest.mark.parametrize("status", [403, 404, 500])
async def test_robots_fail_closed(status):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(status))
    ) as client:
        with pytest.raises(ProviderError) as error:
            await SourceHttpClient(Settings(_env_file=None), client).get(SITE + "/index.php")
        assert error.value.status == 503


async def test_robots_blocked_path_never_requested():
    paths = []

    def handle(request):
        paths.append(request.url.path)
        return httpx.Response(200, text="User-agent: *\nDisallow: /img/\n")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ProviderError, match="robots_disallowed"):
            await SourceHttpClient(Settings(_env_file=None, source_interval_seconds=0), client).get(
                SITE + "/img/cover.jpg"
            )
    assert paths == ["/robots.txt"]


async def test_redirect_to_private_address_is_never_followed():
    calls = []

    def handle(request):
        calls.append(request)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(302, headers={"Location": "http://127.0.0.1/secret"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ProviderError, match="unsafe_source_url"):
            await SourceHttpClient(Settings(_env_file=None, source_interval_seconds=0), client).get(
                SITE + "/index.php"
            )
    assert len(calls) == 2


async def test_source_request_starts_are_spaced():
    starts = []

    def handle(request):
        starts.append(time.monotonic())
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(200, text="<html></html>", headers={"Content-Type": "text/html"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        source = SourceHttpClient(Settings(_env_file=None, source_interval_seconds=0.03), client)
        await asyncio.gather(*(source.get(SITE + "/index.php") for _ in range(3)))
    assert all(b - a >= 0.025 for a, b in zip(starts, starts[1:], strict=False))


async def test_oversized_response_and_timeout_are_failures():
    for body, code in [
        (b"x" * (2 * 1024 * 1024 + 1), "source_response_too_large"),
        (None, "source_timeout"),
    ]:

        def handle(request, body=body):
            if request.url.path == "/robots.txt":
                return httpx.Response(200, text="User-agent: *\nAllow: /\n")
            if body is None:
                raise httpx.ReadTimeout("sensitive-url", request=request)
            return httpx.Response(200, content=body, headers={"Content-Type": "text/html"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            with pytest.raises(ProviderError, match=code):
                await SourceHttpClient(
                    Settings(_env_file=None, source_interval_seconds=0), client
                ).get(SITE + "/index.php")


def test_retry_after_dates_and_invalid_values():
    assert retry_seconds("20") == 20
    assert retry_seconds("bad") == 60
    assert retry_seconds("-1") == 1
    assert 28 <= retry_seconds(format_datetime(datetime.now(UTC) + timedelta(seconds=30))) <= 30


async def test_partial_failure_is_not_cached():
    book = Book(providerId="test:1", title="Türkçe", url="https://example.org/book/1")

    class PartialSource:
        key = "test"
        calls = 0

        async def search(self, request, deadline):
            self.calls += 1
            return SearchResult(matches=[book], partial=True)

        async def lookup(self, source_id):
            return None

    source = PartialSource()
    service = ProviderService(
        Settings(_env_file=None), SourceRegistry([source]), MetadataCache(10240, 1, 1)
    )
    for _ in range(2):
        result = await service.search(SearchRequest(query="Türkçe"))
        assert result.partial
    assert source.calls == 2


async def test_all_source_failures_are_502_not_empty():
    class FailedSource:
        key = "failed"

        async def search(self, request, deadline):
            raise ProviderError("source_broken")

        async def lookup(self, source_id):
            return None

    service = ProviderService(
        Settings(_env_file=None), SourceRegistry([FailedSource()]), MetadataCache(10240, 1, 1)
    )
    with pytest.raises(ProviderError, match="source_broken"):
        await service.search(SearchRequest(query="example"))


async def test_deadline_returns_progress_as_partial(source_transport):
    settings = Settings(_env_file=None, source_interval_seconds=0)
    cache = MetadataCache(102400, 60, 60)

    async def handle(request):
        if request.url.params.get("product_id") not in (None, "51855"):
            await asyncio.sleep(1)
        return await source_transport[0].handle_async_request(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        source = KitapyurduSource(SourceHttpClient(settings, client), cache)
        first = await source.lookup("51855")
        assert first
        result = await source.search(
            SearchRequest(query="Otomatik Portakal (Ciltsiz)", limit=5), time.monotonic() + 0.2
        )
        assert result.partial
        assert result.matches[0].providerId == "kitapyurdu:51855"


def test_cache_is_bounded_and_expires():
    cache = MetadataCache(2048, 0.01, 0.01)
    result = SearchResult(
        matches=[Book(providerId="test:1", title="Türkçe", url="https://example.org")]
    )
    for i in range(20):
        cache.put(cache.searches, str(i), result)
    assert cache.searches.currsize <= 1024
    cache.searches.expire(time.monotonic() + 1)
    assert not cache.searches
