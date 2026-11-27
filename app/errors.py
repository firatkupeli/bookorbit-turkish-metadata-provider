class ProviderError(Exception):
    def __init__(self, code: str, status: int = 502, retry_after: int | None = None):
        self.code = code
        self.status = status
        self.retry_after = retry_after
        super().__init__(code)


class SourceNotFound(ProviderError):
    def __init__(self):
        super().__init__("book_not_found", 404)
