"""Custom exception hierarchy.

Replaces the original code's pattern of catching bare `Exception` everywhere
and logging the message — which made it impossible to distinguish between
transient errors (worth retrying) and permanent failures (need human attention).
"""
from __future__ import annotations


class BotError(Exception):
    """Base class for all bot errors."""

    def __init__(self, message: str = "", *, transient: bool = False):
        super().__init__(message)
        self.transient = transient


class ConfigurationError(BotError):
    """Raised when configuration is invalid or incomplete."""


class BrowserError(BotError):
    """Browser/playwright-level errors (page crashed, navigation failed)."""


class WPPError(BotError):
    """WPP.js injection or call failures."""


class AIProviderError(BotError):
    """AI provider returned an error or timed out."""

    def __init__(self, message: str, *, provider: str = "", status_code: int = 0, transient: bool = True):
        super().__init__(message, transient=transient)
        self.provider = provider
        self.status_code = status_code


class RateLimitError(AIProviderError):
    """AI provider rate-limited the request (429)."""

    def __init__(self, message: str = "Rate limited", *, provider: str = "", retry_after: int = 65):
        super().__init__(message, provider=provider, status_code=429, transient=True)
        self.retry_after = retry_after


class SendError(BotError):
    """Failed to send a message via the browser."""


class MediaError(BotError):
    """Failed to download or process media."""


class STTError(MediaError):
    """Speech-to-text transcription failed."""


class QueueError(BotError):
    """Approval/retry queue operation failed."""


class NonReplyableError(BrowserError):
    """Chat cannot be replied to (announcement group, broadcast, newsletter).
    
    This is a permanent failure — retrying won't help.
    """

    def __init__(self, message: str = "Chat cannot be replied to"):
        super().__init__(message, transient=False)
