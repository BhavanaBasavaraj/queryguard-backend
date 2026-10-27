"""Classify provider exceptions into a small, stable vocabulary.

The values here are written to LogWatch's llm_calls.error_type column,
so they are deliberately few and provider-neutral. The important
distinction is transient (worth retrying) versus permanent (retrying
cannot help, a human must change configuration).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMError(Exception):
    """A provider failure with enough structure to act on and to record."""

    error_type: str
    provider: str
    model: str
    status_code: int | None
    message: str

    @property
    def is_transient(self) -> bool:
        return self.error_type in {"timeout", "rate_limited", "upstream_5xx"}

    def __str__(self) -> str:
        return f"{self.provider}/{self.model}: {self.error_type}: {self.message}"


# Permanent: retrying cannot succeed.
MODEL_GONE = "model_gone"            # retired, end-of-life, or no entitlement
AUTH_FAILED = "auth_failed"          # bad or revoked key
BAD_REQUEST = "bad_request"          # malformed prompt or parameters

# Transient: retrying may succeed.
TIMEOUT = "timeout"
RATE_LIMITED = "rate_limited"
UPSTREAM_5XX = "upstream_5xx"

UNKNOWN = "unknown"


def classify(exc: Exception, provider: str, model: str) -> LLMError:
    """Map an SDK exception onto the vocabulary above.

    Both SDKs expose an HTTP status on their error types, so status is
    the primary signal; the message text is only a tie-breaker for the
    two different meanings of 404.
    """
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if not isinstance(status, int):
        status = None

    text = str(exc)
    lowered = text.lower()

    if isinstance(exc, TimeoutError) or "timeout" in type(exc).__name__.lower():
        error_type = TIMEOUT
    elif status == 429:
        error_type = RATE_LIMITED
    elif status in (401, 403):
        error_type = AUTH_FAILED
    elif status == 410:
        error_type = MODEL_GONE
    elif status == 404:
        # 404 means either "no such model" or "your account may not invoke
        # this one". Both are permanent and both need a config change.
        error_type = MODEL_GONE
    elif status == 400:
        error_type = BAD_REQUEST
    elif status is not None and 500 <= status < 600:
        error_type = UPSTREAM_5XX
    elif "deadline" in lowered or "timed out" in lowered:
        error_type = TIMEOUT
    elif "quota" in lowered or "rate limit" in lowered:
        error_type = RATE_LIMITED
    elif "not found" in lowered or "end of life" in lowered:
        error_type = MODEL_GONE
    else:
        error_type = UNKNOWN

    return LLMError(
        error_type=error_type,
        provider=provider,
        model=model,
        status_code=status,
        message=text[:500],
    )
