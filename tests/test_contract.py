import json
import re
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.config import Settings


def test_info_matches_official_contract(client):
    response = client[0].get("/provider/info")
    info = response.json()
    assert response.status_code == 200
    assert re.fullmatch(r"[a-z][a-z0-9-]{1,31}", info["key"])
    assert info["lookup"] is True
    assert info["searchParams"] == ["isbn", "limit"]
    assert info["mediaTypes"] == ["book"]
    assert "pageCount" in info["supportedFields"]
    assert "pages" not in info["supportedFields"]
    assert "translators" not in info["supportedFields"]
    assert info["rateLimit"]["maxConcurrency"] == 1


def test_search_lookup_and_wire_fields(client):
    response = client[0].get("/search", params={"query": "Otomatik Portakal", "limit": 1})
    assert response.status_code == 200
    assert len(response.content) < 2 * 1024 * 1024
    result = response.json()
    book = result["matches"][0]
    assert book["providerId"] == "kitapyurdu:51855"
    assert book["authors"] == ["Anthony Burgess"]
    assert book["translators"] == ["Aziz Üstel"]
    assert book["pages"] == 171
    assert "pageCount" not in book
    assert book["publishedYear"] == "2019"
    assert book["publishedDate"] == "2019-09-10"
    assert book["languageCode"] == "tr"
    assert book["isbn13"] == "9786052957929"
    assert "TÜRKİYE İŞ BANKASI" in book["publisher"]
    assert "<p>" not in book["description"]
    assert book["cover"].startswith("https://img.kitapyurdu.com/")
    assert client[0].get("/book/kitapyurdu%3A51855").json() == book


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"query": "   "},
        {"isbn": "123"},
        {"limit": -1, "query": "a"},
        {"limit": 51, "query": "a"},
        {"query": "x" * 501},
        {"mediaType": "bad", "query": "a"},
    ],
)
def test_bad_search_is_400(client, params):
    assert client[0].get("/search", params=params).status_code == 400


@pytest.mark.parametrize(
    "provider_id",
    [
        "conformance-unknown-id",
        "1000kitap:1",
        "kitapyurdu:bad",
        "kitapyurdu:0",
        "kitapyurdu:999999",
        "kitapyurdu:" + "1" * 40,
    ],
)
def test_missing_lookup_is_404(client, provider_id):
    assert client[0].get("/book/" + provider_id).status_code == 404


@pytest.mark.parametrize(
    "params",
    [
        {"query": "Otomatik Portakal"},
        {"author": "Anthony Burgess"},
        {"query": "Otomatik Portakal", "author": "Anthony Burgess"},
        {"isbn": "978-605-295-792-9", "query": "Otomatik Portakal"},
    ],
)
def test_supported_search_modes(client, params):
    response = client[0].get("/search", params={**params, "limit": 1})
    assert response.status_code == 200
    assert response.json()["matches"][0]["providerId"] == "kitapyurdu:51855"


def test_genuine_empty_is_cached(client):
    assert client[0].get("/search?query=missing").json() == {"matches": [], "partial": False}
    before = len(client[1])
    client[0].get("/search?query=missing")
    assert len(client[1]) == before


def test_book_and_search_cache_avoid_source_calls(client):
    first = client[0].get("/search?query=Otomatik%20Portakal&limit=1").json()
    before = len(client[1])
    assert client[0].get("/search?query=Otomatik%20Portakal&limit=1").json() == first
    client[0].get("/book/kitapyurdu:51855")
    assert len(client[1]) == before


def test_other_media_does_not_scrape(client):
    assert client[0].get("/search?query=a&mediaType=audiobook").json()["matches"] == []
    assert client[1] == []


def test_bearer_token_is_enforced(source_transport):
    app = create_app(
        Settings(_env_file=None, auth_token="secret", source_interval_seconds=0),
        source_transport[0],
    )
    with TestClient(app) as client:
        assert client.get("/provider/info").json()["authenticationRequired"] is True
        for auth in ("", "Bearer wrong", "Basic secret"):
            assert (
                client.get("/search?query=missing", headers={"Authorization": auth}).status_code
                == 401
            )
        assert (
            client.get(
                "/search?query=missing", headers={"Authorization": "Bearer secret"}
            ).status_code
            == 200
        )


def test_api_rate_limit(source_transport):
    app = create_app(
        Settings(_env_file=None, api_requests_per_minute=1, source_interval_seconds=0),
        source_transport[0],
    )
    with TestClient(app) as client:
        assert client.get("/search?query=missing").status_code == 200
        response = client.get("/search?query=missing")
        assert response.status_code == 429
        assert 1 <= int(response.headers["Retry-After"]) <= 60
        assert client.get("/healthz").status_code == 200


def test_failures_are_not_empty_or_cached():
    attempts = {}

    def handle(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        attempts[request.url.host] = attempts.get(request.url.host, 0) + 1
        return httpx.Response(
            200, text="<h1>Just a moment...</h1>", headers={"Content-Type": "text/html"}
        )

    with TestClient(
        create_app(Settings(_env_file=None, source_interval_seconds=0), httpx.MockTransport(handle))
    ) as client:
        for _ in range(2):
            response = client.get("/search?query=private-title")
            assert response.status_code == 502
            assert response.json() == {"error": "source_search_markup_changed"}
    assert attempts == {"www.kitapyurdu.com": 2, "1000kitap.com": 2}


def test_turkish_query_is_utf8_and_never_sent_as_credentials(client):
    client[0].get("/search", params={"query": "Çığ Öyküsü İŞIK", "limit": 1})
    request = next(r for r in client[1] if r.url.params.get("route") == "product/list")
    assert request.url.params["filter_name"] == "Çığ Öyküsü İŞIK"
    assert "authorization" not in request.headers
    assert request.headers["accept-language"].startswith("tr")


def test_openapi_documents_exact_routes(client):
    paths = client[0].get("/openapi.json").json()["paths"]
    assert {"/provider/info", "/search", "/book/{provider_id}"} <= paths.keys()


def test_compose_and_docker_security_configuration():
    import yaml

    root = Path(__file__).resolve().parents[1]
    compose_path = root / "compose.yaml"
    if not compose_path.exists():
        compose_path = root / "docker-compose.yml"
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    service = compose["services"]["turkish-metadata"]
    # The general Compose file uses the host's native image architecture.
    assert service.get("platform") in (None, "linux/amd64")
    assert service["read_only"] is True
    assert "ports" not in service
    assert service["mem_limit"] == "256m"
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    assert "USER 10001:10001" in dockerfile
    assert "--no-access-log" in dockerfile
    json.loads(
        next(
            line.removeprefix("CMD ") for line in dockerfile.splitlines() if line.startswith("CMD ")
        )
    )
