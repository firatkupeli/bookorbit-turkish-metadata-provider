import asyncio
import json
import re
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup
from pydantic import ValidationError

from app.cache import MetadataCache
from app.errors import ProviderError, SourceNotFound
from app.http import SITE, SourceHttpClient, validate_url
from app.models import Book, SearchRequest, SearchResult
from app.text import (
    author_matches,
    fold,
    isbn13,
    match_title,
    normalize_isbn,
    normalize_text,
    plain_text,
)

BOOK_PATH = re.compile(r"^/kitap/[^/]+/([1-9][0-9]{0,11})\.html$")
SOURCE_ID = re.compile(r"^[1-9][0-9]{0,11}$")


def book_url(source_id: str) -> str:
    # Public HTML route verified against product 51855, not a claimed Kitapyurdu API.
    return SITE + "/index.php?" + urlencode({"route": "product/product", "product_id": source_id})


def clean_book_url(value: str) -> str | None:
    parsed = urlsplit(urljoin(SITE, value))
    url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    try:
        validate_url(url)
    except ProviderError:
        return None
    return url if BOOK_PATH.fullmatch(parsed.path) else None


def image_url(value: str | None) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    url = urljoin(SITE, value)
    parsed = urlsplit(url)
    # Only URLs actually present on the source page. No guessed image resizing endpoints.
    if parsed.scheme == "https" and parsed.netloc == "img.kitapyurdu.com":
        return url
    return None


@dataclass(frozen=True)
class SearchCandidate:
    url: str
    title: str
    authors: tuple[str, ...]


def parse_candidates(html: str) -> list[SearchCandidate]:
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one(".ky-products-container, .product-list")
    if container is None:
        raise ProviderError("source_search_markup_changed")
    candidates = []
    seen = set()
    for product in container.select(".ky-product, .product-cr"):
        url = next(
            (
                url
                for a in product.select("a[href]")
                if (url := clean_book_url(str(a.get("href", ""))))
            ),
            None,
        )
        if not url or url in seen:
            continue
        seen.add(url)
        title = product.select_one(".ky-product-title, .name a")
        authors = product.select(".ky-product-author a, .author a")
        candidates.append(
            SearchCandidate(
                url=url,
                title=normalize_text(title.get_text(" ")) if title else "",
                authors=tuple(dict.fromkeys(normalize_text(a.get_text(" ")) for a in authors)),
            )
        )
    if not candidates:
        # Do not confuse a challenge, redesigned page, or unrelated products with 'not found'.
        empty = container.select_one(".empty-products-container")
        if empty is None and container.select_one(".ky-product, .product-cr") is None:
            raise ProviderError("source_search_markup_changed")
    return candidates


def parse_search(html: str) -> list[str]:
    return [candidate.url for candidate in parse_candidates(html)]


def request_matches(book: Book, request: SearchRequest) -> bool:
    if request.isbn:
        return book.isbn13 == isbn13(request.isbn)
    return not request.author or author_matches(request.author, book.authors)


def rank_candidates(
    candidates: list[SearchCandidate], request: SearchRequest
) -> list[SearchCandidate]:
    if request.author and not request.isbn:
        candidates = [
            candidate
            for candidate in candidates
            if not candidate.authors or author_matches(request.author, candidate.authors)
        ]
    return sorted(
        candidates,
        key=lambda candidate: (
            bool(request.author and author_matches(request.author, candidate.authors)),
            SequenceMatcher(None, match_title(request.query), match_title(candidate.title)).ratio()
            if request.query
            else 0,
        ),
        reverse=True,
    )


def _nodes(value):
    if isinstance(value, list):
        for item in value:
            yield from _nodes(item)
    elif isinstance(value, dict):
        yield value
        if "@graph" in value:
            yield from _nodes(value["@graph"])


def _names(value) -> list[str]:
    values = value if isinstance(value, list) else [value]
    names = []
    for item in values:
        name = item.get("name") if isinstance(item, dict) else item
        if isinstance(name, str) and (name := normalize_text(name)) and name not in names:
            names.append(name)
    return names


def _attributes(soup: BeautifulSoup) -> dict:
    attributes = {}
    for row in soup.select(".ky-pd-attributes__item"):
        label = row.select_one(".ky-pd-attributes__label")
        value = row.select_one(".ky-pd-attributes__value")
        if label and value:
            attributes[fold(label.get_text()).rstrip(":")] = value
    # Older Kitapyurdu product pages use a table for the same attributes.
    for row in soup.select(".attributes tr, .attribute tr"):
        cells = row.find_all("td")
        if len(cells) >= 2:
            attributes[fold(cells[0].get_text()).rstrip(":")] = cells[-1]
    return attributes


def parse_book(html: str, source_id: str) -> Book:
    soup = BeautifulSoup(html, "html.parser")
    data = None
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            nodes = _nodes(json.loads(script.get_text()))
            for node in nodes:
                types = node.get("@type", [])
                types = [types] if isinstance(types, str) else types
                if "Book" in types:
                    data = node
                    break
        except (ValueError, TypeError):
            continue
        if data:
            break
    attrs = _attributes(soup)
    title_tag = soup.select_one("h1.ky-pd-title, h1.pr_header__heading")
    if data is None:
        # Require book-specific evidence before using the HTML fallback.
        canonical = soup.select_one('link[rel="canonical"]')
        if not title_tag or "isbn" not in attrs or not canonical:
            raise ProviderError("source_book_markup_changed")
        data = {"name": title_tag.get_text(), "url": canonical.get("href")}
    url = clean_book_url(str(data.get("url", "")))
    if not url or BOOK_PATH.fullmatch(urlsplit(url).path).group(1) != source_id:
        raise ProviderError("source_book_identity_mismatch")

    def attr(label: str) -> str:
        tag = attrs.get(label)
        return normalize_text(tag.get_text(" ")) if tag else ""

    authors = _names(data.get("author"))
    if not authors:
        authors = [
            normalize_text(a.get_text())
            for a in soup.select('a[href*="/yazar/"]')
            if a.find_parent(class_="ky-pd-heading__authors")
        ]
    translators = _names(data.get("translator"))
    translator_tag = attrs.get("cevirmen")
    if translator_tag:
        translator_links = translator_tag.select("a")
        translators = [normalize_text(a.get_text()) for a in translator_links] or [attr("cevirmen")]
    publisher = _names(data.get("publisher"))
    if not publisher:
        tag = soup.select_one('.ky-pd-heading__authors a[href*="/yayinevi/"]')
        publisher = [normalize_text(tag.get_text())] if tag else []
    raw_isbn = attr("isbn") or str(data.get("isbn", ""))
    isbn = normalize_isbn(raw_isbn)
    raw_date = attr("yayin tarihi") or str(data.get("datePublished", ""))
    published = None
    year = None
    for pattern in ("%d.%m.%Y", "%Y-%m-%d", "%Y"):
        try:
            parsed_date = datetime.strptime(raw_date, pattern)
            year = str(parsed_date.year).zfill(4)
            published = parsed_date.date().isoformat() if pattern != "%Y" else None
            break
        except ValueError:
            continue
    page_value = str(data.get("numberOfPages") or attr("sayfa sayisi"))
    pages = int(page_value) if page_value.isascii() and page_value.isdigit() else None
    lang = str(data.get("inLanguage") or attr("dil"))
    language = {"turkce": "tr", "ingilizce": "en", "almanca": "de", "fransizca": "fr"}.get(
        fold(lang)
    )
    if not language and re.fullmatch(r"[a-z]{2,3}(?:-[A-Z]{2})?", lang):
        language = lang
    cover_link = soup.select_one("a.js-jbox-book-cover[href]")
    image = data.get("image")
    if isinstance(image, list):
        image = image[0] if image else None
    if isinstance(image, dict):
        image = image.get("url")
    cover = image_url(str(cover_link["href"]) if cover_link else image)
    description = data.get("description")
    if not description:
        desc_tag = soup.select_one(".ky-pd-description, .info__text")
        description = str(desc_tag) if desc_tag else None
    try:
        return Book(
            providerId=f"kitapyurdu:{source_id}",
            title=normalize_text(
                str(data.get("name") or (title_tag.get_text() if title_tag else ""))
            ),
            authors=authors,
            translators=translators,
            description=plain_text(description) if isinstance(description, str) else None,
            cover=cover,
            publisher=publisher[0] if publisher else None,
            publishedDate=published,
            publishedYear=year,
            pages=pages if pages and pages > 0 else None,
            languageCode=language,
            isbn13=isbn13(isbn) if isbn else None,
            isbn10=isbn if isbn and len(isbn) == 10 else None,
            url=url,
        )
    except ValidationError:
        raise ProviderError("source_book_invalid_data") from None


class KitapyurduSource:
    key = "kitapyurdu"

    def __init__(self, http: SourceHttpClient, cache: MetadataCache):
        self.http = http
        self.cache = cache

    async def lookup(self, source_id: str) -> Book | None:
        if not SOURCE_ID.fullmatch(source_id):
            return None
        cache_key = f"{self.key}:{source_id}"
        if cached := self.cache.books.get(cache_key):
            return Book.model_validate_json(cached)
        try:
            html = await self.http.get(book_url(source_id))
        except SourceNotFound:
            return None
        book = parse_book(html, source_id)
        self.cache.put(self.cache.books, cache_key, book)
        return book

    async def search(self, request: SearchRequest, deadline: float) -> SearchResult:
        if request.isbn and (cached := self.cache.find_isbn(request.isbn, self.key)):
            return SearchResult(matches=[cached])
        matches: list[Book] = []
        partial = False
        first_error: ProviderError | None = None
        terms = [request.isbn] if request.isbn else []
        title = request.query if not normalize_isbn(request.query) else ""
        if title and request.author:
            terms.append(f"{title} {request.author}")
        if title:
            terms.append(title)
        elif request.author and not terms:
            terms.append(request.author)
        terms = list(dict.fromkeys(terms))
        seen = set()
        fetched = 0
        detail_budget = self.http.settings.max_results
        try:
            async with asyncio.timeout_at(deadline):
                for term in terms:
                    try:
                        html = await self.http.get(
                            SITE
                            + "/index.php?"
                            + urlencode({"route": "product/list", "filter_name": term})
                        )
                    except SourceNotFound:
                        raise ProviderError("source_search_unavailable", 502) from None
                    candidates = rank_candidates(parse_candidates(html), request)
                    for candidate in candidates:
                        if candidate.url in seen:
                            continue
                        if fetched >= detail_budget:
                            break
                        seen.add(candidate.url)
                        fetched += 1
                        source_id = BOOK_PATH.fullmatch(urlsplit(candidate.url).path).group(1)
                        try:
                            book = await self.lookup(source_id)
                        except ProviderError as error:
                            first_error = first_error or error
                            partial = True
                            if error.status == 429:
                                raise
                            continue
                        if book is not None and request_matches(book, request):
                            matches.append(book)
                            if len(matches) >= request.limit:
                                break
                    if matches or fetched >= detail_budget:
                        break
        except ProviderError as error:
            first_error = first_error or error
            partial = True
        except TimeoutError:
            partial = True
            first_error = first_error or ProviderError("search_deadline_exceeded", 503)
        if not matches and first_error:
            raise first_error
        matches.sort(
            key=lambda book: (
                bool(request.author and author_matches(request.author, book.authors)),
                SequenceMatcher(None, match_title(title), match_title(book.title)).ratio()
                if title
                else 0,
            ),
            reverse=True,
        )
        return SearchResult(matches=matches[: request.limit], partial=partial)
