import base64
import io
import json
import zipfile
from xml.etree.ElementTree import ParseError

import httpx
import pytest
from defusedxml.common import DefusedXmlException
from fastapi.testclient import TestClient

from app.api import create_app
from app.config import Settings
from app.epub import DC, OPF, EpubDocument, EpubError, EpubMetadata
from app.models import Book

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII="
)
HEADERS = {"X-BookOrbit-Web": "1"}


def make_epub(version="3.0", *, cover=True, drm=False, extra=None):
    out = io.BytesIO()
    role = (
        '<meta refines="#trl" property="role" scheme="marc:relators">trl</meta>'
        if version.startswith("3")
        else ""
    )
    attribute = 'opf:role="trl"' if version.startswith("2") else ""
    opf = f'''<?xml version="1.0" encoding="UTF-8"?>
    <package xmlns="{OPF}" xmlns:dc="{DC}" xmlns:opf="{OPF}"
      xmlns:unused="urn:preserve-me" version="{version}" unique-identifier="uid">
      <metadata><dc:title id="title">Eski Başlık</dc:title><dc:creator>Eski Yazar</dc:creator>
      <dc:identifier id="uid">urn:uuid:stay-the-same</dc:identifier>
      <dc:identifier id="isbn">9786255539007</dc:identifier>
      <dc:language>tr</dc:language><dc:publisher>Eski Yayınevi</dc:publisher>
      <dc:date>2020-01-01</dc:date>
      <dc:contributor id="trl" {attribute}>Eski Çevirmen</dc:contributor>{role}
      <dc:contributor opf:role="edt">Editör Korunur</dc:contributor>
      <meta name="custom" content="koru"/>
      {'<meta name="cover" content="cover"/>' if cover else ""}</metadata>
      <manifest><item id="chapter" href="text/chapter.xhtml" media-type="application/xhtml+xml"/>
      {
        (
            '<item id="cover" href="images/cover.png" media-type="image/png" '
            'properties="cover-image"/>'
        )
        if cover
        else ""
    }
      <item id="font" href="font.otf" media-type="font/otf"/></manifest>
      <spine><itemref idref="chapter"/></spine></package>'''
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr(
            "META-INF/container.xml",
            '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">'
            '<rootfiles><rootfile full-path="OEBPS/content.opf" '
            'media-type="application/oebps-package+xml"/></rootfiles></container>',
        )
        z.writestr("OEBPS/content.opf", opf)
        z.writestr(
            "OEBPS/text/chapter.xhtml",
            '<html xmlns="http://www.w3.org/1999/xhtml"><body>İçerik: ş ğ ı İ ö ü ç</body></html>',
        )
        z.writestr("OEBPS/font.otf", b"UNCHANGED-OBFUSCATED-FONT")
        if cover:
            z.writestr("OEBPS/images/cover.png", PNG)
        if drm:
            z.writestr(
                "META-INF/encryption.xml",
                '<encryption xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">'
                '<EncryptionMethod xmlns="http://www.w3.org/2001/04/xmlenc#" '
                'Algorithm="http://www.idpf.org/2008/embedding"/></encryption>',
            )
    if extra:
        entries = contents(out.getvalue())
        entries.update(extra)
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for name, data in entries.items():
                z.writestr(name, data)
    return out.getvalue()


def contents(payload):
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        assert z.testzip() is None
        return {name: z.read(name) for name in z.namelist()}


@pytest.mark.parametrize("version", ["2.0", "3.0", "3.3"])
def test_roundtrip_preserves_book_and_roles(version):
    original = make_epub(version, drm=True)
    before = contents(original)
    with EpubDocument(original) as book:
        data = book.metadata_dict()
        assert data["translators"] == ["Eski Çevirmen"]
        data.update(
            title="Şehit! & Öyküler <2026>",
            authors=["Kaveh Akbar", "İlhan Şahin"],
            translators=["Berkan M. Şimşek"],
            description="Birinci paragraf.\n\nİkinci paragraf.",
            publisher="Holden Kitap",
            published_date="2025-02-27",
        )
        result = book.write(EpubMetadata(**data))
    after = contents(result)
    assert set(before) == set(after)
    assert all(before[name] == after[name] for name in before if name != "OEBPS/content.opf")
    assert b'xmlns:unused="urn:preserve-me"' in after["OEBPS/content.opf"]
    assert "Editör Korunur" in after["OEBPS/content.opf"].decode()
    with EpubDocument(result) as book:
        assert book.metadata_dict() == data
        assert book.original_primary == "urn:uuid:stay-the-same"
    with zipfile.ZipFile(io.BytesIO(result)) as z:
        assert z.infolist()[0].filename == "mimetype"
        assert z.infolist()[0].compress_type == zipfile.ZIP_STORED


@pytest.mark.parametrize("has_cover", [False, True])
@pytest.mark.parametrize("version", ["2.0", "3.0"])
def test_cover_is_embedded_without_changing_chapters(has_cover, version):
    original = make_epub(version, cover=has_cover)
    with EpubDocument(original) as book:
        result = book.write(EpubMetadata(**book.metadata_dict()), PNG)
    assert (
        contents(original)["OEBPS/text/chapter.xhtml"]
        == contents(result)["OEBPS/text/chapter.xhtml"]
    )
    with EpubDocument(result) as book:
        assert book.current_cover() is not None
        assert book.preview().startswith("data:image/png;base64,")


@pytest.mark.parametrize(
    "extra",
    [
        {"../outside": b"no"},
        {"C:/outside": b"no"},
        {"META-INF/signatures.xml": b"signed"},
        {"META-INF/container.xml": '<!DOCTYPE x [<!ENTITY y "attack">]><container>&y;</container>'},
        {"META-INF/container.xml": "<container"},
        {
            "META-INF/encryption.xml": '<x xmlns="http://www.w3.org/2001/04/xmlenc#">'
            '<EncryptionMethod Algorithm="DRM"/></x>'
        },
    ],
)
def test_unsafe_archive_rejected(extra):
    with pytest.raises((EpubError, DefusedXmlException, ParseError)):
        with EpubDocument(make_epub(extra=extra)):
            pass


@pytest.mark.parametrize("value", ["0000000000", "9786255539008", "１２３４５６７８９０"])
def test_invalid_isbn_not_written(value):
    with pytest.raises(ValueError):
        EpubMetadata(title="Kitap", isbn=value)


def test_unique_identifier_is_never_rewritten():
    original = make_epub()
    parts = contents(original)
    parts["OEBPS/content.opf"] = parts["OEBPS/content.opf"].replace(
        b"urn:uuid:stay-the-same", b"urn:isbn:9786255539007"
    )
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for name, data in parts.items():
            z.writestr(name, data)
    with EpubDocument(out.getvalue()) as book:
        data = book.metadata_dict()
        data["isbn"] = "9786052957929"
        with pytest.raises(EpubError, match="ana kimli"):
            book.write(EpubMetadata(**data))


def test_web_upload_export_and_same_origin(client):
    api, _ = client
    original = make_epub()
    read = api.post("/web/epub/read", files={"file": ("kitap.epub", original)}, headers=HEADERS)
    assert read.status_code == 200, read.text
    data = read.json()["metadata"]
    data["title"] = "Yeni Türkçe Başlık"
    exported = api.post(
        "/web/epub/export",
        files={"file": ("kitap.epub", original)},
        data={"options": json.dumps({"metadata": data})},
        headers=HEADERS,
    )
    assert exported.status_code == 200, exported.text
    assert exported.headers["content-type"] == "application/epub+zip"
    assert exported.headers["cache-control"] == "no-store"
    with EpubDocument(exported.content) as book:
        assert book.metadata_dict()["title"] == data["title"]
    assert api.post("/web/epub/read", files={"file": ("kitap.epub", original)}).status_code == 403
    assert (
        api.post(
            "/web/epub/read",
            files={"file": ("kitap.epub", original)},
            headers={**HEADERS, "Origin": "https://evil.example"},
        ).status_code
        == 403
    )


def test_unauthorized_web_is_rejected_before_reading_upload():
    with TestClient(create_app(Settings(_env_file=None, auth_token="secret"))) as api:
        assert api.post("/web/epub/read", headers=HEADERS, content=b"junk").status_code == 401
        assert api.get("/").status_code == 200
        assert api.get("/assets/app.js").status_code == 200
        assert api.get("/assets/config.py").status_code == 404


@pytest.mark.parametrize("payload", [b"notzip", b"PK\x03\x04broken"])
def test_bad_upload_is_user_error(client, payload):
    api, _ = client
    assert (
        api.post(
            "/web/epub/read", files={"file": ("book.epub", payload)}, headers=HEADERS
        ).status_code
        == 422
    )


def test_cover_only_fetches_source_selected_host():
    urls = []

    def handler(request):
        urls.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        return httpx.Response(200, content=PNG, headers={"content-type": "image/png"})

    with TestClient(
        create_app(
            Settings(_env_file=None, source_interval_seconds=0), httpx.MockTransport(handler)
        )
    ) as api:
        service = api.app.state.service
        book = Book(
            providerId="kitapyurdu:711075",
            title="Şehit!",
            url="https://www.kitapyurdu.com/kitap/sehit/711075.html",
            cover="https://img.kitapyurdu.com/example.png",
        )
        service.cache.put(service.cache.books, book.providerId, book)
        assert api.get("/web/cover/kitapyurdu:711075", headers=HEADERS).content == PNG
        book.cover = "https://example.com/private.png"
        service.cache.put(service.cache.books, book.providerId, book)
        assert api.get("/web/cover/kitapyurdu:711075", headers=HEADERS).status_code == 502
        assert not any("example.com" in url for url in urls)


def repack(entries):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def test_namespace_bindings_subtitle_and_author_refinements_are_preserved():
    entries = contents(make_epub())
    opf = entries["OEBPS/content.opf"].decode()
    opf = opf.replace(
        "<metadata>",
        '<metadata xmlns="urn:other-default"><opf:meta name="custom-default" content="keep"/>',
    )
    # Prefix the actual OPF metadata container while leaving a different default namespace.
    opf = opf.replace("<metadata ", "<opf:metadata ").replace("</metadata>", "</opf:metadata>")
    # The original unprefixed role metas need OPF prefixes under this different default.
    opf = opf.replace("<meta ", "<opf:meta ").replace("</meta>", "</opf:meta>")
    opf = opf.replace(
        '<dc:title id="title">',
        '<dc:title id="subtitle">Alt Başlık</dc:title>'
        '<opf:meta refines="#subtitle" property="title-type">subtitle</opf:meta>'
        '<opf:meta refines="#title" property="title-type">main</opf:meta>'
        '<dc:title id="title">',
    )
    entries["OEBPS/content.opf"] = opf.encode()
    with EpubDocument(repack(entries)) as book:
        data = book.metadata_dict()
        assert data["title"] == "Eski Başlık"
        data.update(title="Yeni Başlık", authors=["Yeni Yazar"], translators=["Yeni Çevirmen"])
        result = book.write(EpubMetadata(**data))
    with EpubDocument(result) as book:
        assert book.metadata_dict() == data
        assert "Alt Başlık" in book.document.toxml()
        assert 'xmlns="urn:other-default"' in book.document.toxml()


def test_retained_author_keeps_sort_name():
    entries = contents(make_epub())
    entries["OEBPS/content.opf"] = entries["OEBPS/content.opf"].replace(
        b"<dc:creator>Eski Yazar</dc:creator>",
        b'<dc:creator id="aut1">Eski Yazar</dc:creator>'
        b'<meta refines="#aut1" property="file-as">Yazar, Eski</meta>',
    )
    with EpubDocument(repack(entries)) as book:
        data = book.metadata_dict()
        data["authors"].append("İkinci Yazar")
        result = book.write(EpubMetadata(**data))
    with EpubDocument(result) as book:
        assert "Yazar, Eski" in book.document.toxml()
        assert book.metadata_dict()["authors"] == data["authors"]


def test_cover_cannot_overwrite_chapter_bytes():
    entries = contents(make_epub())
    entries["OEBPS/content.opf"] = entries["OEBPS/content.opf"].replace(
        b'href="images/cover.png"', b'href="text/chapter.xhtml"'
    )
    with EpubDocument(repack(entries)) as book:
        with pytest.raises(EpubError, match="JPEG"):
            book.write(EpubMetadata(**book.metadata_dict()), PNG)


def test_unknown_encryption_cannot_hide_without_algorithm():
    with pytest.raises(EpubError, match="DRM"):
        EpubDocument(make_epub(extra={"META-INF/encryption.xml": "<encryption/>"}))


def test_expanded_size_and_file_count_limits(monkeypatch):
    monkeypatch.setattr("app.epub.MAX_EXPANDED", 100)
    with pytest.raises(EpubError, match="128 MiB"):
        EpubDocument(make_epub())


def test_oversized_upload_is_rejected(client, monkeypatch):
    api, _ = client
    monkeypatch.setattr("app.web.MAX_UPLOAD", 100)
    assert (
        api.post(
            "/web/epub/read", files={"file": ("book.epub", b"x" * 101)}, headers=HEADERS
        ).status_code
        == 413
    )


@pytest.mark.parametrize("origin", ["https://[broken", "null", "https://evil.example"])
def test_invalid_origins_are_rejected(client, origin):
    api, _ = client
    assert (
        api.post(
            "/web/epub/read", content=b"not-read", headers={**HEADERS, "Origin": origin}
        ).status_code
        == 403
    )


@pytest.mark.parametrize("date", ["2026-02-30", "2026-13", "2026/01/01"])
def test_invalid_dates_rejected(date):
    with pytest.raises(ValueError):
        EpubMetadata(title="Kitap", published_date=date)


def test_invalid_xml_and_control_characters_are_user_errors(client):
    api, _ = client
    broken = make_epub(extra={"OEBPS/content.opf": "<package"})
    assert (
        api.post(
            "/web/epub/read", files={"file": ("book.epub", broken)}, headers=HEADERS
        ).status_code
        == 422
    )
    data = EpubMetadata(title="Kitap").model_dump()
    data["title"] = "bad\x00title"
    assert (
        api.post(
            "/web/epub/export",
            files={"file": ("book.epub", make_epub())},
            data={"options": json.dumps({"metadata": data})},
            headers=HEADERS,
        ).status_code
        == 422
    )


@pytest.mark.parametrize("policy", ["User-agent: *\nDisallow: /", "<html>Challenge</html>"])
def test_image_robots_is_fail_closed(policy):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(200, text=policy)

    with TestClient(
        create_app(
            Settings(_env_file=None, source_interval_seconds=0), httpx.MockTransport(handler)
        )
    ) as api:
        book = Book(
            providerId="kitapyurdu:711075",
            title="Kitap",
            url="https://www.kitapyurdu.com/kitap/x/711075.html",
            cover="https://img.kitapyurdu.com/cover.png",
        )
        api.app.state.service.cache.put(api.app.state.service.cache.books, book.providerId, book)
        assert api.get("/web/cover/" + book.providerId, headers=HEADERS).status_code == 503
        assert calls == ["/robots.txt"]
