import asyncio
import json
import time
from itertools import zip_longest

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
        # Single-source web searches and combined API searches share book records,
        # but must never reuse one another's search results.
        key = json.dumps([list(self.registry.sources), request.model_dump()], ensure_ascii=False)
        if cached := self.cache.searches.get(key):
            return SearchResult.model_validate_json(cached)
        if self._work_lock.locked():
            raise ProviderError("provider_busy", 429, 2)
        async with self._work_lock:
            deadline = time.monotonic() + self.settings.deadline_seconds
            result = SearchResult()
            first_error = None

            async def search_source(source):
                try:
                    # Each adapter owns its deadline so it can return matches
                    # collected before timing out, rather than lose that progress
                    # to an outer cancellation at the same instant.
                    return await source.search(request, deadline)
                except TimeoutError:
                    return ProviderError("search_deadline_exceeded", 503)
                except ProviderError as error:
                    return error

            answers = await asyncio.gather(
                *(search_source(source) for source in self.registry.sources.values())
            )
            batches = []
            for answer in answers:
                if isinstance(answer, ProviderError):
                    first_error = answer if answer.status == 429 else first_error or answer
                    result.partial = True
                else:
                    batches.append(answer.matches)
                    result.partial |= answer.partial
            # Preserve each source's ranking and give both sources room in the
            # limited BookOrbit result list. Cross-source editions keep their IDs.
            seen = set()
            for row in zip_longest(*batches):
                for book in row:
                    if book is not None and book.providerId not in seen:
                        result.matches.append(book)
                        seen.add(book.providerId)
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
