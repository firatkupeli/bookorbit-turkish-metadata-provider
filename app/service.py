import asyncio
import time

from app.cache import MetadataCache
from app.config import Settings
from app.errors import ProviderError, SourceNotFound
from app.models import Book, SearchRequest, SearchResult
from app.sources.base import SourceRegistry


def bounded_book(book: Book) -> Book:
    if len(book.model_dump_json(exclude_none=True).encode("utf-8")) > 2 * 1024 * 1024:
        raise ProviderError("book_response_too_large", 502)
    return book


class ProviderService:
    def __init__(self, settings: Settings, registry: SourceRegistry, cache: MetadataCache):
        self.settings = settings
        self.registry = registry
        self.cache = cache
        self._work_lock = asyncio.Lock()

    async def search(self, request: SearchRequest) -> SearchResult:
        key = request.model_dump_json()
        if cached := self.cache.searches.get(key):
            return SearchResult.model_validate_json(cached)
        if self._work_lock.locked():
            raise ProviderError("provider_busy", 429, 2)
        async with self._work_lock:
            deadline = time.monotonic() + self.settings.deadline_seconds
            result = SearchResult()
            first_error = None
            for source in self.registry.sources.values():
                try:
                    answer = await source.search(request, deadline)
                    result.matches.extend(answer.matches)
                    result.partial |= answer.partial
                except ProviderError as error:
                    first_error = error if error.status == 429 else first_error or error
                    result.partial = True
            if not result.matches and first_error:
                raise first_error
            result.matches = result.matches[: request.limit]
            # BookOrbit refuses JSON responses larger than 2 MiB.
            while len(result.model_dump_json(exclude_none=True).encode("utf-8")) > 2 * 1024 * 1024:
                result.matches.pop()
                result.partial = True
                if not result.matches:
                    raise ProviderError("search_response_too_large", 502)
            # A partial answer must not suppress a subsequent retry.
            if not result.partial:
                self.cache.put(self.cache.searches, key, result)
            return result

    async def lookup(self, provider_id: str) -> Book:
        resolved = self.registry.resolve(provider_id)
        if resolved is None:
            raise SourceNotFound()
        if cached := self.cache.books.get(provider_id):
            return bounded_book(Book.model_validate_json(cached))
        if self._work_lock.locked():
            raise ProviderError("provider_busy", 429, 2)
        async with self._work_lock:
            try:
                async with asyncio.timeout(self.settings.deadline_seconds):
                    book = await resolved[0].lookup(resolved[1])
            except TimeoutError:
                raise ProviderError("lookup_deadline_exceeded", 503) from None
        if book is None:
            raise SourceNotFound()
        return bounded_book(book)
