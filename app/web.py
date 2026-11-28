"""Same-origin UI and stateless upload/download endpoints."""

import asyncio
import hashlib
import zipfile
from pathlib import Path
from urllib.parse import quote, urlsplit
from xml.etree.ElementTree import ParseError
from xml.parsers.expat import ExpatError

from defusedxml.common import DefusedXmlException
from fastapi import Depends, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException

from app.epub import (
    MAX_COVER,
    MAX_UPLOAD,
    EpubDocument,
    EpubError,
    EpubMetadata,
    image_type,
    kepub_filename,
)
from app.epub_check import inspect_book
from app.errors import ProviderError
from app.images import image_info
from app.models import SearchRequest, SearchResult
from app.text import normalize_isbn, normalize_text

STATIC = Path(__file__).parent / "static"
MAX_OPTIONS = 256 * 1024


class ExportOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metadata: EpubMetadata
    cover_provider_id: str | None = Field(
        default=None, pattern=r"^(?:kitapyurdu|1000kitap):[1-9][0-9]{0,11}$"
    )
    upgrade_epub3: StrictBool = False
    expected_cover_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


async def upload(request, cover_only=False):
    if not request.headers.get("content-type", "").startswith("multipart/form-data;"):
        raise ProviderError("multipart_upload_required", 415)
    data = bytearray()
    try:
        async with asyncio.timeout(30):
            async for chunk in request.stream():
                limit = (
                    MAX_COVER + 4096 if cover_only else MAX_UPLOAD + MAX_COVER + MAX_OPTIONS + 8192
                )
                if len(data) + len(chunk) > limit:
                    raise ProviderError("upload_too_large", 413)
                data.extend(chunk)
    except TimeoutError:
        raise ProviderError("upload_timeout", 408) from None
    body = bytes(data)

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    bounded = Request(request.scope, receive)
    try:
        async with bounded.form(
            max_files=1 if cover_only else 2, max_fields=1, max_part_size=MAX_OPTIONS
        ) as form:
            items = list(form.multi_items())
            file = form.get("file")
            cover = form.get("cover")
            cover_content = None
            if cover is not None:
                if not isinstance(cover, UploadFile) or not (cover.filename or "").lower().endswith(
                    (".jpg", ".jpeg", ".png")
                ):
                    raise EpubError("Kapak için JPG veya PNG dosyası seçin.")
                cover_content = await cover.read(MAX_COVER + 1)
                if not cover_content or len(cover_content) > MAX_COVER:
                    raise EpubError("Kapak en fazla 5 MiB olabilir.")
            if cover_only:
                if len(items) != 1 or cover_content is None:
                    raise EpubError("Tek bir JPG veya PNG kapağı seçin.")
                return None, "", cover.filename, cover_content
            if (
                not isinstance(file, UploadFile)
                or not (file.filename or "").lower().endswith((".epub", ".kepub"))
                or len(items) != len(form)
                or any(k not in ("file", "options", "cover") for k, _ in items)
            ):
                raise EpubError("Tek bir .epub, .kepub.epub veya .kepub dosyası seçin.")
            content = await file.read(MAX_UPLOAD + 1)
            if len(content) > MAX_UPLOAD:
                raise ProviderError("upload_too_large", 413)
            options = form.get("options", "")
            if not isinstance(options, str) or len(options.encode()) > MAX_OPTIONS:
                raise EpubError("Metadata boyutu sınırı aşıldı.")
            return content, options, file.filename or "book.epub", cover_content
    except HTTPException:
        raise EpubError("Dosya yükleme biçimi geçersiz.") from None


def install_web(app, authorize):
    lock = asyncio.Lock()

    @app.middleware("http")
    async def headers(request, call_next):
        response = await call_next(request)
        if request.url.path == "/" or request.url.path.startswith(("/web/", "/assets/")):
            response.headers.update(
                {
                    "Content-Security-Policy": "default-src 'none'; "
                    "script-src 'self' 'wasm-unsafe-eval'; worker-src 'self'; "
                    "style-src 'self'; "
                    "img-src 'self' data: blob:; connect-src 'self'; font-src 'self'; "
                    "base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
                    "X-Content-Type-Options": "nosniff",
                    "Referrer-Policy": "no-referrer",
                    "Cache-Control": "no-store",
                    "X-Frame-Options": "DENY",
                }
            )
        return response

    @app.exception_handler(EpubError)
    async def epub_error(_request, error):
        return JSONResponse({"error": "invalid_epub", "message": str(error)}, status_code=422)

    async def web_guard(request: Request):
        origin = request.headers.get("origin")
        try:
            origin_host = urlsplit(origin).netloc if origin else None
        except ValueError:
            raise ProviderError("same_origin_required", 403) from None
        if (
            request.headers.get("x-bookorbit-web") != "1"
            or request.headers.get("sec-fetch-site") == "cross-site"
            or (origin and origin_host != request.url.netloc)
        ):
            raise ProviderError("same_origin_required", 403)

    async def cover_bytes(request, provider_id):
        key = provider_id.partition(":")[0]
        service = request.app.state.web_services.get(key)
        if service is None:
            raise ProviderError("book_not_found", 404)
        book = await service.lookup(provider_id)
        if not book.cover:
            raise ProviderError("cover_not_found", 404)
        client = (
            request.app.state.cover_http
            if key == "kitapyurdu"
            else request.app.state.bin_cover_http
        )
        data = await client.get(book.cover)
        await run_in_threadpool(image_info, data)
        return data

    dependencies = [Depends(authorize), Depends(web_guard)]

    @app.get(
        "/web/search",
        dependencies=dependencies,
        response_model=SearchResult,
        response_model_exclude_none=True,
        include_in_schema=False,
    )
    async def web_search(
        request: Request,
        source: str = Query("kitapyurdu", pattern="^(kitapyurdu|1000kitap|all)$"),
        query: str = Query("", max_length=500),
        author: str = Query("", max_length=300),
        isbn: str = Query("", max_length=64),
        limit: int = Query(5, ge=1, le=5),
    ):
        query, author, isbn = map(normalize_text, (query, author, isbn))
        normalized = normalize_isbn(isbn) or normalize_isbn(query)
        if isbn and not normalized and not (query or author):
            raise ProviderError("invalid_isbn", 400)
        if not (query or author or normalized):
            raise ProviderError("query_author_or_isbn_required", 400)
        params = SearchRequest(
            query=query,
            author=author,
            isbn=normalized,
            limit=min(limit, app.state.service.settings.max_results),
        )
        if source != "all":
            return await app.state.web_services[source].search(params)
        return await app.state.service.search(params)

    @app.post("/web/cover/inspect", dependencies=dependencies, include_in_schema=False)
    async def inspect_cover(request: Request):
        if lock.locked():
            raise ProviderError("editor_busy", 429, 2)
        async with lock:
            _, _, _, data = await upload(request, cover_only=True)
            return {
                "info": await run_in_threadpool(image_info, data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/assets/{filename}", include_in_schema=False)
    async def asset(filename: str):
        if filename not in ("app.js", "kepub.js", "style.css"):
            raise ProviderError("asset_not_found", 404)
        return FileResponse(STATIC / filename)

    @app.get("/assets/vendor/kepubify/{filename}", include_in_schema=False)
    async def kepub_asset(filename: str):
        allowed = {
            "index.js",
            "worker.js",
            "kepubify.worker.js",
            "chunk-3E3Y2FKS.js",
            "kepubify.wasm",
            "LICENSE",
            "VENDOR.json",
        }
        if filename not in allowed:
            raise ProviderError("asset_not_found", 404)
        media = "application/wasm" if filename.endswith(".wasm") else None
        return FileResponse(STATIC / "vendor" / "kepubify" / filename, media_type=media)

    @app.get("/web/cover/{provider_id}", dependencies=dependencies, include_in_schema=False)
    async def cover(provider_id: str, request: Request):
        data = await cover_bytes(request, provider_id)
        info = await run_in_threadpool(image_info, data)
        return Response(
            data,
            media_type=image_type(data)[0],
            headers={
                "X-Cover-SHA256": hashlib.sha256(data).hexdigest(),
                "X-Image-Width": str(info["width"]),
                "X-Image-Height": str(info["height"]),
                "X-Image-Bytes": str(info["bytes"]),
                "X-Image-Format": info["format"],
                "X-Image-Ratio": info["ratio"],
            },
        )

    async def process(request, writing=False, checking=False):
        if lock.locked():
            raise ProviderError("editor_busy", 429, 2)
        async with lock:
            content, raw_options, input_name, manual_cover = await upload(request)
            try:
                options = ExportOptions.model_validate_json(raw_options) if writing else None
                if manual_cover is not None and (not options or options.cover_provider_id):
                    raise EpubError("Tek bir kapak kaynağı seçin.")
                if manual_cover is not None:
                    await run_in_threadpool(image_info, manual_cover)
                cover = (
                    await cover_bytes(request, options.cover_provider_id)
                    if options and options.cover_provider_id
                    else None
                )
                cover = manual_cover if manual_cover is not None else cover
                if (
                    cover is not None
                    and options.expected_cover_sha256
                    and hashlib.sha256(cover).hexdigest() != options.expected_cover_sha256
                ):
                    raise EpubError(
                        "Kaynak kapağı değişmiş. Baskıyı yeniden seçip kapağı kontrol edin."
                    )

                def work():
                    with EpubDocument(content) as book:
                        if options:
                            return (
                                book.write(
                                    options.metadata, cover, upgrade_epub3=options.upgrade_epub3
                                ),
                                kepub_filename(input_name) or book.has_kepub_markup(),
                            )
                        cover_item = book.current_cover()
                        try:
                            info = image_info(book.cover_data()) if book.cover_data() else None
                        except EpubError:
                            info = None
                        result = {
                            "metadata": book.metadata_dict(),
                            "cover": book.preview() if info else None,
                            "cover_info": info,
                            "has_cover": cover_item is not None,
                            "can_replace_cover": cover_item is None
                            or cover_item.getAttribute("media-type") in ("image/jpeg", "image/png"),
                            "epub_version": book.version,
                            "input_format": "kepub"
                            if kepub_filename(input_name) or book.has_kepub_markup()
                            else "epub",
                            "kepub_markup": book.has_kepub_markup(),
                        }
                        if checking:
                            result["report"] = inspect_book(book)
                        return result

                result = await run_in_threadpool(work)
            except ValidationError:
                raise EpubError(
                    "Metadata geçersiz. Başlığı, ISBN, tarih ve dil kodunu kontrol edin."
                ) from None
            except (
                zipfile.BadZipFile,
                zipfile.LargeZipFile,
                DefusedXmlException,
                ExpatError,
                ParseError,
                KeyError,
                UnicodeError,
                RuntimeError,
                OSError,
            ):
                raise EpubError("EPUB okunamadı veya desteklenmeyen bir yapı içeriyor.") from None
        if writing:
            result, is_kepub = result
            title = options.metadata.title
            filename = (
                "".join(c for c in title if c.isalnum() or c in " -_").strip()[:100] or "kitap"
            )
            suffix = ".kepub.epub" if is_kepub else ".epub"
            download_name = quote(filename + "-metadata" + suffix)
            return Response(
                result,
                media_type="application/epub+zip",
                headers={
                    "Content-Disposition": f"attachment; filename=book-metadata{suffix}; "
                    f"filename*=UTF-8''{download_name}"
                },
            )
        return JSONResponse(result)

    @app.post("/web/epub/read", dependencies=dependencies, include_in_schema=False)
    async def read(request: Request):
        return await process(request)

    @app.post("/web/epub/check", dependencies=dependencies, include_in_schema=False)
    async def check(request: Request):
        return await process(request, checking=True)

    @app.post("/web/epub/export", dependencies=dependencies, include_in_schema=False)
    async def export(request: Request):
        return await process(request, writing=True)
