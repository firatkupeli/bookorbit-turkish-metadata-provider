# ruff: noqa: E501 -- Inline XML fixtures keep the sample publication self-contained.
import io
import json
import zipfile

import pytest

from app.epub import DC, OPF, EpubDocument, EpubError, EpubMetadata, children
from app.epub_structure import EPUB, XHTML, cover_pages, nodes, xml_document
from tests.test_epub_editor import HEADERS, PNG, contents, repack


def sample_epub(*, duplicate_cover=True, uid=True):
    """An original, small book with a nested NCX and an unregistered cover."""
    output = io.BytesIO()
    extra_cover = (
        '<item id="cover2" href="cover.xhtml" media-type="application/xhtml+xml"/>'
        if duplicate_cover
        else ""
    )
    extra_spine = '<itemref idref="cover2"/>' if duplicate_cover else ""
    identifier = (
        '<dc:identifier id="uid">urn:uuid:66fc04dd-9913-4c6c-b19b-4da17a655cab</dc:identifier>'
        if uid
        else ""
    )
    files = {
        "mimetype": b"application/epub+zip",
        "META-INF/container.xml": b'<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OPS/book.opf" media-type="application/oebps-package+xml"/></rootfiles></container>',
        "OPS/book.opf": f'''<package xmlns="{OPF}" xmlns:dc="{DC}" xmlns:opf="{OPF}" version="2.0" unique-identifier="uid"><metadata>{identifier}<dc:title>Künye Deneme</dc:title><dc:language>tr</dc:language><dc:creator opf:role="aut" opf:file-as="Yazar, Deneme">Deneme Yazar</dc:creator></metadata><manifest><item id="cover1" href="titlepage.xhtml" media-type="application/xhtml+xml"/>{extra_cover}<item id="image" href="images/cover.png" media-type="image/png"/><item id="image2" href="images/old.png" media-type="image/png"/><item id="chapter" href="chapter.xhtml" media-type="application/xhtml+xml"/><item id="css" href="style.css" media-type="text/css"/><item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/></manifest><spine toc="ncx"><itemref idref="cover1"/>{extra_spine}<itemref idref="chapter"/></spine><guide><reference type="cover" title="Kapak" href="titlepage.xhtml"/></guide></package>'''.encode(),
        "OPS/titlepage.xhtml": f'<html xmlns="{XHTML}"><head><title>Kapak</title></head><body><div><img src="images/cover.png" alt="Kapak"/></div></body></html>'.encode(),
        "OPS/chapter.xhtml": f'<html xmlns="{XHTML}"><head><title>Birinci bölüm</title><link rel="stylesheet" type="text/css" href="style.css"/></head><body><h1 id="bolum">Birinci bölüm</h1><p>İçerik korunur: ş, ğ, ı, İ, ö, ü, ç. <a href="#dipnot">Dipnot</a></p><p id="dipnot">Dipnot metni.</p><h2 id="alt">Alt bölüm</h2><img src="images/old.png" alt="Bölüm içi görsel"/></body></html>'.encode(),
        "OPS/style.css": b"body { margin: 1em; } h1 { font-size: 1.5em; }",
        "OPS/images/cover.png": PNG,
        "OPS/images/old.png": PNG,
        "OPS/toc.ncx": """<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1"><head><meta name="dtb:uid" content="urn:uuid:66fc04dd-9913-4c6c-b19b-4da17a655cab"/><meta name="dtb:depth" content="2"/><meta name="dtb:totalPageCount" content="0"/><meta name="dtb:maxPageNumber" content="0"/></head><docTitle><text>Künye Deneme</text></docTitle><navMap><navPoint id="p1" playOrder="1"><navLabel><text>Birinci bölüm</text></navLabel><content src="chapter.xhtml#bolum"/><navPoint id="p2" playOrder="2"><navLabel><text>Alt bölüm</text></navLabel><content src="chapter.xhtml#alt"/></navPoint></navPoint></navMap></ncx>""".encode(),
    }
    if duplicate_cover:
        files["OPS/cover.xhtml"] = (
            f'<html xmlns="{XHTML}"><head><title>Kapak</title></head><body><p><img src="images/old.png" alt="Kapak"/></p></body></html>'.encode()
        )
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(
                name,
                data,
                compress_type=zipfile.ZIP_STORED if name == "mimetype" else zipfile.ZIP_DEFLATED,
            )
    return output.getvalue()


def export(payload, *, upgrade=True, cover=None):
    with EpubDocument(payload) as book:
        return book.write(EpubMetadata(**book.metadata_dict()), cover, upgrade_epub3=upgrade)


def test_upgrade_is_opt_in_and_default_keeps_all_resources():
    original = sample_epub()
    after = contents(export(original, upgrade=False))
    before = contents(original)
    assert all(after[path] == data for path, data in before.items() if not path.endswith(".opf"))
    with EpubDocument(export(original, upgrade=False)) as book:
        assert book.version == "2.0"
        assert len(cover_pages(book)) == 2


def test_epub3_nested_toc_images_css_chapters_and_identity_are_preserved():
    original = sample_epub()
    result = export(original)
    before, after = contents(original), contents(result)
    for path, value in before.items():
        if path != "OPS/book.opf":
            assert after[path] == value
    with EpubDocument(result) as book:
        assert book.version == "3.0"
        assert book.original_primary == "urn:uuid:66fc04dd-9913-4c6c-b19b-4da17a655cab"
        assert book.metadata_dict()["authors"] == ["Deneme Yazar"]
        assert "Yazar, Deneme" in book.document.toxml()
        assert children(book.package, OPF, "spine")[0].getAttribute("toc") == "ncx"
        nav = xml_document(book, after["OPS/kunye-nav.xhtml"])
        try:
            assert [n.getAttribute("href") for n in nodes(nav, XHTML, "a")] == [
                "chapter.xhtml#bolum",
                "chapter.xhtml#alt",
            ]
            assert len(nodes(nav, XHTML, "ol")) == 2
            assert nodes(nav, XHTML, "nav")[0].getAttributeNS(EPUB, "type") == "toc"
        finally:
            nav.unlink()


def test_cover_is_discovered_and_duplicates_are_not_removed_without_cover_change():
    with EpubDocument(sample_epub()) as book:
        assert book.current_cover().getAttribute("id") == "image"
        assert book.preview().startswith("data:image/png")
    with EpubDocument(export(sample_epub())) as book:
        assert len(cover_pages(book)) == 2


def test_replaced_cover_uses_one_opening_page_and_keeps_chapter_illustration():
    original = sample_epub()
    result = export(original, cover=PNG + b"replacement")
    before, after = contents(original), contents(result)
    assert after["OPS/images/cover.png"] == PNG + b"replacement"
    assert after["OPS/images/old.png"] == before["OPS/images/old.png"]
    assert after["OPS/chapter.xhtml"] == before["OPS/chapter.xhtml"]
    assert after["OPS/style.css"] == before["OPS/style.css"]
    with EpubDocument(result) as book:
        assert len(cover_pages(book)) == 1
        assert [
            n.getAttribute("idref")
            for n in children(children(book.package, OPF, "spine")[0], OPF, "itemref")
        ] == ["cover1", "chapter"]
    # The redundant file is retained, with its image synchronized rather than deleted.
    assert b"images/cover.png" in after["OPS/cover.xhtml"]


def test_opening_page_with_text_is_never_removed_as_duplicate_cover():
    entries = contents(sample_epub())
    entries["OPS/cover.xhtml"] = entries["OPS/cover.xhtml"].replace(
        b"</body>", b"<p>Publisher information.</p></body>"
    )
    with EpubDocument(export(repack(entries), cover=PNG)) as book:
        assert len(children(children(book.package, OPF, "spine")[0], OPF, "itemref")) == 3


def test_unregistered_bitmap_cover_is_reused_instead_of_creating_another_image():
    entries = contents(sample_epub())
    entries["OPS/book.opf"] = entries["OPS/book.opf"].replace(
        b'<item id="image" href="images/cover.png" media-type="image/png"/>', b""
    )
    after = contents(export(repack(entries), cover=PNG))
    assert set(after) - set(entries) == {"OPS/kunye-nav.xhtml"}
    with EpubDocument(repack(after)) as book:
        assert book.current_cover().getAttribute("href") == "images/cover.png"
        assert len(cover_pages(book)) == 1


@pytest.mark.parametrize("target", [b"missing.xhtml", b"chapter.xhtml#missing-anchor"])
def test_upgrade_refuses_broken_navigation(target):
    entries = contents(sample_epub())
    entries["OPS/toc.ncx"] = entries["OPS/toc.ncx"].replace(b"chapter.xhtml#bolum", target)
    with pytest.raises(EpubError, match="bağlantı|hedef"):
        export(repack(entries))


def test_missing_identity_is_created_deterministically_only_on_upgrade():
    original = sample_epub(uid=False)
    with EpubDocument(export(original, upgrade=False)) as book:
        assert book.original_primary is None
    identifiers = []
    for _ in range(2):
        with EpubDocument(export(original)) as book:
            identifiers.append(book.original_primary)
    assert identifiers[0] == identifiers[1]
    assert identifiers[0].startswith("urn:uuid:")


def test_no_ncx_generates_navigation_from_reading_order():
    entries = contents(sample_epub())
    entries["OPS/book.opf"] = (
        entries["OPS/book.opf"]
        .replace(b' toc="ncx"', b"")
        .replace(b'<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>', b"")
    )
    result = export(repack(entries))
    with EpubDocument(result) as book:
        nav = xml_document(book, contents(result)["OPS/kunye-nav.xhtml"])
        try:
            assert len(nodes(nav, XHTML, "a")) == 3
        finally:
            nav.unlink()


def test_external_doctype_is_not_loaded_and_body_text_survives():
    entries = contents(sample_epub())
    entries["OPS/chapter.xhtml"] = (
        b'<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">'
        + entries["OPS/chapter.xhtml"]
    )
    result = contents(export(repack(entries)))["OPS/chapter.xhtml"]
    assert b"DOCTYPE" not in result
    assert "İçerik korunur" in result.decode()


def test_internal_entities_are_rejected():
    entries = contents(sample_epub())
    entries["OPS/chapter.xhtml"] = (
        b'<!DOCTYPE html [<!ENTITY leak SYSTEM "file:///private">]>' + entries["OPS/chapter.xhtml"]
    )
    with pytest.raises(EpubError, match="entity"):
        export(repack(entries))


def test_api_exposes_upgrade_and_keeps_existing_provider_identity(client):
    api, _ = client
    original = sample_epub()
    with EpubDocument(original) as book:
        data = book.metadata_dict()
    response = api.post(
        "/web/epub/export",
        files={"file": ("book.epub", original)},
        data={"options": json.dumps({"metadata": data, "upgrade_epub3": True})},
        headers=HEADERS,
    )
    assert response.status_code == 200, response.text
    with EpubDocument(response.content) as book:
        assert book.version == "3.0"
    assert api.get("/provider/info").json()["key"] == "turkish-metadata"
    assert "Künye" in api.get("/").text


def test_already_epub3_upgrade_keeps_chapter_bytes():
    original = export(sample_epub())
    before, after = contents(original), contents(export(original))
    assert all(after[path] == data for path, data in before.items() if not path.endswith(".opf"))
