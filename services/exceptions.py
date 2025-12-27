class UrlExpiredError(Exception):
    """Raised when a short URL has expired."""


class ShortCodeNotFoundError(Exception):
    """Raised when a short code does not exist."""
