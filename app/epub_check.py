"""Bounded, read-only book checks. No repair, network access or EPUBCheck claim."""

import re
import zipfile
from xml.etree.ElementTree import ParseError
from xml.parsers.expat import ExpatError

from defusedxml.common import DefusedXmlException

from app.epub import MAX_XML, OPF, EpubError, children
from app.epub_structure import EPUB, XHTML, cover_pages, href_path, nodes, xml_document

XML = "http://www.w3.org/XML/1998/namespace"
PARSE_ERRORS = (EpubError, ParseError, ExpatError, DefusedXmlException, UnicodeError, ValueError)


def inspect_book(book):
    issues = []
    counts = {"error": 0, "warning": 0}
    complete = True

    def issue(severity, code, message, path=""):
        counts[severity] += 1
        if len(issues) < 100:
            issues.append({"severity": severity, "code": code, "message": message, "file": path})

    try:
        bad = book.archive.testzip()
        if bad:
            issue("error", "crc", "Arşivde okunamayan bir dosya var.", bad)
    except (zipfile.BadZipFile, RuntimeError, OSError):
        issue("error", "crc", "Arşivin bütünlük kontrolü tamamlanamadı.")

    items = children(book.manifest, OPF, "item")
    by_id, listed = {}, {}
    for item in items:
        identifier = item.getAttribute("id")
        if not identifier or identifier in by_id:
            issue("error", "manifest_id", "Kaynak kimliği eksik veya yineleniyor.", book.opf_path)
        by_id[identifier] = item
        try:
            target = href_path(book.opf_path, item.getAttribute("href"))
            if target is None:
                issue("warning", "external_resource", "Kitap dış bir kaynağa bağlı.")
                continue
            path = target[0]
            listed[path] = item
            if path not in book.entries:
                issue(
                    "error", "missing_resource", "Kitapta kayıtlı bir kaynak dosyası eksik.", path
                )
        except PARSE_ERRORS:
            issue("error", "resource_path", "Kaynak dosyalarından birinin bağlantısı geçersiz.")

    spines = children(book.package, OPF, "spine")
    spine_refs = children(spines[0], OPF, "itemref") if len(spines) == 1 else []
    if not spine_refs:
        issue("error", "missing_spine", "Kitabın okuma sırası bulunamadı.")
    seen = set()
    for ref in spine_refs:
        identifier = ref.getAttribute("idref")
        if identifier not in by_id:
            issue("error", "missing_chapter", "Okuma sırasında bulunamayan bir bölüm var.")
        elif identifier in seen:
            issue("warning", "repeated_chapter", "Aynı bölüm okuma sırasında tekrar listeleniyor.")
        seen.add(identifier)

    metadata = book.metadata_dict()
    if not metadata["title"]:
        issue("error", "missing_title", "Kitap adı boş.")
    if not metadata["language"]:
        issue("warning", "missing_language", "Kitabın dil kodu boş.")
    if book.primary is None:
        issue("warning", "missing_identity", "Kitabın ana kimliği tanımlanmamış.")
    nav_items = [item for item in items if "nav" in item.getAttribute("properties").split()]
    if book.version.startswith("3.") and len(nav_items) != 1:
        issue("error", "navigation", "EPUB 3 kitabında tek bir içindekiler belgesi gerekiyor.")
    if book.version.startswith("2.") and not any(
        item.getAttribute("media-type") == "application/x-dtbncx+xml" for item in items
    ):
        issue("warning", "navigation", "EPUB 2 içindekiler belgesi bulunamadı.")
    try:
        pages = cover_pages(book)
        if len(pages) > 1:
            issue("warning", "duplicate_cover", f"Başlangıçta {len(pages)} ayrı kapak sayfası var.")
        if book.current_cover() is None and not pages:
            issue("warning", "cover_missing", "Kitap kapağı belirlenemedi.")
    except PARSE_ERRORS:
        issue("warning", "cover_unchecked", "Başlangıçtaki kapak sayfaları tam denetlenemedi.")

    anchors, references = {}, []
    byte_budget, node_budget = 16 * 1024 * 1024, 250000
    checked = 0
    reference_limit = False

    def add_reference(source, value, resource):
        nonlocal reference_limit
        if not value or value.startswith("data:"):
            return
        if len(references) >= 50000:
            reference_limit = True
            return
        try:
            target = href_path(source, value)
            if target is None:
                if resource:
                    issue(
                        "warning",
                        "external_resource",
                        "Bu dosya dış bir görsel veya kaynağa bağlı.",
                        source,
                    )
                return
            references.append((source, target[0], target[1], resource))
        except PARSE_ERRORS:
            issue("error", "invalid_link", "Dosyada geçersiz bir kitap içi bağlantı var.", source)

    for path, item in listed.items():
        if path not in book.entries:
            continue
        media = item.getAttribute("media-type")
        if media not in (
            "application/xhtml+xml",
            "text/html",
            "image/svg+xml",
            "application/x-dtbncx+xml",
            "text/css",
        ):
            continue
        info = book.entries[path]
        byte_budget -= info.file_size
        if byte_budget < 0 or info.file_size > MAX_XML:
            complete = False
            continue
        document = None
        try:
            raw = book.read(path, MAX_XML)
            if media == "text/css":
                css = re.sub(r"/\*.*?\*/", "", raw.decode("utf-8-sig"), flags=re.S)
                for match in re.finditer(r"url\(\s*([\"']?)(.*?)\1\s*\)", css, re.I):
                    add_reference(path, match[2].strip(), True)
                for match in re.finditer(r"@import\s+[\"']([^\"']+)[\"']", css, re.I):
                    add_reference(path, match[1], True)
                checked += 1
                continue
            document = xml_document(book, raw)
            elements = nodes(document)
            node_budget -= len(elements)
            if node_budget < 0:
                complete = False
                break
            ids = set()
            for node in elements:
                identifier = node.getAttribute("id") or node.getAttributeNS(XML, "id")
                if identifier:
                    if identifier in ids:
                        issue(
                            "error",
                            "duplicate_anchor",
                            "Bölüm içinde aynı bağlantı kimliği tekrarlanıyor.",
                            path,
                        )
                    ids.add(identifier)
                if node.localName == "a" and node.hasAttribute("name"):
                    ids.add(node.getAttribute("name"))
                for attribute in node.attributes.values():
                    if attribute.localName not in ("href", "src", "poster"):
                        continue
                    if attribute.name.startswith("xmlns"):
                        continue
                    resource = not (
                        node.localName == "a"
                        and attribute.localName == "href"
                        or media == "application/x-dtbncx+xml"
                    )
                    add_reference(path, attribute.value, resource)
            anchors[path] = ids
            if (
                item in nav_items
                and len(
                    [
                        node
                        for node in nodes(document, XHTML, "nav")
                        if "toc" in node.getAttributeNS(EPUB, "type").split()
                    ]
                )
                != 1
            ):
                issue(
                    "error",
                    "navigation_toc",
                    "İçindekiler belgesinin bölüm listesi eksik veya yineleniyor.",
                    path,
                )
            checked += 1
        except PARSE_ERRORS:
            issue("error", "invalid_xml", "Bu bölüm veya kaynak güvenle okunamadı.", path)
        finally:
            if document is not None:
                document.unlink()
    if not complete or reference_limit:
        complete = False
        issue(
            "warning",
            "check_limit",
            "Kitap büyük veya karmaşık olduğu için denetim kısmen tamamlandı.",
        )
    reported = set()
    for source, target, fragment, resource in references:
        key = (source, target, fragment)
        if key in reported:
            continue
        reported.add(key)
        if target not in book.entries:
            code = "missing_image" if resource else "broken_link"
            issue("error", code, f"Bağlantının hedef dosyası eksik: {target}", source)
        elif target not in listed:
            issue(
                "warning",
                "unlisted_resource",
                f"Dosya kitap içinde var, kaynak listesine eklenmemiş: {target}",
                source,
            )
        elif fragment and target in anchors and fragment not in anchors[target]:
            issue(
                "error",
                "broken_anchor",
                f"Bölüm içi bağlantı hedefi bulunamadı: {target}#{fragment}",
                source,
            )
    return {
        "errors": counts["error"],
        "warnings": counts["warning"],
        "complete": complete,
        "issues": issues,
        "issues_truncated": sum(counts.values()) > len(issues),
        "stats": {
            "files": len(book.entries),
            "reading_order": len(spine_refs),
            "images": sum(item.getAttribute("media-type").startswith("image/") for item in items),
            "checked_documents": checked,
        },
        "scope": (
            "Arşiv, bölüm sırası, içindekiler, kaynaklar ve kitap içi bağlantılar denetlendi. "
            "Görünüm ve cihaz uyumluluğu ayrıca kontrol edilmelidir."
        ),
    }
