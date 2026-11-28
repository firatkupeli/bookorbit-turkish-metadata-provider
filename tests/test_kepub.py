import json
import shutil
import subprocess
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from app.epub import EpubDocument
from tests.test_epub_editor import HEADERS, contents, make_epub
from tests.test_epub_upgrade import export, sample_epub

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def converted(tmp_path_factory):
    node = shutil.which("node")
    assert node, "Node 24 is required for the offline KEPUB integration test"
    folder = tmp_path_factory.mktemp("kepub")
    source = folder / "input.epub"
    output = folder / "output.kepub.epub"
    source.write_bytes(make_epub(cover=False))
    subprocess.run(
        [node, str(ROOT / "tools/kepub_roundtrip.mjs"), str(source), str(output)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        timeout=30,
    )
    return source.read_bytes(), output.read_bytes()


def test_real_conversion_adds_kobo_spans_and_preserves_text(converted):
    original, kepub = converted
    before, after = contents(original), contents(kepub)
    chapter = "OEBPS/text/chapter.xhtml"
    assert b"koboSpan" not in before[chapter]
    assert b"koboSpan" in after[chapter]

    def body(value):
        return " ".join(
            BeautifulSoup(value.decode(), "html.parser").body.get_text(" ", strip=True).split()
        )

    assert body(before[chapter]) == body(after[chapter])
    assert before["OEBPS/font.otf"] == after["OEBPS/font.otf"]
    with EpubDocument(kepub) as document:
        assert document.has_kepub_markup()
        assert document.original_primary == "urn:uuid:stay-the-same"


@pytest.mark.parametrize(
    "name", ["kitap.kepub", "kitap.kepub.epub", "kitap.KePuB.EpUb", "kitap.epub"]
)
def test_existing_kepub_metadata_edit_preserves_all_chapter_bytes(client, converted, name):
    _, payload = converted
    api, _ = client
    read = api.post("/web/epub/read", files={"file": (name, payload)}, headers=HEADERS)
    assert read.status_code == 200, read.text
    assert read.json()["input_format"] == "kepub"
    assert read.json()["kepub_markup"] is True
    data = read.json()["metadata"]
    data["title"] = "KEPUB — Yeni Türkçe Başlık"
    result = api.post(
        "/web/epub/export",
        files={"file": (name, payload)},
        data={"options": json.dumps({"metadata": data})},
        headers=HEADERS,
    )
    assert result.status_code == 200, result.text
    assert "-metadata.kepub.epub" in result.headers["content-disposition"]
    before, after = contents(payload), contents(result.content)
    with EpubDocument(result.content) as document:
        assert document.metadata_dict()["title"] == data["title"]
        assert all(before[path] == after[path] for path in before if path != document.opf_path)


@pytest.mark.parametrize("name", ["book.epub", "book.kepub", "book.kepub.epub", "book.KEPUB"])
def test_epub_container_accepted_with_supported_extensions(client, name):
    api, _ = client
    result = api.post("/web/epub/read", files={"file": (name, make_epub())}, headers=HEADERS)
    assert result.status_code == 200, result.text


def test_new_vendor_assets_have_correct_mime_and_are_local(client):
    api, _ = client
    wasm = api.get("/assets/vendor/kepubify/kepubify.wasm")
    assert wasm.status_code == 200 and wasm.headers["content-type"] == "application/wasm"
    assert wasm.content.startswith(b"\0asm")
    assert api.get("/assets/vendor/kepubify/worker.js").status_code == 200
    assert api.get("/assets/vendor/kepubify/unknown.js").status_code == 404
    assert "'wasm-unsafe-eval'" in wasm.headers["content-security-policy"]


def test_kepub_bytes_still_have_zip_safety_checks(client):
    api, _ = client
    payload = make_epub(extra={"../escape": b"not allowed"})
    assert (
        api.post(
            "/web/epub/read", files={"file": ("bad.kepub", payload)}, headers=HEADERS
        ).status_code
        == 422
    )


def test_vendor_package_matches_published_hashes():
    import hashlib

    folder = ROOT / "app/static/vendor/kepubify"
    manifest = json.loads((folder / "VENDOR.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "5.0.0"
    for entry in manifest["files"]:
        data = (folder / entry["path"]).read_bytes()
        assert len(data) == entry["bytes"]
        assert hashlib.sha256(data).hexdigest() == entry["sha256"]


def test_epub3_kepub_conversion_keeps_one_cover_and_original_chapter_text(tmp_path):
    from app.epub_structure import cover_pages
    from tests.test_epub_editor import PNG

    source = tmp_path / "epub3.epub"
    target = tmp_path / "converted.kepub.epub"
    source.write_bytes(export(sample_epub(), cover=PNG))
    subprocess.run(
        [shutil.which("node"), str(ROOT / "tools/kepub_roundtrip.mjs"), str(source), str(target)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        timeout=30,
    )
    with EpubDocument(target.read_bytes()) as book:
        assert book.version == "3.0"
        assert len(cover_pages(book)) == 1
        assert book.has_kepub_markup()
    before, after = contents(source.read_bytes()), contents(target.read_bytes())
    chapter = "OPS/chapter.xhtml"

    def body(value):
        return BeautifulSoup(value, "html.parser").body.get_text()

    assert body(before[chapter]) == body(after[chapter])
    assert before["OPS/images/old.png"] == after["OPS/images/old.png"]
    assert before["OPS/style.css"] == after["OPS/style.css"]
