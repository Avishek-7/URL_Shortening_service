class UrlExpiredError(Exception):
    """Raised when a short URL has expired."""


class ShortCodeNotFoundError(Exception):
    """Raised when a short code does not exist."""


class AliasAlreadyInUseError(Exception):
    """Raised when a requested custom alias is already taken."""
