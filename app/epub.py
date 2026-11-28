"""Bounded, stateless EPUB metadata editing. No archive extraction or retained uploads."""

import base64
import copy
import hashlib
import io
import posixpath
import re
import stat
import zipfile
from datetime import UTC, datetime
from urllib.parse import unquote, urlsplit
from xml.dom import Node

from defusedxml import ElementTree
from defusedxml.minidom import parseString
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.text import normalize_isbn

MAX_UPLOAD = 25 * 1024 * 1024
MAX_EXPANDED = 128 * 1024 * 1024
MAX_XML = 2 * 1024 * 1024
MAX_COVER = 5 * 1024 * 1024
DC = "http://purl.org/dc/elements/1.1/"
OPF = "http://www.idpf.org/2007/opf"
XMLNS = "http://www.w3.org/2000/xmlns/"


class EpubError(ValueError):
    pass


class EpubMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=1000)
    authors: list[str] = Field(default_factory=list, max_length=50)
    translators: list[str] = Field(default_factory=list, max_length=50)
    language: str = Field(default="", max_length=50)
    publisher: str = Field(default="", max_length=1000)
    published_date: str = Field(default="", max_length=32)
    description: str = Field(default="", max_length=50000)
    isbn: str = Field(default="", max_length=64)

    @field_validator("authors", "translators")
    @classmethod
    def names(cls, values):
        if any(not value.strip() or len(value) > 300 for value in values):
            raise ValueError("Her kişi adı 1–300 karakter olmalı.")
        return list(dict.fromkeys(value.strip() for value in values))

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value):
        if not value.strip():
            raise ValueError("Başlık boş bırakılamaz.")
        return value.strip()

    @field_validator("isbn")
    @classmethod
    def valid_isbn(cls, value):
        if value.strip() and not normalize_isbn(value):
            raise ValueError("ISBN kontrol basamağı geçersiz.")
        return normalize_isbn(value) or ""

    @field_validator("language")
    @classmethod
    def valid_language(cls, value):
        if value and not re.fullmatch(r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*", value):
            raise ValueError("Dil kodunu tr veya tr-TR gibi yazın.")
        return value

    @field_validator("published_date")
    @classmethod
    def valid_date(cls, value):
        if value:
            if not re.fullmatch(r"\d{4}(?:-\d{2}(?:-\d{2})?)?", value):
                raise ValueError("Tarih YYYY, YYYY-MM veya YYYY-MM-DD olmalı.")
            datetime.fromisoformat(value + {4: "-01-01", 7: "-01", 10: ""}[len(value)])
        return value

    @field_validator("*", mode="after")
    @classmethod
    def xml_text(cls, value):
        values = value if isinstance(value, list) else [value]
        for item in values:
            if isinstance(item, str) and any(
                not (
                    c in "\t\n\r"
                    or 0x20 <= ord(c) <= 0xD7FF
                    or 0xE000 <= ord(c) <= 0xFFFD
                    or 0x10000 <= ord(c) <= 0x10FFFF
                )
                for c in item
            ):
                raise ValueError("Metin XML içinde kullanılamayan karakter içeriyor.")
        return value


def text(node):
    return "".join(
        child.data
        for child in node.childNodes
        if child.nodeType in (Node.TEXT_NODE, Node.CDATA_SECTION_NODE)
    ).strip()


def children(node, namespace, name):
    return [
        child
        for child in node.childNodes
        if child.nodeType == Node.ELEMENT_NODE
        and child.namespaceURI == namespace
        and child.localName == name
    ]


def image_type(data):
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    raise EpubError("Kapak JPEG veya PNG biçiminde olmalı.")


def archive_path(base, href):
    parts = urlsplit(href)
    if parts.scheme or parts.netloc or parts.query or parts.fragment or "\\" in href:
        raise EpubError("EPUB içinde geçersiz dosya bağlantısı var.")
    path = posixpath.normpath(posixpath.join(base, unquote(parts.path)))
    if path.startswith(("/", "../")) or path == "..":
        raise EpubError("EPUB bağlantısı arşivin dışına çıkıyor.")
    return path


def kepub_filename(filename):
    return filename.lower().endswith((".kepub", ".kepub.epub"))


class EpubDocument:
    def __init__(self, payload):
        self.document = None
        self.archive = None
        try:
            self._open(payload)
        except Exception:
            self.close()
            raise

    def _open(self, payload):
        if len(payload) > MAX_UPLOAD:
            raise EpubError("EPUB en fazla 25 MiB olabilir.")
        self.source_digest = hashlib.sha256(payload).hexdigest()
        self.archive = zipfile.ZipFile(io.BytesIO(payload))
        infos = self.archive.infolist()
        self.entries = {info.filename: info for info in infos}
        if len(infos) > 4000 or len(self.entries) != len(infos):
            raise EpubError("Arşiv çok fazla veya yinelenen dosya içeriyor.")
        if sum(info.file_size for info in infos) > MAX_EXPANDED:
            raise EpubError("EPUB'un açılmış boyutu 128 MiB sınırını aşıyor.")
        for info in infos:
            name = info.filename
            if (
                "\\" in name
                or "\x00" in name
                or name.startswith("/")
                or ".." in name.split("/")
                or ":" in name.split("/")[0]
                or stat.S_ISLNK(info.external_attr >> 16)
                or info.flag_bits & 1
                or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
            ):
                raise EpubError("EPUB arşiv yapısı desteklenmiyor.")
        if self.read("mimetype", 100) != b"application/epub+zip":
            raise EpubError("Bu dosya geçerli bir EPUB arşivi değil.")
        if "META-INF/signatures.xml" in self.entries:
            raise EpubError("Dijital imzalı EPUB bu düzenleyicide değiştirilemez.")
        if "META-INF/encryption.xml" in self.entries:
            encryption = self.xml(self.read("META-INF/encryption.xml", MAX_XML))
            allowed = {"http://www.idpf.org/2008/embedding", "http://ns.adobe.com/pdf/enc#RC"}
            methods = [node for node in encryption.iter() if node.tag.endswith("}EncryptionMethod")]
            if not methods or any(node.get("Algorithm") not in allowed for node in methods):
                raise EpubError("DRM ile korunan EPUB desteklenmiyor.")
        container = self.xml(self.read("META-INF/container.xml", MAX_XML))
        rootfiles = container.findall(
            ".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile"
        )
        if len(rootfiles) != 1:
            raise EpubError("Tek paket belgesi içeren EPUB gerekiyor.")
        self.opf_path = archive_path("", rootfiles[0].get("full-path", ""))
        raw = self.read(self.opf_path, MAX_XML)
        self.xml(raw)  # Enforce depth/node bounds before constructing a DOM.
        self.document = parseString(
            raw, forbid_dtd=True, forbid_entities=True, forbid_external=True
        )
        self.package = self.document.documentElement
        if self.package.namespaceURI != OPF or self.package.localName != "package":
            raise EpubError("EPUB paket belgesi geçersiz.")
        self.version = self.package.getAttribute("version")
        if not self.version.startswith(("2.", "3.")):
            raise EpubError("Yalnız EPUB 2 ve EPUB 3 destekleniyor.")
        metadata = children(self.package, OPF, "metadata")
        manifests = children(self.package, OPF, "manifest")
        if len(metadata) != 1 or len(manifests) != 1:
            raise EpubError("EPUB metadata veya manifest bölümü eksik.")
        self.metadata, self.manifest = metadata[0], manifests[0]
        uid = self.package.getAttribute("unique-identifier")
        self.primary = next(
            (n for n in children(self.metadata, DC, "identifier") if n.getAttribute("id") == uid),
            None,
        )
        self.original_primary = text(self.primary) if self.primary else None

    @staticmethod
    def xml(raw):
        root = ElementTree.fromstring(
            raw, forbid_dtd=True, forbid_entities=True, forbid_external=True
        )
        stack = [(root, 1)]
        count = 0
        while stack:
            node, depth = stack.pop()
            count += 1
            if depth > 64 or count > 20000:
                raise EpubError("XML belgesi çok karmaşık.")
            stack.extend((child, depth + 1) for child in node)
        return root

    def read(self, name, limit):
        entry = self.entries.get(name)
        if not entry or entry.file_size > limit:
            raise EpubError("EPUB içindeki gerekli bir dosya eksik veya çok büyük.")
        with self.archive.open(entry) as source:
            data = source.read(limit + 1)
        if len(data) > limit:
            raise EpubError("EPUB içindeki bir dosya boyut sınırını aşıyor.")
        return data

    def role(self, node):
        direct = node.getAttributeNS(OPF, "role")
        if direct:
            return direct
        identifier = node.getAttribute("id")
        return next(
            (
                text(meta)
                for meta in children(self.metadata, OPF, "meta")
                if identifier
                and meta.getAttribute("refines") == "#" + identifier
                and meta.getAttribute("property") == "role"
            ),
            "",
        )

    def metadata_dict(self):
        def first(name):
            return next((text(n) for n in children(self.metadata, DC, name)), "")

        isbn = next(
            (
                normalize_isbn(text(n).removeprefix("urn:isbn:"))
                for n in children(self.metadata, DC, "identifier")
                if normalize_isbn(text(n).removeprefix("urn:isbn:"))
            ),
            "",
        )
        return {
            "title": text(self.main_title()) if self.main_title() is not None else "",
            "authors": [
                text(n)
                for n in children(self.metadata, DC, "creator")
                if self.role(n) in ("", "aut")
            ],
            "translators": [
                text(n) for n in children(self.metadata, DC, "contributor") if self.role(n) == "trl"
            ],
            "language": first("language"),
            "publisher": first("publisher"),
            "published_date": first("date"),
            "description": first("description"),
            "isbn": isbn,
        }

    def main_title(self):
        titles = children(self.metadata, DC, "title")
        main_ids = {
            meta.getAttribute("refines").removeprefix("#")
            for meta in children(self.metadata, OPF, "meta")
            if meta.getAttribute("property") == "title-type" and text(meta) == "main"
        }
        return next(
            (title for title in titles if title.getAttribute("id") in main_ids),
            titles[0] if titles else None,
        )

    def current_cover(self):
        items = children(self.manifest, OPF, "item")
        cover_id = next(
            (
                n.getAttribute("content")
                for n in children(self.metadata, OPF, "meta")
                if n.getAttribute("name") == "cover"
            ),
            "",
        )
        declared = next(
            (item for item in items if "cover-image" in item.getAttribute("properties").split()),
            next(
                (item for item in items if cover_id and item.getAttribute("id") == cover_id), None
            ),
        )
        if declared is not None:
            return declared
        from app.epub_structure import cover_pages, item_path

        pages = cover_pages(self)
        if pages:
            return next(
                (item for item in items if item_path(self, item) == pages[0]["image"]), None
            )
        return None

    def has_kepub_markup(self):
        """Recognize existing Kobo spans without parsing or rewriting chapter content."""
        budget = 8 * 1024 * 1024
        marker = re.compile(
            rb"<(?:[\w.-]+:)?span\b[^>]{0,2048}\bclass\s*=\s*[\"\'][^\"\']*\bkoboSpan\b"
        )
        for item in children(self.manifest, OPF, "item"):
            if item.getAttribute("media-type") not in ("application/xhtml+xml", "text/html"):
                continue
            path = archive_path(posixpath.dirname(self.opf_path), item.getAttribute("href"))
            if path not in self.entries:
                continue
            with self.archive.open(self.entries[path]) as chapter:
                data = chapter.read(min(budget, MAX_XML))
            if marker.search(data):
                return True
            budget -= len(data)
            if budget <= 0:
                break
        return False

    def cover_data(self):
        cover = self.current_cover()
        from app.epub_structure import cover_pages

        pages = cover_pages(self) if cover is None else []
        if cover is not None or pages:
            try:
                data = self.read(
                    archive_path(posixpath.dirname(self.opf_path), cover.getAttribute("href"))
                    if cover is not None
                    else pages[0]["image"],
                    MAX_COVER,
                )
                image_type(data)
                return data
            except (EpubError, ValueError, KeyError):
                pass
        return None

    def preview(self):
        data = self.cover_data()
        if data is not None:
            media, _ = image_type(data)
            return f"data:{media};base64,{base64.b64encode(data).decode()}"
        return None

    def element(self, namespace, name, value):
        # Local namespace declarations preserve even unusual source prefix bindings.
        prefix = "bo-dc" if namespace == DC else "bo-opf"
        node = self.document.createElementNS(namespace, f"{prefix}:{name}")
        node.setAttributeNS(XMLNS, f"xmlns:{prefix}", namespace)
        node.appendChild(self.document.createTextNode(value))
        return node

    def remove(self, node):
        identifier = node.getAttribute("id")
        for meta in children(self.metadata, OPF, "meta"):
            if identifier and meta.getAttribute("refines") == "#" + identifier:
                self.metadata.removeChild(meta)
        self.metadata.removeChild(node)

    def set_scalar(self, name, value):
        nodes = children(self.metadata, DC, name)
        # Only the first title is the editable main title; preserve other titles and refinements.
        if name == "title" and nodes:
            main = self.main_title()
            for child in list(main.childNodes):
                main.removeChild(child)
            main.appendChild(self.document.createTextNode(value))
            return
        for node in nodes:
            self.remove(node)
        if value:
            self.metadata.appendChild(self.element(DC, name, value))

    def unique_id(self, base):
        used = {n.getAttribute("id") for n in self.document.getElementsByTagName("*")}
        identifier = base
        while identifier in used:
            identifier += "x"
        return identifier

    def set_people(self, name, names, role):
        old = [
            node
            for node in children(self.metadata, DC, name)
            if self.role(node) == role or (role == "aut" and not self.role(node))
        ]
        retained = {}
        for node in old:
            if text(node) in names and text(node) not in retained:
                retained[text(node)] = node
            else:
                self.remove(node)
        for index, value in enumerate(names):
            if value in retained:
                self.metadata.appendChild(retained[value])
                continue
            node = self.element(DC, name, value)
            self.metadata.appendChild(node)
            if self.version.startswith("2."):
                node.setAttributeNS(XMLNS, "xmlns:bo-opf", OPF)
                node.setAttributeNS(OPF, "bo-opf:role", role)
            else:
                identifier = self.unique_id(f"bo-{role}-{index}")
                node.setAttribute("id", identifier)
                meta = self.element(OPF, "meta", role)
                meta.setAttribute("refines", "#" + identifier)
                meta.setAttribute("property", "role")
                meta.setAttribute("scheme", "marc:relators")
                self.metadata.appendChild(meta)

    def write(self, metadata: EpubMetadata, cover=None, *, upgrade_epub3=False):
        existing = self.metadata_dict()
        primary_isbn = normalize_isbn((self.original_primary or "").removeprefix("urn:isbn:"))
        if metadata.isbn != existing["isbn"] and primary_isbn and metadata.isbn != primary_isbn:
            raise EpubError(
                "ISBN bu EPUB'un ana kimliği. Ana kimliği korumak için ISBN değiştirilemez."
            )
        for field, name in [
            ("title", "title"),
            ("publisher", "publisher"),
            ("language", "language"),
            ("published_date", "date"),
            ("description", "description"),
        ]:
            if getattr(metadata, field) != existing[field]:
                self.set_scalar(name, getattr(metadata, field))
        if metadata.authors != existing["authors"]:
            self.set_people("creator", metadata.authors, "aut")
        if metadata.translators != existing["translators"]:
            self.set_people("contributor", metadata.translators, "trl")
        if metadata.isbn != existing["isbn"]:
            for node in children(self.metadata, DC, "identifier"):
                if node is not self.primary and normalize_isbn(
                    text(node).removeprefix("urn:isbn:")
                ):
                    self.remove(node)
            if metadata.isbn:
                node = self.element(DC, "identifier", "urn:isbn:" + metadata.isbn)
                node.setAttribute("id", self.unique_id("bo-isbn"))
                self.metadata.appendChild(node)
        added = {}
        if cover is not None:
            if len(cover) > MAX_COVER:
                raise EpubError("Kapak 5 MiB sınırını aşıyor.")
            media, extension = image_type(cover)
            item = self.current_cover()
            if item is not None:
                target = archive_path(posixpath.dirname(self.opf_path), item.getAttribute("href"))
                # Keep its resource identity; update references if the format changes.
                if item.getAttribute("media-type") not in ("image/jpeg", "image/png"):
                    raise EpubError(
                        "Mevcut kapak türü güvenle değiştirilemiyor; mevcut kapağı koruyun."
                    )
                image_type(self.read(target, MAX_COVER))
                item.setAttribute("media-type", media)
            else:
                from app.epub_structure import cover_pages

                identifier = self.unique_id("bo-cover")
                pages = cover_pages(self)
                if pages:
                    target = pages[0]["image"]
                    image_type(self.read(target, MAX_COVER))
                else:
                    target = archive_path(posixpath.dirname(self.opf_path), identifier + extension)
                    while target in self.entries:
                        target = target.removesuffix(extension) + "x" + extension
                item = self.element(OPF, "item", "")
                item.setAttribute("id", identifier)
                item.setAttribute(
                    "href", posixpath.relpath(target, posixpath.dirname(self.opf_path) or ".")
                )
                item.setAttribute("media-type", media)
                if self.version.startswith("3."):
                    item.setAttribute("properties", "cover-image")
                else:
                    meta = self.element(OPF, "meta", "")
                    meta.setAttribute("name", "cover")
                    meta.setAttribute("content", identifier)
                    self.metadata.appendChild(meta)
                self.manifest.appendChild(item)
            valid_extensions = (".jpg", ".jpeg") if media == "image/jpeg" else (".png",)
            if posixpath.splitext(target)[1].lower() not in valid_extensions:
                from app.epub_structure import item_path, manifest_items, redirect_image

                previous_target = target
                target = posixpath.splitext(target)[0] + extension
                while target in self.entries or target in added:
                    target = target.removesuffix(extension) + "x" + extension
                previous_media, _ = image_type(self.read(previous_target, MAX_COVER))
                item.setAttribute(
                    "href", posixpath.relpath(target, posixpath.dirname(self.opf_path) or ".")
                )
                if not any(
                    item_path(self, other) == previous_target for other in manifest_items(self)
                ):
                    previous = self.element(OPF, "item", "")
                    previous.setAttribute("id", self.unique_id("bo-previous-cover"))
                    previous.setAttribute(
                        "href",
                        posixpath.relpath(previous_target, posixpath.dirname(self.opf_path) or "."),
                    )
                    previous.setAttribute("media-type", previous_media)
                    self.manifest.appendChild(previous)
                redirect_image(self, previous_target, target, added)
            if self.version.startswith("3."):
                properties = set(item.getAttribute("properties").split()) | {"cover-image"}
                item.setAttribute("properties", " ".join(sorted(properties)))
            else:
                cover_metas = [
                    node
                    for node in children(self.metadata, OPF, "meta")
                    if node.getAttribute("name") == "cover"
                ]
                if not cover_metas:
                    meta = self.element(OPF, "meta", "")
                    meta.setAttribute("name", "cover")
                    self.metadata.appendChild(meta)
                    cover_metas.append(meta)
                for meta in cover_metas:
                    meta.setAttribute("content", item.getAttribute("id"))
            added[target] = cover
            from app.epub_structure import synchronize_cover

            synchronize_cover(self, target, added)
        if upgrade_epub3:
            from app.epub_upgrade import upgrade_to_epub3

            upgrade_to_epub3(self, added)
        if self.version.startswith("3."):
            for node in children(self.metadata, OPF, "meta"):
                if node.getAttribute("property") == "dcterms:modified":
                    self.metadata.removeChild(node)
            modified = self.element(OPF, "meta", datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))
            modified.setAttribute("property", "dcterms:modified")
            self.metadata.appendChild(modified)
        added[self.opf_path] = self.document.toxml(encoding="utf-8")
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("mimetype", b"application/epub+zip", compress_type=zipfile.ZIP_STORED)
            for entry in self.archive.infolist():
                if entry.filename == "mimetype":
                    continue
                info = copy.copy(entry)
                if entry.filename in added:
                    archive.writestr(info, added.pop(entry.filename))
                else:
                    with self.archive.open(entry) as source, archive.open(info, "w") as target:
                        while chunk := source.read(65536):
                            target.write(chunk)
                if output.tell() > MAX_UPLOAD + MAX_COVER + MAX_XML:
                    raise EpubError("Çıktı boyutu sınırı aşıldı.")
            for name, data in added.items():
                archive.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
        result = output.getvalue()
        if len(result) > MAX_UPLOAD:
            raise EpubError("Yeni EPUB 25 MiB sınırını aşıyor; mevcut kapağı korumayı deneyin.")
        # Reopen and validate the result before offering a download.
        with EpubDocument(result) as check:
            expected_primary = text(self.primary) if self.primary is not None else None
            if check.original_primary != expected_primary:
                raise EpubError("EPUB ana kimliği korunamadı.")
        return result

    def close(self):
        if self.document is not None:
            self.document.unlink()
        if self.archive is not None:
            self.archive.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
