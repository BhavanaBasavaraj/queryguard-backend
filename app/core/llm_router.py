"""Route SQL generation across providers, with retries and a circuit breaker.

Design notes:
- Only transient failures are retried. A retired model or a rejected key
  cannot be fixed by trying again, so those fall through immediately.
- The circuit breaker counts one failure per request, not per retry
  attempt, so its threshold means what it says.
- Provider identifiers follow OpenTelemetry GenAI conventions, because
  they are recorded as-is by LogWatch and joined against model pricing.
"""
import logging
import random
import time

from app.config import settings
from app.core import providers
from app.core.llm_errors import LLMError, classify
from app.services import gemini_client, nvidia_client

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
BASE_BACKOFF_SECONDS = 1.0


class CircuitBreaker:
    """Stop calling a provider that is consistently failing.

    Counts consecutive failed requests. After `failure_threshold` the
    breaker opens and calls are skipped until `cooldown_seconds` passes.
    """

    def __init__(self, name: str, failure_threshold: int = 5,
                 cooldown_seconds: int = 60):
        self.name = name
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.last_failure_time: float | None = None
        self.is_open = False

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold and not self.is_open:
            self.is_open = True
            logger.warning(
                "circuit breaker OPEN for %s after %d consecutive failures",
                self.name, self.failure_count,
            )

    def record_success(self) -> None:
        if self.is_open:
            logger.info("circuit breaker CLOSED for %s", self.name)
        self.failure_count = 0
        self.is_open = False

    def can_attempt(self) -> bool:
        if not self.is_open:
            return True
        if time.time() - self.last_failure_time >= self.cooldown_seconds:
            logger.info("circuit breaker HALF-OPEN for %s, trying again", self.name)
            self.is_open = False
            self.failure_count = 0
            return True
        return False


gemini_breaker = CircuitBreaker(providers.GEMINI)


def _backoff(attempt: int) -> float:
    """Exponential backoff with jitter.

    Jitter spreads retries out so that many clients failing at the same
    moment do not all retry at the same moment and re-break the service.
    """
    return BASE_BACKOFF_SECONDS * (2 ** attempt) * (0.5 + random.random())


class LLMRouter:

    def generate_sql(self, question: str, anonymized_schema: dict,
                     schema_hints: dict = None) -> tuple[str, str]:
        last_error: LLMError | None = None

        if gemini_breaker.can_attempt():
            for attempt in range(MAX_ATTEMPTS):
                try:
                    sql = gemini_client.generate_sql(
                        question, anonymized_schema, schema_hints)
                    gemini_breaker.record_success()
                    return sql, providers.GEMINI
                except LLMError as e:
                    last_error = e
                    if not e.is_transient:
                        logger.error(
                            "%s failed permanently (%s), not retrying: %s",
                            providers.GEMINI, e.error_type, e.message[:200],
                        )
                        break
                    if attempt < MAX_ATTEMPTS - 1:
                        wait = _backoff(attempt)
                        logger.warning(
                            "%s attempt %d/%d failed (%s), retrying in %.1fs",
                            providers.GEMINI, attempt + 1, MAX_ATTEMPTS,
                            e.error_type, wait,
                        )
                        time.sleep(wait)
            # One failed request counts once toward the breaker, however
            # many attempts it took.
            gemini_breaker.record_failure()
        else:
            logger.info("%s skipped: circuit breaker is open", providers.GEMINI)

        try:
            sql = nvidia_client.generate_sql(
                question, anonymized_schema, schema_hints)
            return sql, providers.NIM
        except LLMError as e:
            logger.error("all providers failed; last error: %s", e)
            raise AllProvidersFailed(primary=last_error, fallback=e) from e


class AllProvidersFailed(Exception):
    """Every provider in the chain failed.

    Carries both structured errors so the caller, and LogWatch, can see
    why each one failed rather than a single flattened string.
    """

    def __init__(self, primary: LLMError | None, fallback: LLMError):
        self.primary = primary
        self.fallback = fallback
        parts = []
        if primary is not None:
            parts.append(f"{primary.provider}={primary.error_type}")
        parts.append(f"{fallback.provider}={fallback.error_type}")
        super().__init__("all LLM providers failed: " + ", ".join(parts))
