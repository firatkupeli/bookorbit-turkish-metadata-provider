"""Regressions derived from the upstream Kakao/YES24 review, using Kitapyurdu fixtures."""

import json

import httpx
import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from app.api import create_app
from app.cache import MetadataCache
from app.config import Settings
from app.errors import ProviderError
from app.models import SearchRequest
from app.service import ProviderService
from app.sources.base import SourceRegistry
from app.sources.kitapyurdu import parse_book
from app.text import fold, normalize_isbn
from tests.conftest import FIXTURES, make_source_transport

ISBN = "9786052957929"
PARAMS = {
    "query": "Otomatik Portakal",
    "author": "Anthony Burgess",
    "isbn": ISBN,
    "limit": 1,
}


@pytest.mark.parametrize(
    "value",
    ["0000000000", "978６０５２９５７９２９", "０３０６４０６１５２"],
)
def test_placeholder_or_non_ascii_isbn_is_not_valid(value):
    assert normalize_isbn(value) is None


@pytest.mark.parametrize("value", ["0000000000", "9786052957920", "not-an-isbn"])
def test_invalid_isbn_with_title_uses_text_search(client, value):
    api, calls = client
    response = api.get("/search", params={**PARAMS, "isbn": value})
    assert response.status_code == 200
    assert response.json()["matches"][0]["isbn13"] == ISBN
    assert response.json()["matches"][0]["authors"] == ["Anthony Burgess"]
    terms = [r.url.params["filter_name"] for r in calls if "filter_name" in r.url.params]
    assert terms == ["Otomatik Portakal Anthony Burgess"]


@pytest.mark.parametrize("value", ["0000000000", "9786052957920"])
def test_invalid_isbn_without_text_is_400_and_never_fetches_source(client, value):
    api, calls = client
    response = api.get("/search", params={"isbn": value})
    assert response.status_code == 400
    assert response.json() == {"error": "invalid_isbn"}
    assert not calls


def test_valid_isbn_still_has_priority_over_title(client):
    api, calls = client
    response = api.get("/search", params=PARAMS)
    assert response.status_code == 200
    assert response.json()["matches"][0]["isbn13"] == ISBN
    terms = [r.url.params["filter_name"] for r in calls if "filter_name" in r.url.params]
    assert terms[0] == ISBN
    assert terms[1] == "Otomatik Portakal Anthony Burgess"


def test_source_placeholder_isbn_is_omitted_instead_of_converted():
    html = (FIXTURES / "book-51855.html").read_text(encoding="utf-8")
    book = parse_book(html.replace(ISBN, "0000000000"), "51855")
    assert book.isbn13 is None
    assert book.isbn10 is None


def test_lookup_survives_app_restart_before_another_search():
    first_transport, _ = make_source_transport()
    settings = Settings(_env_file=None, source_interval_seconds=0)
    with TestClient(create_app(settings, first_transport)) as first:
        before = first.get("/search", params=PARAMS).json()["matches"][0]
    # New application lifespan means a fresh cache, HTTP client and source registry.
    second_transport, calls = make_source_transport()
    with TestClient(create_app(settings, second_transport)) as restarted:
        response = restarted.get("/book/" + before["providerId"])
    assert response.status_code == 200
    assert response.json() == before
    assert not any("filter_name" in request.url.params for request in calls)
    assert any(request.url.params.get("product_id") == "51855" for request in calls)


@pytest.mark.parametrize("upstream_status,api_status", [(429, 429), (503, 502)])
def test_isbn_miss_then_title_failure_is_not_successful_empty(upstream_status, api_status):
    normal, calls = make_source_transport()
    failing = True

    async def handle(request):
        if (
            failing
            and request.url.params.get("route") == "product/list"
            and request.url.params.get("filter_name") != ISBN
        ):
            return httpx.Response(upstream_status, headers={"Retry-After": "11"})
        return await normal.handle_async_request(request)

    app = create_app(
        Settings(_env_file=None, source_interval_seconds=0), httpx.MockTransport(handle)
    )
    with TestClient(app) as api:
        response = api.get("/search", params=PARAMS)
        assert response.status_code == api_status
        assert "matches" not in response.json()
        failing = False
        retry = api.get("/search", params=PARAMS)
        if upstream_status == 429:
            assert response.headers["Retry-After"] == "11"
            assert retry.status_code == 429
        else:
            assert retry.status_code == 200
            assert retry.json()["matches"][0]["isbn13"] == ISBN
    assert calls


def test_later_throttling_takes_priority_over_earlier_detail_failure():
    normal, _ = make_source_transport()
    details = 0

    async def handle(request):
        nonlocal details
        if request.url.params.get("route") == "product/product":
            details += 1
            return httpx.Response(503 if details == 1 else 429, headers={"Retry-After": "13"})
        return await normal.handle_async_request(request)

    app = create_app(
        Settings(_env_file=None, source_interval_seconds=0), httpx.MockTransport(handle)
    )
    with TestClient(app) as api:
        response = api.get("/search", params=PARAMS)
        assert response.status_code == 429
        assert response.headers["Retry-After"] == "13"
        assert api.get("/search", params=PARAMS).status_code == 429
    assert details == 2


async def test_registry_preserves_throttle_status_from_a_later_source():
    class FailedSource:
        key = "failed"

        async def search(self, request, deadline):
            raise ProviderError("upstream_error", 502)

    class ThrottledSource:
        key = "limited"

        async def search(self, request, deadline):
            raise ProviderError("upstream_throttled", 429, 17)

    service = ProviderService(
        Settings(_env_file=None),
        SourceRegistry([FailedSource(), ThrottledSource()]),
        MetadataCache(10240, 60, 60),
    )
    with pytest.raises(ProviderError) as error:
        await service.search(SearchRequest(query="Book"))
    assert error.value.status == 429
    assert error.value.retry_after == 17


def test_no_edition_language_is_not_guessed():
    soup = BeautifulSoup((FIXTURES / "book-51855.html").read_text(encoding="utf-8"), "html.parser")
    script = soup.select_one('script[type="application/ld+json"]')
    data = json.loads(script.string)
    data["@graph"][0].pop("inLanguage")
    script.string = json.dumps(data)
    for row in soup.select(".ky-pd-attributes__item"):
        label = row.select_one(".ky-pd-attributes__label")
        if label and fold(label.get_text()).rstrip(":") == "dil":
            row.decompose()
    assert parse_book(str(soup), "51855").languageCode is None


def test_cover_uses_observed_larger_jsonld_image():
    # Live checks: the fixture's JSON-LD link is 800x1358; popup link is 346x587.
    html = (FIXTURES / "book-51855.html").read_text(encoding="utf-8")
    assert parse_book(html, "51855").cover == (
        "https://img.kitapyurdu.com/v1/getImage/fn:8539346/wi:800/wh:a869f31e8"
    )


@pytest.mark.parametrize("structured_image", [None, "https://untrusted.example/cover.jpg"])
def test_missing_or_untrusted_structured_cover_uses_source_popup(structured_image):
    soup = BeautifulSoup((FIXTURES / "book-51855.html").read_text(encoding="utf-8"), "html.parser")
    script = soup.select_one('script[type="application/ld+json"]')
    data = json.loads(script.string)
    data["@graph"][0]["image"] = structured_image
    script.string = json.dumps(data)
    assert parse_book(str(soup), "51855").cover == (
        "https://img.kitapyurdu.com/v1/getImage/fn:8539346/mh:1000/wh:a869f31e8"
    )
