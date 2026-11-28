"""Conservative cover discovery and XML helpers shared by EPUB export operations."""

import posixpath
import re
from urllib.parse import quote, unquote, urlsplit
from xml.dom import Node

from defusedxml.minidom import parseString

from app.epub import MAX_XML, OPF, EpubError, archive_path, children

XHTML = "http://www.w3.org/1999/xhtml"
EPUB = "http://www.idpf.org/2007/ops"
XLINK = "http://www.w3.org/1999/xlink"


def xml_document(book, raw):
    # XHTML 1 external declarations are common in EPUB 2. Never resolve a DTD,
    # and never permit an internal subset or entity declarations.
    if b"<!ENTITY" in raw.upper() or re.search(rb"<!DOCTYPE[^>]*\[", raw, re.I):
        raise EpubError("İç entity veya DTD tanımı olan bölüm güvenle dönüştürülemiyor.")
    raw = re.sub(rb"<!DOCTYPE\s+[^>]+>", b"", raw, flags=re.I)
    book.xml(raw)
    return parseString(raw, forbid_dtd=True, forbid_entities=True, forbid_external=True)


def nodes(document, namespace=None, name=None):
    return [
        node
        for node in document.getElementsByTagName("*")
        if (namespace is None or node.namespaceURI == namespace)
        and (name is None or node.localName == name)
    ]


def href_path(base_file, href):
    try:
        parts = urlsplit(href)
    except ValueError:
        raise EpubError("Kitap içi bağlantı biçimi geçersiz.") from None
    if parts.scheme or parts.netloc:
        return None
    path = archive_path(posixpath.dirname(base_file), parts.path) if parts.path else base_file
    return path, unquote(parts.fragment)


def relative_href(base_file, target):
    return quote(posixpath.relpath(target, posixpath.dirname(base_file) or "."), safe="/._~-")


def manifest_items(book):
    return children(book.manifest, OPF, "item")


def item_path(book, item):
    return archive_path(posixpath.dirname(book.opf_path), item.getAttribute("href"))


def cover_pages(book):
    """Only recognize consecutive, image-only, clearly named/marked opening pages."""
    spines = children(book.package, OPF, "spine")
    if not spines:
        return []
    items = {item.getAttribute("id"): item for item in manifest_items(book)}
    marked = set()
    for guide in children(book.package, OPF, "guide"):
        for ref in children(guide, OPF, "reference"):
            if ref.getAttribute("type") == "cover":
                link = href_path(book.opf_path, ref.getAttribute("href"))
                if link:
                    marked.add(link[0])
    pages = []
    for ref in children(spines[0], OPF, "itemref")[:5]:
        item = items.get(ref.getAttribute("idref"))
        if item is None or item.getAttribute("media-type") != "application/xhtml+xml":
            break
        path = item_path(book, item)
        document = None
        try:
            document = xml_document(book, book.read(path, MAX_XML))
            bodies = nodes(document, XHTML, "body")
            if len(bodies) != 1:
                break
            body = bodies[0]
            named = re.search(r"(?:cover|title[-_]?page|kapak)", posixpath.basename(path), re.I)
            if not (
                named or path in marked or "cover" in body.getAttributeNS(EPUB, "type").split()
            ):
                break
            images = [n for n in nodes(body) if n.localName in ("img", "image")]
            forbidden = {"script", "object", "audio", "video", "iframe", "canvas", "table"}
            if len(images) != 1 or any(n.localName in forbidden for n in nodes(body)):
                break

            def visible_text(node):
                if node.nodeType in (Node.TEXT_NODE, Node.CDATA_SECTION_NODE):
                    return node.data
                if node.nodeType == Node.ELEMENT_NODE and node.localName in (
                    "style",
                    "title",
                    "desc",
                    "metadata",
                ):
                    return ""
                return "".join(visible_text(child) for child in node.childNodes)

            if visible_text(body).strip():
                break
            image = images[0]
            href = image.getAttribute("src") or image.getAttributeNS(XLINK, "href")
            link = href_path(path, href)
            if not link or link[1] or link[0] not in book.entries:
                break
            pages.append({"path": path, "image": link[0], "ref": ref})
        except (ValueError, KeyError, UnicodeError):
            break
        finally:
            if document is not None:
                document.unlink()
    return pages


def synchronize_cover(book, target, added):
    """Replace recognized cover-page references; collapse only those opening pages.

    Redundant page/image files remain in the archive. Links to a redundant cover
    page are redirected, so no chapter or illustration is deleted.
    """
    pages = cover_pages(book)
    if not pages:
        return
    redirects = {page["path"]: pages[0]["path"] for page in pages[1:]}
    for page in pages[1:]:
        page["ref"].parentNode.removeChild(page["ref"])
    for guide in children(book.package, OPF, "guide"):
        for ref in children(guide, OPF, "reference"):
            link = href_path(book.opf_path, ref.getAttribute("href"))
            if link and link[0] in redirects:
                ref.setAttribute("href", relative_href(book.opf_path, redirects[link[0]]))
    page_paths = {page["path"] for page in pages}
    for item in manifest_items(book):
        if item.getAttribute("media-type") not in (
            "application/xhtml+xml",
            "application/x-dtbncx+xml",
        ):
            continue
        path = item_path(book, item)
        if path not in page_paths and not redirects:
            continue
        raw = added.get(path, book.read(path, MAX_XML))
        document = xml_document(book, raw)
        changed = False
        try:
            for node in nodes(document):
                if path in page_paths and node.localName in ("img", "image"):
                    href = relative_href(path, target)
                    if node.localName == "img":
                        if node.getAttribute("src") != href:
                            node.setAttribute("src", href)
                            changed = True
                    elif node.getAttributeNS(XLINK, "href") != href:
                        node.setAttributeNS(XLINK, "xlink:href", href)
                        changed = True
                for attribute in ("href", "src"):
                    if not node.hasAttribute(attribute):
                        continue
                    link = href_path(path, node.getAttribute(attribute))
                    if link and link[0] in redirects:
                        node.setAttribute(attribute, relative_href(path, redirects[link[0]]))
                        changed = True
            if changed:
                added[path] = document.toxml(encoding="utf-8")
        finally:
            document.unlink()


def redirect_image(book, old, new, added):
    """Update references when the replacement format needs a different extension."""

    def css_links(value, source):
        def replace(match):
            link = href_path(source, match[2].strip())
            return (
                'url("' + relative_href(source, new) + '")' if link and link[0] == old else match[0]
            )

        return re.sub(r"url\(\s*([\"']?)(.*?)\1\s*\)", replace, value, flags=re.I)

    for item in manifest_items(book):
        kind = item.getAttribute("media-type")
        if kind not in ("application/xhtml+xml", "image/svg+xml", "text/css"):
            continue
        path = item_path(book, item)
        raw = added[path] if path in added else book.read(path, MAX_XML)
        if kind == "text/css":
            value = raw.decode("utf-8-sig")
            changed = css_links(value, path)
            if value != changed:
                added[path] = changed.encode()
            continue
        document = xml_document(book, raw)
        changed = False
        try:
            for node in nodes(document):
                for attribute in list(node.attributes.values()):
                    if attribute.localName in ("src", "href", "poster"):
                        link = href_path(path, attribute.value)
                        if link and link[0] == old:
                            attribute.value = relative_href(path, new)
                            changed = True
                    elif attribute.localName == "style":
                        value = css_links(attribute.value, path)
                        if value != attribute.value:
                            attribute.value = value
                            changed = True
                if node.localName == "style":
                    for child in node.childNodes:
                        if child.nodeType in (Node.TEXT_NODE, Node.CDATA_SECTION_NODE):
                            value = css_links(child.data, path)
                            if value != child.data:
                                child.data = value
                                changed = True
            if changed:
                added[path] = document.toxml(encoding="utf-8")
        finally:
            document.unlink()
