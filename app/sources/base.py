from typing import Protocol

from app.models import Book, SearchRequest, SearchResult


class MetadataSource(Protocol):
    key: str

    async def search(self, request: SearchRequest, deadline: float) -> SearchResult: ...

    async def lookup(self, source_id: str) -> Book | None: ...


class SourceRegistry:
    def __init__(self, sources: list[MetadataSource]):
        self.sources = {source.key: source for source in sources}
        if len(self.sources) != len(sources):
            raise ValueError("Duplicate source key")

    def resolve(self, provider_id: str) -> tuple[MetadataSource, str] | None:
        key, separator, source_id = provider_id.partition(":")
        source = self.sources.get(key)
        return (source, source_id) if separator and source and source_id else None
