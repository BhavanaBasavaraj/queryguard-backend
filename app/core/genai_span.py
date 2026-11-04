"""GenAI span attributes, per the OpenTelemetry GenAI semantic conventions.

These conventions are still in development: the namespace moved to its own
repository and nothing in it is marked stable. `gen_ai.system` was renamed
to `gen_ai.provider.name` during development, which is why attribute keys
live here rather than being written inline. When the spec moves again, this
file changes and nothing else does.

Content capture (the prompt and completion text) is OFF by default.
QueryGuard exists to keep real schema away from the model; putting the
prompt into the telemetry pipeline would place the same content in a second
system. Spans carry a hash and a length instead, and the full text only when
settings.otel_capture_content is true.
"""
import hashlib
import re
from typing import Any

from opentelemetry.trace import Status, StatusCode

# Pinned convention version. Recorded on every span so stored rows can be
# interpreted against the spec that produced them.
SEMCONV_VERSION = "1.37.0"

# --- attribute keys -------------------------------------------------------
OPERATION = "gen_ai.operation.name"
PROVIDER = "gen_ai.provider.name"      # renamed from gen_ai.system
REQUEST_MODEL = "gen_ai.request.model"
RESPONSE_MODEL = "gen_ai.response.model"
INPUT_TOKENS = "gen_ai.usage.input_tokens"
OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
REASONING_TOKENS = "gen_ai.usage.reasoning.output_tokens"
CACHED_INPUT_TOKENS = "gen_ai.usage.cache_read.input_tokens"
FINISH_REASONS = "gen_ai.response.finish_reasons"
TEMPERATURE = "gen_ai.request.temperature"
MAX_TOKENS = "gen_ai.request.max_tokens"
ERROR_TYPE = "error.type"

# Not in the spec: QueryGuard's own attributes.
QG_SEMCONV_VERSION = "queryguard.semconv_version"
QG_ATTEMPT_SEQ = "queryguard.attempt_seq"
QG_PROMPT_SHA256 = "queryguard.prompt_sha256"
QG_PROMPT_CHARS = "queryguard.prompt_char_len"
QG_SQL_FINGERPRINT = "queryguard.sql_fingerprint"

# Spec attributes for content, used only when capture is enabled.
INPUT_MESSAGES = "gen_ai.input.messages"
OUTPUT_MESSAGES = "gen_ai.output.messages"

_LITERAL = re.compile(r"'[^']*'|\b\d+\b")


def span_name(operation: str, model: str) -> str:
    """{gen_ai.operation.name} {gen_ai.request.model}, per the spec."""
    return f"{operation} {model}"


def sql_fingerprint(sql: str) -> str:
    """SQL with literal values replaced by '?'.

    Groups identical query shapes and drops any user data that reached a
    literal, e.g. WHERE name = 'John Smith' becomes WHERE name = ?.
    """
    return _LITERAL.sub("?", sql or "")


def sha256(text: str) -> str:
    return hashlib.sha256((text or "").encode()).hexdigest()


def set_request_attributes(span, *, provider: str, model: str,
                           prompt: str, temperature: float, max_tokens: int,
                           attempt_seq: int, capture_content: bool) -> None:
    span.set_attribute(OPERATION, "chat")
    span.set_attribute(PROVIDER, provider)
    span.set_attribute(REQUEST_MODEL, model)
    span.set_attribute(TEMPERATURE, temperature)
    span.set_attribute(MAX_TOKENS, max_tokens)
    span.set_attribute(QG_SEMCONV_VERSION, SEMCONV_VERSION)
    span.set_attribute(QG_ATTEMPT_SEQ, attempt_seq)

    # Shape and identity of the prompt, never its content by default.
    span.set_attribute(QG_PROMPT_SHA256, sha256(prompt))
    span.set_attribute(QG_PROMPT_CHARS, len(prompt or ""))
    if capture_content:
        span.set_attribute(INPUT_MESSAGES, prompt)


def set_response_attributes(span, *, response_model: str | None,
                            input_tokens: int | None, output_tokens: int | None,
                            reasoning_tokens: int | None,
                            cached_input_tokens: int | None,
                            finish_reason: str | None,
                            sql: str | None, capture_content: bool) -> None:
    # Recorded separately from the request model: a provider may serve a
    # different model than the one asked for, and cost is priced on what
    # actually answered.
    if response_model:
        span.set_attribute(RESPONSE_MODEL, response_model)
    if input_tokens is not None:
        span.set_attribute(INPUT_TOKENS, input_tokens)
    if output_tokens is not None:
        span.set_attribute(OUTPUT_TOKENS, output_tokens)
    if reasoning_tokens:
        span.set_attribute(REASONING_TOKENS, reasoning_tokens)
    if cached_input_tokens:
        span.set_attribute(CACHED_INPUT_TOKENS, cached_input_tokens)
    if finish_reason:
        span.set_attribute(FINISH_REASONS, [str(finish_reason)])
    if sql:
        span.set_attribute(QG_SQL_FINGERPRINT, sql_fingerprint(sql))
        if capture_content:
            span.set_attribute(OUTPUT_MESSAGES, sql)


def record_error(span, exc: Any, error_type: str) -> None:
    """Three distinct things: a status, an event, and a groupable attribute."""
    span.set_attribute(ERROR_TYPE, error_type)
    span.record_exception(exc)
    span.set_status(Status(StatusCode.ERROR, error_type))


# --- root span (one per request) ------------------------------------------
# Request-level facts, as distinct from per-call facts. These map onto
# query_events; the gen_ai.* attributes above map onto llm_calls.
QG_CACHE_HIT = "queryguard.cache_hit"
QG_PROVIDER_FINAL = "queryguard.provider_final"
QG_ATTEMPT_COUNT = "queryguard.attempt_count"
QG_GUARD_VERDICT = "queryguard.guard_verdict"
QG_QUESTION_SHA256 = "queryguard.question_sha256"
QG_QUESTION_CHARS = "queryguard.question_char_len"
QG_USER_ID = "queryguard.user_id"
QG_DATABASE_ID = "queryguard.database_id"
QG_ROWS_RETURNED = "queryguard.rows_returned"


def set_request_facts(span, *, question: str, user_id: str, database_id: str) -> None:
    """Facts known before any work happens. Set on every path, including
    the ones that fail, so a failed request is still explicable."""
    span.set_attribute(QG_QUESTION_SHA256, sha256(question))
    span.set_attribute(QG_QUESTION_CHARS, len(question or ""))
    span.set_attribute(QG_USER_ID, user_id)
    span.set_attribute(QG_DATABASE_ID, database_id)
    span.set_attribute(QG_SEMCONV_VERSION, SEMCONV_VERSION)


def set_outcome(span, *, cache_hit: bool, provider_final: str | None = None,
                attempt_count: int | None = None, guard_verdict: str | None = None,
                rows_returned: int | None = None, sql: str | None = None) -> None:
    """How the request resolved.

    cache_hit is always set, never omitted: a cache hit produces a span
    with no child, and without this attribute that is indistinguishable
    from a request that failed before reaching a model.
    """
    span.set_attribute(QG_CACHE_HIT, cache_hit)
    if provider_final:
        span.set_attribute(QG_PROVIDER_FINAL, provider_final)
    if attempt_count is not None:
        span.set_attribute(QG_ATTEMPT_COUNT, attempt_count)
    if guard_verdict:
        span.set_attribute(QG_GUARD_VERDICT, guard_verdict)
    if rows_returned is not None:
        span.set_attribute(QG_ROWS_RETURNED, rows_returned)
    if sql:
        span.set_attribute(QG_SQL_FINGERPRINT, sql_fingerprint(sql))
