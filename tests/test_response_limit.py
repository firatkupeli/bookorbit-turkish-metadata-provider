import pytest

from app.cache import MetadataCache
from app.config import Settings
from app.errors import ProviderError
from app.models import Book, SearchRequest, SearchResult
from app.service import ProviderService
from app.sources.base import SourceRegistry


async def test_unicode_search_payload_stays_under_bookorbit_limit():
    class LargeSource:
        key = "large"

        async def search(self, request, deadline):
            return SearchResult(
                matches=[
                    Book(
                        providerId=f"large:{i}",
                        title="Türkçe",
                        url="https://example.org",
                        description="📚" * 50000,
                        authors=["ğ" * 1000] * 5,
                    )
                    for i in range(10)
                ]
            )

    cache = MetadataCache(16 * 1024 * 1024, 60, 60)
    service = ProviderService(Settings(_env_file=None), SourceRegistry([LargeSource()]), cache)
    result = await service.search(SearchRequest(query="Türkçe", limit=10))
    assert len(result.model_dump_json(exclude_none=True).encode("utf-8")) <= 2 * 1024 * 1024
    assert result.partial is True
    assert 0 < len(result.matches) < 10
    assert not cache.searches


async def test_oversized_cached_lookup_is_not_served():
    class LargeSource:
        key = "large"

    cache = MetadataCache(16 * 1024 * 1024, 60, 60)
    book = Book(
        providerId="large:1",
        title="Türkçe",
        url="https://example.org",
        authors=["ğ" * (2 * 1024 * 1024)],
    )
    cache.put(cache.books, book.providerId, book)
    service = ProviderService(Settings(_env_file=None), SourceRegistry([LargeSource()]), cache)
    with pytest.raises(ProviderError, match="book_response_too_large"):
        await service.lookup("large:1")
