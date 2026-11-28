import hmac
import logging
import math
import time
from collections import deque
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app import __version__
from app.cache import MetadataCache
from app.config import Settings
from app.errors import ProviderError
from app.http import SourceHttpClient
from app.models import Book, SearchRequest, SearchResult
from app.service import ProviderService
from app.sources.base import SourceRegistry
from app.sources.binkitap import BinKitapSource
from app.sources.kitapyurdu import KitapyurduSource
from app.text import normalize_isbn, normalize_text
from app.web import install_web

logger = logging.getLogger("provider")


def create_app(settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None):
    config = settings or Settings()
    calls: deque[float] = deque()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        cache = MetadataCache(
            config.cache_max_bytes, config.search_cache_ttl, config.book_cache_ttl
        )
        async with httpx.AsyncClient(
            timeout=config.request_timeout_seconds,
            follow_redirects=False,
            trust_env=False,
            headers={
                "User-Agent": config.user_agent,
                "Accept-Language": "tr-TR,tr;q=0.9",
                "Accept": "text/html",
            },
            limits=httpx.Limits(max_connections=2, max_keepalive_connections=2),
            transport=transport,
        ) as client:
            source = KitapyurduSource(SourceHttpClient(config, client), cache)
            bin_source = BinKitapSource(
                SourceHttpClient(config, client, site="https://1000kitap.com"), cache
            )
            sources = [source, bin_source]
            app.state.service = ProviderService(config, SourceRegistry(sources), cache)
            app.state.cover_http = SourceHttpClient(
                config, client, site="https://img.kitapyurdu.com", images=True
            )
            app.state.web_services = {
                item.key: ProviderService(config, SourceRegistry([item]), cache) for item in sources
            }
            app.state.bin_cover_http = SourceHttpClient(
                config, client, site="https://1k-cdn.com", images=True
            )
            yield

    app = FastAPI(
        title="BookOrbit Turkish Metadata Provider", version=__version__, lifespan=lifespan
    )

    @app.exception_handler(ProviderError)
    async def provider_error(_request: Request, error: ProviderError):
        logger.warning("provider_error code=%s status=%d", error.code, error.status)
        headers = {"Retry-After": str(error.retry_after)} if error.retry_after else {}
        return JSONResponse({"error": error.code}, status_code=error.status, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request: Request, _error: RequestValidationError):
        return JSONResponse({"error": "invalid_request_parameters"}, status_code=400)

    async def authorize(authorization: str = Header(default="")):
        token = config.auth_token.get_secret_value()
        if token and not hmac.compare_digest(authorization.encode(), f"Bearer {token}".encode()):
            raise ProviderError("unauthorized", 401)
        now = time.monotonic()
        while calls and now - calls[0] >= 60:
            calls.popleft()
        if len(calls) >= config.api_requests_per_minute:
            raise ProviderError("provider_rate_limited", 429, math.ceil(60 - (now - calls[0])))
        calls.append(now)

    @app.get("/healthz")
    async def health():
        return {"status": "ok", "version": __version__}

    @app.get("/provider/info")
    async def info():
        return {
            "name": "BookOrbit Turkish Metadata Provider",
            "key": "turkish-metadata",
            "version": __version__,
            "color": "#00866a",
            "mediaTypes": ["book"],
            "lookup": True,
            "searchParams": ["isbn", "limit"],
            "supportedFields": [
                "title",
                "description",
                "cover",
                "authors",
                "publisher",
                "isbn",
                "publishedYear",
                "language",
                "pageCount",
            ],
            "idMaxLength": 32,
            "rateLimit": {
                "maxConcurrency": 1,
                "minIntervalMs": min(60000, math.ceil(config.source_interval_seconds * 1000)),
            },
            "authenticationRequired": bool(config.auth_token.get_secret_value()),
        }

    @app.get(
        "/search",
        response_model=SearchResult,
        response_model_exclude_none=True,
        dependencies=[Depends(authorize)],
    )
    async def search(
        request: Request,
        query: str = Query(default="", max_length=500),
        author: str = Query(default="", max_length=300),
        isbn: str = Query(default="", max_length=64),
        limit: int = Query(default=3, ge=1, le=50),
        mediaType: str = Query(default="book", pattern="^(book|audiobook|comic)$"),
    ):
        query, author, isbn = map(normalize_text, (query, author, isbn))
        normalized_isbn = normalize_isbn(isbn) or normalize_isbn(query)
        # Bad embedded identifiers must not prevent an otherwise useful text search.
        if isbn and not normalized_isbn and not (query or author):
            raise ProviderError("invalid_isbn", 400)
        if not (query or author or normalized_isbn):
            raise ProviderError("query_author_or_isbn_required", 400)
        if mediaType != "book":
            return SearchResult()
        params = SearchRequest(
            query=query, author=author, isbn=normalized_isbn, limit=min(limit, config.max_results)
        )
        return await request.app.state.service.search(params)

    @app.get(
        "/book/{provider_id}",
        response_model=Book,
        response_model_exclude_none=True,
        dependencies=[Depends(authorize)],
    )
    async def lookup(provider_id: str, request: Request):
        if len(provider_id) > 32:
            raise ProviderError("book_not_found", 404)
        return await request.app.state.service.lookup(provider_id)

    install_web(app, authorize)
    return app
