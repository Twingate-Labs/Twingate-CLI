"""Custom exception hierarchy for the Twingate CLI."""

from __future__ import annotations


class TwingateError(Exception):
    """Base exception for all tgcli errors."""


class TwingateAuthError(TwingateError):
    """Session not found or API token invalid."""


class TwingateAPIError(TwingateError):
    """GraphQL or HTTP-level API error."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class TwingateNotFoundError(TwingateAPIError):
    """Requested resource/entity was not found."""


class TwingateThrottleError(TwingateAPIError):
    """HTTP 429 – Twingate API rate limit reached.

    Attributes:
        retry_after: Seconds to wait before retrying, parsed from the
                     ``Retry-After`` response header (defaults to 60 s when
                     the header is absent or unparseable).
    """

    DEFAULT_RETRY_AFTER: int = 60

    def __init__(self, retry_after: int = DEFAULT_RETRY_AFTER) -> None:
        super().__init__(
            f"Rate limited by Twingate API — retry after {retry_after}s.",
            status_code=429,
        )
        self.retry_after = retry_after


class TwingateValidationError(TwingateError):
    """Input argument validation failed."""
