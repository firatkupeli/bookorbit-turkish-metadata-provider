import json

import pytest

from app.epub import EpubDocument
from app.epub_check import inspect_book
from tests.test_epub_editor import HEADERS, PNG, contents, repack
from tests.test_epub_upgrade import export, sample_epub


def report(payload):
    with EpubDocument(payload) as book:
        return inspect_book(book)


def test_inspection_finds_existing_duplicate_cover_without_changing_book():
    original = sample_epub()
    with EpubDocument(original) as book:
        before = book.document.toxml()
        result = inspect_book(book)
        assert book.document.toxml() == before
    assert result["errors"] == 0
    assert result["complete"]
    assert any(issue["code"] == "duplicate_cover" for issue in result["issues"])


def test_repaired_epub3_has_no_missing_resources_or_duplicate_covers():
    result = report(export(sample_epub(), cover=PNG))
    assert result["errors"] == 0
    assert result["warnings"] == 0
    assert result["stats"]["reading_order"] == 2


@pytest.mark.parametrize(
    ("replacement", "code"),
    [(b"gone.png", "missing_image"), (b"chapter.xhtml#gone", "broken_anchor")],
)
def test_missing_images_and_anchor_targets_are_reported(replacement, code):
    files = contents(sample_epub())
    files["OPS/chapter.xhtml"] = files["OPS/chapter.xhtml"].replace(
        b"images/old.png" if code == "missing_image" else b"#dipnot", replacement
    )
    result = report(repack(files))
    assert any(issue["code"] == code for issue in result["issues"])


def test_css_background_image_is_checked():
    files = contents(sample_epub())
    files["OPS/style.css"] += b'body { background-image: url("images/gone.png"); }'
    result = report(repack(files))
    assert any(issue["code"] == "missing_image" for issue in result["issues"])


def test_external_images_are_reported_without_network_access():
    files = contents(sample_epub())
    files["OPS/chapter.xhtml"] = files["OPS/chapter.xhtml"].replace(
        b"images/old.png", b"https://example.invalid/image.png"
    )
    assert any(issue["code"] == "external_resource" for issue in report(repack(files))["issues"])


def test_legacy_named_anchor_is_accepted():
    files = contents(sample_epub())
    files["OPS/chapter.xhtml"] = files["OPS/chapter.xhtml"].replace(
        b'<p id="dipnot">', b'<p><a name="dipnot"></a>'
    )
    result = report(repack(files))
    assert not any(issue["code"] == "broken_anchor" for issue in result["issues"])


def test_entity_in_chapter_is_a_check_issue():
    files = contents(sample_epub())
    files["OPS/chapter.xhtml"] = (
        b'<!DOCTYPE html [<!ENTITY private SYSTEM "file:///not-read">]>'
        + files["OPS/chapter.xhtml"]
    )
    assert any(issue["code"] == "invalid_xml" for issue in report(repack(files))["issues"])


def test_check_api_returns_actual_file_metadata_cover_and_report(client):
    api, _ = client
    result = api.post(
        "/web/epub/check", files={"file": ("book.epub", sample_epub())}, headers=HEADERS
    )
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["metadata"]["title"] == "Künye Deneme"
    assert data["cover"].startswith("data:image/png;base64,")
    assert data["report"]["stats"]["images"] == 2
    assert data["input_format"] == "epub"


def test_check_api_requires_same_origin_guard(client):
    api, _ = client
    assert (
        api.post("/web/epub/check", files={"file": ("book.epub", sample_epub())}).status_code == 403
    )


def test_cover_preview_cannot_silently_change_between_preview_and_export(client, monkeypatch):
    from app.models import Book

    api, _ = client

    async def get_cover(_url):
        return PNG

    monkeypatch.setattr(api.app.state.cover_http, "get", get_cover)
    service = api.app.state.service
    book = Book(
        providerId="kitapyurdu:711075",
        title="Kitap",
        url="https://www.kitapyurdu.com/kitap/x/711075.html",
        cover="https://img.kitapyurdu.com/cover.png",
    )
    service.cache.put(service.cache.books, book.providerId, book)
    preview = api.get("/web/cover/" + book.providerId, headers=HEADERS)
    assert preview.status_code == 200
    assert len(preview.headers["x-cover-sha256"]) == 64
    original = sample_epub()
    with EpubDocument(original) as document:
        metadata = document.metadata_dict()
    result = api.post(
        "/web/epub/export",
        files={"file": ("book.epub", original)},
        data={
            "options": json.dumps(
                {
                    "metadata": metadata,
                    "cover_provider_id": book.providerId,
                    "expected_cover_sha256": "0" * 64,
                }
            )
        },
        headers=HEADERS,
    )
    assert result.status_code == 422
    assert "değişmiş" in result.json()["message"].lower()
