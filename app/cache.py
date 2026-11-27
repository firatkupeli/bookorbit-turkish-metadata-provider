from cachetools import TTLCache

from app.models import Book, SearchResult
from app.text import isbn13


class MetadataCache:
    """Bounded by serialized bytes; one event loop and one Uvicorn worker."""

    def __init__(self, max_bytes: int, search_ttl: int, book_ttl: int):
        self.searches: TTLCache = TTLCache(max_bytes // 2, search_ttl, getsizeof=len)
        self.books: TTLCache = TTLCache(max_bytes // 2, book_ttl, getsizeof=len)

    def find_isbn(self, isbn: str, source_key: str) -> Book | None:
        """Reuse exact editions already learned through a title search or lookup."""
        wanted = isbn13(isbn)
        for key in list(self.books):
            if encoded := self.books.get(key):
                book = Book.model_validate_json(encoded)
                if book.providerId.startswith(source_key + ":") and book.isbn13 == wanted:
                    return book
        return None

    @staticmethod
    def put(cache: TTLCache, key: str, value: Book | SearchResult) -> None:
        data = value.model_dump_json(exclude_none=True).encode("utf-8")
        if len(data) <= cache.maxsize:
            cache[key] = data
