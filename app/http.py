import asyncio
import math
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from app.config import Settings
from app.errors import ProviderError, SourceNotFound

SITE = "https://www.kitapyurdu.com"
MAX_BODY = 2 * 1024 * 1024


def retry_seconds(value: str | None) -> int:
    try:
        seconds = int(value or "")
    except ValueError:
        try:
            stamp = parsedate_to_datetime(value or "")
            seconds = math.ceil((stamp - datetime.now(UTC)).total_seconds())
        except (ValueError, TypeError, OverflowError):
            seconds = 60
    return max(1, min(seconds, 86400))


def validate_url(url: str) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "www.kitapyurdu.com"
        or parsed.username
        or parsed.fragment
    ):
        raise ProviderError("unsafe_source_url")


class SourceHttpClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self.settings = settings
        self.client = client
        self._lock = asyncio.Lock()
        self._robots_lock = asyncio.Lock()
        self._policy: RobotFileParser | None = None
        self._robots_expires = 0.0
        self._next_start = 0.0
        self._paused_until = 0.0
        self._crawl_delay = 0.0

    def _check_pause(self) -> None:
        remaining = self._paused_until - time.monotonic()
        if remaining > 0:
            raise ProviderError("source_rate_limited", 429, math.ceil(remaining))

    async def _raw(self, url: str, robots: bool = False) -> str:
        for _ in range(4):
            validate_url(url)
            if not robots and self._policy is not None:
                if not self._policy.can_fetch(self.settings.user_agent, url):
                    raise ProviderError("source_robots_disallowed", 503)
            async with self._lock:
                self._check_pause()
                # Windows event loops can wake a sleep before its requested deadline.
                while (remaining := self._next_start - time.monotonic()) > 0:  # noqa: ASYNC110
                    await asyncio.sleep(remaining)
                self._check_pause()
                self._next_start = time.monotonic() + max(
                    self.settings.source_interval_seconds, self._crawl_delay
                )
                try:
                    async with self.client.stream("GET", url) as response:
                        if response.status_code == 429:
                            delay = retry_seconds(response.headers.get("Retry-After"))
                            self._paused_until = time.monotonic() + delay
                            raise ProviderError("source_rate_limited", 429, delay)
                        if response.is_redirect:
                            target = response.headers.get("location")
                            if not target:
                                raise ProviderError("invalid_source_redirect")
                            url = urljoin(url, target)
                            continue
                        if response.status_code == 404 and not robots:
                            raise SourceNotFound()
                        if response.status_code != 200:
                            code = (
                                "source_access_refused"
                                if response.status_code in (401, 403)
                                else "source_http_error"
                            )
                            raise ProviderError(code)
                        if not robots and "text/html" not in response.headers.get(
                            "content-type", ""
                        ):
                            raise ProviderError("source_invalid_content_type")
                        body = bytearray()
                        async for chunk in response.aiter_bytes():
                            if len(body) + len(chunk) > MAX_BODY:
                                raise ProviderError("source_response_too_large")
                            body.extend(chunk)
                        return body.decode("utf-8", errors="replace")
                except httpx.TimeoutException:
                    raise ProviderError("source_timeout", 503) from None
                except httpx.HTTPError:
                    raise ProviderError("source_network_error", 502) from None
        raise ProviderError("too_many_source_redirects")

    async def _ensure_robots(self) -> None:
        async with self._robots_lock:
            if self._policy is not None and time.monotonic() < self._robots_expires:
                return
            try:
                text = await self._raw(SITE + "/robots.txt", robots=True)
            except ProviderError as error:
                if error.status == 429:
                    raise
                raise ProviderError("source_robots_unavailable", 503) from None
            if "user-agent:" not in text.lower():
                raise ProviderError("source_robots_invalid", 503)
            policy = RobotFileParser(SITE + "/robots.txt")
            policy.parse(text.splitlines())
            self._policy = policy
            self._robots_expires = time.monotonic() + 3600
            self._crawl_delay = float(policy.crawl_delay(self.settings.user_agent) or 0)
            rate = policy.request_rate(self.settings.user_agent)
            if rate and rate.requests:
                self._crawl_delay = max(self._crawl_delay, rate.seconds / rate.requests)

    async def get(self, url: str) -> str:
        validate_url(url)
        self._check_pause()
        await self._ensure_robots()
        return await self._raw(url)
