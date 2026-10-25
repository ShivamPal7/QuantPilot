"""Internal exchange error taxonomy and response mapping.

Per Section 6.3 of agent.md:
Each error maps to a defined system behavior (retry, halt, alert, reject intent).
"""

from __future__ import annotations

from enum import Enum


class ErrorRecoveryAction(str, Enum):
    RETRY_WITH_BACKOFF = "RETRY_WITH_BACKOFF"
    HALT_ENGINE = "HALT_ENGINE"
    ALERT_OPERATOR = "ALERT_OPERATOR"
    REJECT_INTENT = "REJECT_INTENT"


class ExchangeError(Exception):
    """Base exception for all exchange interactions."""

    def __init__(self, message: str, action: ErrorRecoveryAction = ErrorRecoveryAction.ALERT_OPERATOR) -> None:
        super().__init__(message)
        self.action = action


class InvalidKeyError(ExchangeError):
    def __init__(self, message: str = "Invalid API key or wrong environment") -> None:
        super().__init__(message, action=ErrorRecoveryAction.HALT_ENGINE)


class SignatureExpiredError(ExchangeError):
    def __init__(self, message: str = "Request signature expired (>5s)") -> None:
        super().__init__(message, action=ErrorRecoveryAction.RETRY_WITH_BACKOFF)


class SignatureMismatchError(ExchangeError):
    def __init__(self, message: str = "HMAC signature mismatch") -> None:
        super().__init__(message, action=ErrorRecoveryAction.HALT_ENGINE)


class IPNotWhitelistedError(ExchangeError):
    def __init__(self, message: str = "Origin IP is not whitelisted on this API key") -> None:
        super().__init__(message, action=ErrorRecoveryAction.HALT_ENGINE)


class RateLimitExceededError(ExchangeError):
    def __init__(self, retry_after_ms: int = 1000, message: str = "HTTP 429: Rate limit exceeded") -> None:
        super().__init__(message, action=ErrorRecoveryAction.RETRY_WITH_BACKOFF)
        self.retry_after_ms = retry_after_ms


class InsufficientMarginError(ExchangeError):
    def __init__(self, message: str = "Insufficient margin to open order") -> None:
        super().__init__(message, action=ErrorRecoveryAction.REJECT_INTENT)


class ProductNotOperationalError(ExchangeError):
    def __init__(self, message: str = "Target instrument is not in operational status") -> None:
        super().__init__(message, action=ErrorRecoveryAction.REJECT_INTENT)


class CDNForbiddenError(ExchangeError):
    def __init__(self, message: str = "Request forbidden by CDN (missing User-Agent)") -> None:
        super().__init__(message, action=ErrorRecoveryAction.HALT_ENGINE)
