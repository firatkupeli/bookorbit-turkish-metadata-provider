"""Experimental public HTML adapter. No account, private API or access bypass."""

import asyncio
import json
import re
import time
from urllib.parse import urlencode, urljoin, urlsplit

from bs4 import BeautifulSoup

from app.errors import ProviderError, SourceNotFound
from app.models import Book, SearchResult
from app.sources.kitapyurdu import request_matches
from app.text import isbn13, normalize_isbn, normalize_text, plain_text

SITE = "https://1000kitap.com"
BOOK_PATH = re.compile(r"^/kitap/(?:[^/?]+--)?([1-9][0-9]{0,11})$")


def clean_url(value):
    if not isinstance(value, str):
        return None
    try:
        url = urlsplit(urljoin(SITE, value))
    except ValueError:
        return None
    return (
        SITE + url.path
        if url.scheme == "https" and url.netloc == "1000kitap.com" and BOOK_PATH.fullmatch(url.path)
        else None
    )


def candidates(html):
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("main.govde-arama")
    if main is None:
        raise ProviderError("source_search_markup_changed")
    result = list(
        dict.fromkeys(
            url for node in main.select("a[href]") if (url := clean_url(node.get("href", "")))
        )
    )
    if not result and "Gösterilecek içerik bulunamadı" not in main.get_text(" "):
        raise ProviderError("source_search_markup_changed")
    return result


def _parse_book(html, source_id):
    soup = BeautifulSoup(html, "html.parser")
    records = []
    for node in soup.select('script[type="application/ld+json"]'):
        try:
            value = json.loads(node.get_text())
            values = value if isinstance(value, list) else [value]
            for entry in values:
                records.extend(entry.get("@graph", [entry]) if isinstance(entry, dict) else [])
        except ValueError:
            continue
    data = next(
        (
            d
            for d in records
            if isinstance(d, dict)
            and "Book"
            in ([d.get("@type")] if isinstance(d.get("@type"), str) else d.get("@type") or [])
        ),
        None,
    )
    if not data:
        raise ProviderError("source_book_markup_changed")
    title = data.get("name")
    if not isinstance(title, str) or not title.strip() or len(title) > 1000:
        raise ProviderError("source_book_markup_changed")
    url = clean_url(data.get("url") or data.get("@id") or "")
    if not url or BOOK_PATH.fullmatch(urlsplit(url).path)[1] != source_id:
        raise ProviderError("source_book_identity_mismatch")

    def names(value):
        values = value if isinstance(value, list) else [value]
        return list(
            dict.fromkeys(
                normalize_text(n)
                for v in values
                if isinstance(n := v.get("name") if isinstance(v, dict) else v, str) and n.strip()
            )
        )

    isbn = normalize_isbn(str(data.get("isbn", "")))
    raw_cover = data.get("image")
    raw_cover = raw_cover.get("url") if isinstance(raw_cover, dict) else raw_cover
    try:
        cover = urlsplit(raw_cover) if isinstance(raw_cover, str) else None
    except ValueError:
        cover = None
    date = str(data.get("datePublished", ""))
    date = date[:10] if re.fullmatch(r"\d{4}(?:-\d{2}(?:-\d{2})?)?", date[:10]) else None
    language = data.get("inLanguage", "")
    language = language if isinstance(language, str) else ""
    language = {
        "Türkçe": "tr",
        "İngilizce": "en",
        "Almanca": "de",
        "Fransızca": "fr",
        "Azerbaycanca": "az",
    }.get(language, language if re.fullmatch(r"[a-z]{2,3}(?:-[A-Z]{2})?", language) else None)
    pages = data.get("numberOfPages")
    pages = int(pages) if str(pages).isdigit() and 0 < int(pages) < 100000 else None
    publishers = names(data.get("publisher"))
    return Book(
        providerId="1000kitap:" + source_id,
        title=normalize_text(title),
        authors=names(data.get("author")),
        translators=names(data.get("translator")),
        description=plain_text(data.get("description") or "")[:50000] or None,
        publisher=publishers[0] if publishers else None,
        languageCode=language,
        pages=pages,
        publishedDate=date,
        publishedYear=date[:4] if date else None,
        isbn13=isbn13(isbn) if isbn else None,
        isbn10=isbn if isbn and len(isbn) == 10 else None,
        cover=raw_cover
        if cover and cover.scheme == "https" and cover.netloc == "1k-cdn.com" and not cover.username
        else None,
        url=url,
    )


def parse_book(html, source_id):
    try:
        return _parse_book(html, source_id)
    except ProviderError:
        raise
    except (ValueError, TypeError, KeyError):
        raise ProviderError("source_book_markup_changed") from None


class BinKitapSource:
    key = "1000kitap"

    def __init__(self, http, cache):
        self.http, self.cache = http, cache

    async def lookup(self, source_id):
        if not re.fullmatch(r"[1-9][0-9]{0,11}", source_id):
            raise SourceNotFound()
        provider_id = self.key + ":" + source_id
        if value := self.cache.books.get(provider_id):
            return Book.model_validate_json(value)
        book = parse_book(await self.http.get(SITE + "/kitap/" + source_id), source_id)
        self.cache.put(self.cache.books, provider_id, book)
        return book

    async def search(self, request, deadline):
        query = request.query or request.isbn or request.author
        url = SITE + "/ara?" + urlencode({"q": query[:100], "bolum": "kitaplar"})
        result = SearchResult()
        try:
            async with asyncio.timeout(max(0.001, deadline - time.monotonic())):
                try:
                    urls = candidates(await self.http.get(url))
                except SourceNotFound:
                    raise ProviderError("source_search_unavailable", 502) from None
                for url in urls[:5]:
                    try:
                        book = await self.lookup(BOOK_PATH.fullmatch(urlsplit(url).path)[1])
                    except SourceNotFound:
                        continue
                    if request_matches(book, request):
                        result.matches.append(book)
                    if len(result.matches) >= request.limit:
                        break
                result.partial = len(urls) > 5 and len(result.matches) < request.limit
        except TimeoutError:
            if not result.matches:
                raise ProviderError("search_deadline_exceeded", 503) from None
            result.partial = True
        except ProviderError:
            if not result.matches:
                raise
            result.partial = True
        return result
