def test_warm_isbn_search_reuses_exact_edition(client):
    api, calls = client
    assert api.get("/book/kitapyurdu:51855").status_code == 200
    before = len(calls)
    response = api.get("/search", params={"isbn": "9786052957929"})
    assert response.status_code == 200
    assert response.json()["matches"][0]["providerId"] == "kitapyurdu:51855"
    assert len(calls) == before


def test_cold_isbn_search_does_not_guess_matches(client):
    response = client[0].get("/search", params={"isbn": "9786052957929"})
    assert response.status_code == 200
    assert response.json() == {"matches": [], "partial": False}


def test_other_isbn_cannot_reuse_cached_edition(client):
    api, calls = client
    api.get("/book/kitapyurdu:51855")
    before = len(calls)
    response = api.get(
        "/search", params={"isbn": "9780306406157", "query": "Otomatik Portakal", "limit": 1}
    )
    assert response.status_code == 200
    assert response.json()["matches"] == []
    assert len(calls) > before
