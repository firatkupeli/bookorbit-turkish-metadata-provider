import httpx
import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from app.api import create_app
from app.config import Settings
from app.text import author_matches, match_title
from tests.conftest import FIXTURES


def identity_transport(*, broad_only=False, late_match=False, wrong_author=False, wrong_isbn=False):
    calls = []
    narrow = (FIXTURES / "search-sehit-author-title.html").read_text(encoding="utf-8")
    broad = (FIXTURES / "search-sehit-title.html").read_text(encoding="utf-8")
    if late_match:
        soup = BeautifulSoup(broad, "html.parser")
        soup.div.append(BeautifulSoup(narrow, "html.parser").select_one(".ky-product"))
        broad = str(soup)
    book = (FIXTURES / "book-711075.html").read_text(encoding="utf-8")
    if wrong_author:
        book = book.replace("Kaveh Akbar", "Muharrem Kaşıtoğlu")
    if wrong_isbn:
        book = book.replace("9786255539007", "9786052957929")

    def handle(request):
        calls.append(request)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        if request.url.host == "1000kitap.com" and request.url.path == "/ara":
            return httpx.Response(
                200,
                text='<main class="govde-arama">Gösterilecek içerik bulunamadı.</main>',
                headers={"Content-Type": "text/html"},
            )
        params = request.url.params
        if params.get("route") == "product/list":
            term = params.get("filter_name")
            if term == "Şehit!":
                body = broad
            elif term == "Şehit! Kaveh Akbar" and not broad_only:
                body = narrow
            else:
                body = (FIXTURES / "search-empty.html").read_text(encoding="utf-8")
            return httpx.Response(200, text=body, headers={"Content-Type": "text/html"})
        if params.get("product_id") == "711075":
            return httpx.Response(200, text=book, headers={"Content-Type": "text/html"})
        if wrong_isbn:
            return httpx.Response(404)
        raise AssertionError("A known unrelated author must not cost a detail request")

    return httpx.MockTransport(handle), calls


@pytest.mark.parametrize("with_isbn", [False, True])
def test_sehit_is_found_without_prewarming_or_manual_lookup(with_isbn):
    transport, calls = identity_transport()
    params = {"query": "Şehit!", "author": "Kaveh Akbar", "limit": 1}
    if with_isbn:
        params["isbn"] = "9786255539007"
    with TestClient(
        create_app(Settings(_env_file=None, source_interval_seconds=0), transport)
    ) as api:
        response = api.get("/search", params=params)
    assert response.status_code == 200
    matches = response.json()["matches"]
    assert len(matches) == 1
    assert matches[0]["providerId"] == "kitapyurdu:711075"
    assert matches[0]["authors"] == ["Kaveh Akbar"]
    assert matches[0]["isbn13"] == "9786255539007"
    assert matches[0]["pages"] == 424
    assert matches[0]["translators"] == ["Berkan M. Şimşek"]
    terms = [r.url.params["filter_name"] for r in calls if "filter_name" in r.url.params]
    assert "Şehit! Kaveh Akbar" in terms
    assert "Şehit!" not in terms
    assert response.json()["partial"] is False


def test_wrong_author_broad_results_are_discarded_before_fetch():
    transport, calls = identity_transport(broad_only=True)
    with TestClient(
        create_app(Settings(_env_file=None, source_interval_seconds=0), transport)
    ) as api:
        response = api.get("/search", params={"query": "Şehit!", "author": "Kaveh Akbar"})
    assert response.json()["matches"] == []
    assert not any("product_id" in r.url.params for r in calls)


def test_author_filter_precedes_limit_even_when_correct_book_is_late():
    transport, calls = identity_transport(broad_only=True, late_match=True)
    with TestClient(
        create_app(Settings(_env_file=None, source_interval_seconds=0), transport)
    ) as api:
        response = api.get(
            "/search", params={"query": "Şehit!", "author": "Kaveh Akbar", "limit": 1}
        )
    assert response.json()["matches"][0]["providerId"] == "kitapyurdu:711075"
    assert [r.url.params["product_id"] for r in calls if "product_id" in r.url.params] == ["711075"]


def test_detail_author_is_rechecked_even_if_preview_claims_match():
    transport, _ = identity_transport(wrong_author=True)
    with TestClient(
        create_app(Settings(_env_file=None, source_interval_seconds=0), transport)
    ) as api:
        response = api.get("/search", params={"query": "Şehit!", "author": "Kaveh Akbar"})
    assert response.json()["matches"] == []


def test_isbn_mismatch_never_becomes_title_fallback_result():
    transport, _ = identity_transport(wrong_isbn=True)
    with TestClient(
        create_app(Settings(_env_file=None, source_interval_seconds=0), transport)
    ) as api:
        response = api.get(
            "/search", params={"query": "Şehit!", "author": "Kaveh Akbar", "isbn": "9786255539007"}
        )
    assert response.json()["matches"] == []


@pytest.mark.parametrize(
    "query,authors,want",
    [
        ("Kaveh Akbar", ["Muharrem Kaşıtoğlu"], False),
        ("Orhan Pamuk", ["Orhan Veli Kanık"], False),
        ("Akbar, Kaveh", ["Kaveh Akbar"], True),
        ("PlatonEflatun Platon(Eflatun)", ["Platon (Eflatun)"], True),
        ("Ömer Seyfettin", ["Omer Seyfettin"], True),
    ],
)
def test_author_identity_normalization(query, authors, want):
    assert author_matches(query, authors) is want


def test_turkish_title_punctuation_does_not_change_identity():
    assert match_title("Sokrates'in Savunması") == match_title("Sokratesin Savunmasi")
