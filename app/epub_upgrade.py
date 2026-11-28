"""An opt-in EPUB 2 to EPUB 3 upgrade, keeping resources and reading order."""

import posixpath
import re
import uuid
from xml.dom import Node

from app.epub import DC, MAX_COVER, MAX_XML, OPF, XMLNS, EpubError, children, image_type, text
from app.epub_structure import (
    EPUB,
    XHTML,
    cover_pages,
    href_path,
    item_path,
    manifest_items,
    nodes,
    relative_href,
    xml_document,
)

XML = "http://www.w3.org/XML/1998/namespace"
NCX = "http://www.daisy.org/z3986/2005/ncx/"


def body_text(document):
    bodies = nodes(document, XHTML, "body")

    def collect(node):
        if node.nodeType in (Node.TEXT_NODE, Node.CDATA_SECTION_NODE):
            return node.data
        if node.nodeType == Node.ELEMENT_NODE and node.localName in ("style", "script"):
            return ""
        return "".join(collect(child) for child in node.childNodes)

    return collect(bodies[0]) if len(bodies) == 1 else ""


def upgrade_content(book, path, raw):
    document = xml_document(book, raw)
    changed = False
    properties = set()
    try:
        root = document.documentElement
        if root.namespaceURI != XHTML or root.localName != "html":
            raise EpubError(f"EPUB 3 için XHTML bölümü gerekiyor: {path}")
        if len(nodes(document, XHTML, "body")) != 1 or len(nodes(document, XHTML, "head")) != 1:
            raise EpubError(f"Bölümün başlık veya gövde yapısı geçersiz: {path}")
        before = body_text(document)
        for node in nodes(document):
            if node.namespaceURI == "http://www.w3.org/2000/svg":
                properties.add("svg")
            if node.namespaceURI == "http://www.w3.org/1998/Math/MathML":
                properties.add("mathml")
            if node.namespaceURI != XHTML:
                continue
            name = node.localName
            if name == "base" or node.hasAttributeNS(XML, "base"):
                raise EpubError(f"Özel bağlantı tabanı olan bölüm otomatik yükseltilmiyor: {path}")
            if name != "a" and any(
                node.getAttribute(attribute).startswith(("https:", "http:", "//"))
                for attribute in ("src", "href", "poster")
            ):
                raise EpubError(f"Harici kaynak kullanan bölüm otomatik yükseltilmiyor: {path}")
            if name in ("script", "iframe", "frameset", "frame", "object", "embed") or any(
                attribute.lower().startswith("on") for attribute in node.attributes.keys()
            ):
                raise EpubError(f"Etkileşimli bölüm EPUB 3'e otomatik yükseltilmiyor: {path}")
            if name == "meta" and node.getAttribute("http-equiv").lower() == "content-type":
                node.removeAttribute("http-equiv")
                if node.hasAttribute("content"):
                    node.removeAttribute("content")
                node.setAttribute("charset", "utf-8")
                changed = True
            if name == "a" and node.hasAttribute("name"):
                value = node.getAttribute("name")
                if node.hasAttribute("id") and node.getAttribute("id") != value:
                    anchor = document.createElementNS(XHTML, "span")
                    anchor.setAttribute("id", value)
                    node.parentNode.insertBefore(anchor, node)
                else:
                    node.setAttribute("id", value)
                node.removeAttribute("name")
                changed = True
            rename = {
                "center": "div",
                "big": "span",
                "tt": "span",
                "strike": "span",
                "acronym": "abbr",
            }
            style = {
                "center": "text-align: center",
                "big": "font-size: larger",
                "tt": "font-family: monospace",
                "strike": "text-decoration: line-through",
            }.get(name, "")
            if name in rename:
                document.renameNode(node, XHTML, rename[name])
                changed = True
            # Avoid silently changing publisher-specific legacy font/table layouts.
            if name in ("font", "applet", "basefont") or any(
                node.hasAttribute(attribute)
                for attribute in ("bgcolor", "background", "cellpadding", "cellspacing")
            ):
                raise EpubError(
                    f"Bu eski sayfa düzeni otomatik EPUB 3 dönüşümü gerektiriyor: {path}"
                )
            if node.hasAttribute("align"):
                value = node.getAttribute("align").lower()
                if value not in ("left", "right", "center", "justify") or name in ("img", "table"):
                    raise EpubError(f"Bölüm hizalaması güvenle dönüştürülemiyor: {path}")
                style = f"text-align: {value}; " + style
                node.removeAttribute("align")
                changed = True
            if style:
                node.setAttribute("style", style + "; " + node.getAttribute("style"))
            if name == "link" and node.getAttribute("type") == "text/css":
                # The stylesheet bytes and original reference remain unchanged.
                pass
        if body_text(document) != before:
            raise EpubError(f"Dönüşüm bölüm metnini değiştirdi; çıktı durduruldu: {path}")
        # An XHTML 1 external doctype is removed, without rewriting unaffected XML.
        result = (
            document.toxml(encoding="utf-8")
            if changed
            else re.sub(rb"<!DOCTYPE\s+[^>]+>", b"", raw, flags=re.I)
        )
        return result, properties
    finally:
        document.unlink()


def upgrade_metadata(book):
    if book.primary is None:
        identifier = book.element(
            DC, "identifier", "urn:uuid:" + str(uuid.uuid5(uuid.NAMESPACE_URL, book.source_digest))
        )
        identifier.setAttribute("id", book.unique_id("kunye-uid"))
        book.metadata.appendChild(identifier)
        book.package.setAttribute("unique-identifier", identifier.getAttribute("id"))
        book.primary = identifier
    for node in list(book.metadata.childNodes):
        if node.nodeType != Node.ELEMENT_NODE or node.namespaceURI != DC:
            continue
        for attribute, property_name in (("role", "role"), ("file-as", "file-as")):
            value = node.getAttributeNS(OPF, attribute)
            if not value:
                continue
            identifier = node.getAttribute("id") or book.unique_id("kunye-person")
            node.setAttribute("id", identifier)
            meta = book.element(OPF, "meta", value)
            meta.setAttribute("refines", "#" + identifier)
            meta.setAttribute("property", property_name)
            if attribute == "role":
                meta.setAttribute("scheme", "marc:relators")
            book.metadata.appendChild(meta)
            node.removeAttributeNS(OPF, attribute)
        if node.hasAttributeNS(OPF, "scheme"):
            scheme = node.getAttributeNS(OPF, "scheme")
            node.removeAttributeNS(OPF, "scheme")
            if scheme.upper() == "ISBN" and node.localName == "identifier":
                identifier = node.getAttribute("id") or book.unique_id("kunye-isbn")
                node.setAttribute("id", identifier)
                meta = book.element(
                    OPF, "meta", "15" if len(text(node).removeprefix("urn:isbn:")) == 13 else "02"
                )
                meta.setAttribute("refines", "#" + identifier)
                meta.setAttribute("property", "identifier-type")
                meta.setAttribute("scheme", "onix:codelist5")
                book.metadata.appendChild(meta)
        if node.hasAttributeNS(OPF, "event"):
            # The date value itself remains in place; EPUB 2's event attribute is legacy.
            node.removeAttributeNS(OPF, "event")
    book.package.setAttribute("version", "3.0")
    book.version = "3.0"


def synchronize_ncx_identity(book, added):
    for item in manifest_items(book):
        if item.getAttribute("media-type") != "application/x-dtbncx+xml":
            continue
        path = item_path(book, item)
        raw = added[path] if path in added else book.read(path, MAX_XML)
        document = xml_document(book, raw)
        try:
            metas = [
                node
                for node in nodes(document, NCX, "meta")
                if node.getAttribute("name") == "dtb:uid"
            ]
            if metas and metas[0].getAttribute("content") != text(book.primary):
                metas[0].setAttribute("content", text(book.primary))
                added[path] = document.toxml(encoding="utf-8")
        finally:
            document.unlink()


def make_navigation(book, added, spine, items):
    document = book.document.implementation.createDocument(XHTML, "html", None)
    try:
        root = document.documentElement
        root.setAttributeNS(XMLNS, "xmlns", XHTML)
        root.setAttributeNS(XMLNS, "xmlns:epub", EPUB)
        language = book.metadata_dict()["language"]
        root.setAttributeNS(XML, "xml:lang", language)
        root.setAttribute("lang", language)

        def element(parent, name, value=None):
            node = document.createElementNS(XHTML, name)
            if value is not None:
                node.appendChild(document.createTextNode(value))
            parent.appendChild(node)
            return node

        head = element(root, "head")
        element(head, "title", "İçindekiler")
        body = element(root, "body")
        nav = element(body, "nav")
        nav.setAttributeNS(EPUB, "epub:type", "toc")
        nav.setAttribute("id", "toc")
        element(nav, "h1", "İçindekiler")
        listing = element(nav, "ol")
        nav_id = book.unique_id("kunye-nav")
        path = posixpath.join(posixpath.dirname(book.opf_path), nav_id + ".xhtml")
        while path in book.entries:
            path = path.removesuffix(".xhtml") + "x.xhtml"

        def link(parent, label, source, href):
            target = href_path(source, href)
            if target is None or not label.strip():
                raise EpubError("İçindekilerde yerel olmayan veya boş bir bağlantı var.")
            anchor = element(parent, "a", label.strip())
            anchor.setAttribute(
                "href", relative_href(path, target[0]) + ("#" + target[1] if target[1] else "")
            )

        ncx_item = items.get(spine.getAttribute("toc")) or next(
            (
                item
                for item in items.values()
                if item.getAttribute("media-type") == "application/x-dtbncx+xml"
            ),
            None,
        )
        if ncx_item is not None:
            ncx_path = item_path(book, ncx_item)
            ncx = xml_document(book, added.get(ncx_path, book.read(ncx_path, MAX_XML)))
            try:
                maps = nodes(ncx, NCX, "navMap")
                if len(maps) != 1 or not children(maps[0], NCX, "navPoint"):
                    raise EpubError(
                        "Mevcut içindekiler belgesi okunamıyor; EPUB 3 çıktısı durduruldu."
                    )

                def branch(source, destination):
                    for point in children(source, NCX, "navPoint"):
                        labels = nodes(point, NCX, "navLabel")
                        sources = children(point, NCX, "content")
                        label_nodes = nodes(labels[0], NCX, "text") if labels else []
                        if not label_nodes or len(sources) != 1:
                            raise EpubError("İçindekilerde eksik bir bölüm kaydı var.")
                        row = element(destination, "li")
                        link(row, text(label_nodes[0]), ncx_path, sources[0].getAttribute("src"))
                        if children(point, NCX, "navPoint"):
                            branch(point, element(row, "ol"))

                branch(maps[0], listing)
                # Preserve print-page navigation when present in the old NCX.
                page_lists = nodes(ncx, NCX, "pageList")
                if page_lists and children(page_lists[0], NCX, "pageTarget"):
                    page_nav = element(body, "nav")
                    page_nav.setAttributeNS(EPUB, "epub:type", "page-list")
                    page_nav.setAttribute("hidden", "hidden")
                    page_rows = element(page_nav, "ol")
                    for page in children(page_lists[0], NCX, "pageTarget"):
                        label_nodes = nodes(page, NCX, "text")
                        targets = children(page, NCX, "content")
                        if not label_nodes or len(targets) != 1:
                            raise EpubError("Basılı sayfa listesindeki bir kayıt okunamıyor.")
                        link(
                            element(page_rows, "li"),
                            text(label_nodes[0]),
                            ncx_path,
                            targets[0].getAttribute("src"),
                        )
            finally:
                ncx.unlink()
        else:
            for index, ref in enumerate(children(spine, OPF, "itemref"), 1):
                item = items.get(ref.getAttribute("idref"))
                if item is None:
                    raise EpubError("Bölüm sırasındaki bir dosya bulunamadı.")
                chapter_path = item_path(book, item)
                chapter = xml_document(
                    book, added.get(chapter_path, book.read(chapter_path, MAX_XML))
                )
                try:
                    headings = (
                        nodes(chapter, XHTML, "h1")
                        or nodes(chapter, XHTML, "h2")
                        or nodes(chapter, XHTML, "title")
                    )
                    label = text(headings[0]) if headings else ""
                    link(
                        element(listing, "li"),
                        label or f"Bölüm {index}",
                        book.opf_path,
                        item.getAttribute("href"),
                    )
                finally:
                    chapter.unlink()
        item = book.element(OPF, "item", "")
        item.setAttribute("id", nav_id)
        item.setAttribute("href", relative_href(book.opf_path, path))
        item.setAttribute("media-type", "application/xhtml+xml")
        item.setAttribute("properties", "nav")
        book.manifest.appendChild(item)
        added[path] = document.toxml(encoding="utf-8")
    finally:
        document.unlink()


def validate_links(book, added):
    anchors = {}
    references = []
    budget = 16 * 1024 * 1024
    node_budget = 250000
    for item in manifest_items(book):
        path = item_path(book, item)
        if path not in book.entries and path not in added:
            raise EpubError(f"Kitapta eksik bir kaynak var: {path}")
        if item.getAttribute("media-type") != "application/xhtml+xml":
            continue
        raw = added[path] if path in added else book.read(path, MAX_XML)
        budget -= len(raw)
        if budget < 0:
            raise EpubError("EPUB 3 bağlantı denetimi için bölüm boyutu 16 MiB'ı aşıyor.")
        document = xml_document(book, raw)
        ids = set()
        try:
            for node in nodes(document):
                node_budget -= 1
                if node_budget < 0:
                    raise EpubError("Kitap EPUB 3 bağlantı denetimi için çok karmaşık.")
                identifier = node.getAttribute("id") or node.getAttributeNS(XML, "id")
                if identifier:
                    if identifier in ids:
                        raise EpubError(f"Bölümde yinelenen bağlantı kimliği var: {path}")
                    ids.add(identifier)
                for attribute in node.attributes.values():
                    if attribute.localName in (
                        "href",
                        "src",
                        "poster",
                    ) and not attribute.name.startswith("xmlns"):
                        value = attribute.value
                        target = href_path(path, value)
                        if target is not None and value:
                            references.append(target)
                        if len(references) > 50000:
                            raise EpubError("Kitapta çok fazla bağlantı var.")
            anchors[path] = ids
        finally:
            document.unlink()
    for path, fragment in references:
        if path not in book.entries and path not in added:
            raise EpubError(f"Kırık bir kitap içi bağlantı var: {path}")
        if fragment and path in anchors and fragment not in anchors[path]:
            raise EpubError(f"Bağlantının bölüm içi hedefi bulunamadı: {path}#{fragment}")


def upgrade_to_epub3(book, added):
    if book.version.startswith("3."):
        return
    if not book.metadata_dict()["language"]:
        raise EpubError("EPUB 3 için önce dil kodunu doldurun (ör. tr).")
    if any(text(meta) == "pre-paginated" for meta in children(book.metadata, OPF, "meta")):
        raise EpubError("Sabit sayfa düzenli kitap otomatik EPUB 3'e yükseltilmiyor.")
    spines = children(book.package, OPF, "spine")
    if len(spines) != 1 or not children(spines[0], OPF, "itemref"):
        raise EpubError("Kitabın okuma sırası eksik.")
    items = {item.getAttribute("id"): item for item in manifest_items(book)}
    if len(items) != len(manifest_items(book)) or "" in items:
        raise EpubError("Kitabın kaynak kimlikleri yineleniyor veya eksik.")
    for ref in children(spines[0], OPF, "itemref"):
        if ref.getAttribute("idref") not in items:
            raise EpubError("Kitabın okuma sırasında eksik bir bölüm var.")
    content_budget = 16 * 1024 * 1024
    for item in items.values():
        media = item.getAttribute("media-type")
        if media in ("application/xhtml+xml", "text/html"):
            path = item_path(book, item)
            raw = added[path] if path in added else book.read(path, MAX_XML)
            content_budget -= len(raw)
            if content_budget < 0:
                raise EpubError("EPUB 3 dönüşümü için bölüm boyutu 16 MiB'ı aşıyor.")
            data, properties = upgrade_content(book, path, raw)
            if data != raw:
                added[path] = data
            item.setAttribute("media-type", "application/xhtml+xml")
            properties.update(item.getAttribute("properties").split())
            if properties:
                item.setAttribute("properties", " ".join(sorted(properties)))
        fonts = {
            "application/x-font-ttf": "font/ttf",
            "application/x-font-opentype": "font/otf",
            "application/vnd.ms-opentype": "font/otf",
        }
        if media in fonts:
            item.setAttribute("media-type", fonts[media])
    if not any("nav" in item.getAttribute("properties").split() for item in items.values()):
        make_navigation(book, added, spines[0], items)
    cover = book.current_cover()
    if cover is None:
        pages = cover_pages(book)
        if pages:
            media, _ = image_type(book.read(pages[0]["image"], MAX_COVER))
            cover = book.element(OPF, "item", "")
            cover.setAttribute("id", book.unique_id("kunye-cover"))
            cover.setAttribute("href", relative_href(book.opf_path, pages[0]["image"]))
            cover.setAttribute("media-type", media)
            book.manifest.appendChild(cover)
    if cover is not None:
        properties = set(cover.getAttribute("properties").split()) | {"cover-image"}
        cover.setAttribute("properties", " ".join(sorted(properties)))
    upgrade_metadata(book)
    synchronize_ncx_identity(book, added)
    validate_links(book, added)
