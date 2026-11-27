from typing import Literal

from pydantic import BaseModel, Field


class Book(BaseModel):
    """Wire names are the BookOrbit contract, not its field-rule names."""

    providerId: str = Field(min_length=1, max_length=512)
    title: str = Field(min_length=1, max_length=1000)
    mediaType: Literal["book"] = "book"
    authors: list[str] = Field(default_factory=list)
    description: str | None = Field(default=None, max_length=50000)
    cover: str | None = None
    publisher: str | None = None
    publishedYear: str | None = Field(default=None, pattern=r"^\d{4}$")
    publishedDate: str | None = None
    pages: int | None = Field(default=None, gt=0)
    languageCode: str | None = None
    isbn13: str | None = Field(default=None, pattern=r"^\d{13}$")
    isbn10: str | None = Field(default=None, pattern=r"^\d{9}[\dX]$")
    url: str
    # Extension: BookOrbit currently ignores this field.
    translators: list[str] = Field(default_factory=list)


class SearchResult(BaseModel):
    matches: list[Book] = Field(default_factory=list)
    partial: bool = False


class SearchRequest(BaseModel):
    query: str = ""
    author: str = ""
    isbn: str | None = None
    limit: int = 3
