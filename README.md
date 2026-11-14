# QueryGuard 🛡️
### Privacy-First AI Database Gateway

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.134-green)](https://fastapi.tiangolo.com)
[![Redis](https://img.shields.io/badge/Redis-7-red)](https://redis.io)
[![OpenTelemetry](https://img.shields.io/badge/OpenTelemetry-tracing-blueviolet)](https://opentelemetry.io)
[![Tests](https://img.shields.io/badge/tests-32%20passing-brightgreen)](#testing)

> **Ask your database questions in plain English, without sending your
> real schema to an AI provider.**

---

## Overview

QueryGuard translates natural-language questions into validated SQL. Before
any prompt leaves the service, the database schema is anonymized: the model
sees `T1` and `C3`, never `customers` and `email`. The generated SQL is
checked by a safety validator, de-anonymized, executed against PostgreSQL,
cached per user in Redis, audited to DynamoDB, and traced with OpenTelemetry.

It is a working prototype, not a production system. The
[Roadmap](#roadmap) lists what is deliberately not built yet.

---

## The Problem

Letting an AI query a database creates four risks:

- **Schema exposure** — the model sees real table and column names
- **Destructive SQL** — a generated `DROP` or `DELETE` could destroy data
- **Repeated cost** — identical questions hit the API every time
- **Provider failure** — one API outage stops the system

---

## How it works

```
POST /query  {question, database_id, user_id}
      │
      ▼
Redis cache lookup ──── hit ──▶ return cached rows (model skipped)
      │ miss
      ▼
Schema anonymization        customers → T1, email → C3
      │
      ▼
LLM router                  Gemini (retries + circuit breaker) → NVIDIA NIM fallback
      │                     sees only anonymized names + column type hints
      ▼
SQL validator               rejects anything that is not a single bounded SELECT
      │
      ▼
De-anonymization            T1 → customers
      │
      ▼
PostgreSQL execution        rows serialized to JSON
      │
      ▼
Audit row (DynamoDB) → cache store (Redis, 1h TTL) → response
```

Every step runs inside an OpenTelemetry request span; each LLM call is a
child span.

---

## What's implemented

### Privacy
- **Schema anonymization** (`app/core/privacy_proxy.py`) — real table and
  column names are replaced with `T<n>` / `C<n>` before any prompt is built.
  The mapping lives in memory for the duration of one request and is used to
  de-anonymize the returned SQL with word-boundary matching (longest names
  first, so `C12` is never partially replaced by `C1`).
- **Type hints without names** — the prompt carries column *descriptions*
  (`C4 (total revenue amount (numeric))`) to improve SQL quality, never the
  real names. An earlier version leaked the real table name in the hint text;
  a test now asserts the LLM input contains no real table names.
- **De-anonymize only after validation** — rejected SQL is never mapped back
  to real names.
- **Privacy-preserving telemetry** — spans carry a SHA-256 hash and length of
  the prompt and question, and a literal-stripped SQL fingerprint, never the
  text itself. Content capture is off unless `OTEL_CAPTURE_CONTENT=true`.

### SQL safety
The validator (`app/core/validator.py`) runs five checks:
1. The statement must start with `SELECT` or `WITH`
2. No denied keywords (`DROP`, `DELETE`, `TRUNCATE`, `INSERT`, `UPDATE`,
   `ALTER`, `CREATE`, `GRANT`, `REVOKE`, `EXECUTE`, `EXEC`)
3. A `LIMIT` clause is required
4. `LIMIT` must be a plain number no greater than 10,000 (`LIMIT ALL` and
   non-numeric values are rejected)
5. No stacked statements (a semicolon anywhere but the end is rejected)

Checks run against SQL with comments stripped and single- and double-quoted
literals masked, so `WHERE status = 'UPDATE'` does not trigger a false
positive and `/* DROP */` cannot hide a keyword from the scanner.

### Reliability
- **Two providers** — Google Gemini (`gemini-3.6-flash`, via `google-genai`)
  primary, NVIDIA NIM (`nvidia/nemotron-3.5-bolt-e4b`, via the OpenAI-compatible
  API) fallback. Model IDs are pinned in config, temperature is `0`, and
  Gemini's thinking budget is set to `0` for cheap, deterministic SQL.
- **Retries** — up to 3 Gemini attempts with exponential backoff and jitter,
  **transient failures only**.
- **Circuit breaker** on Gemini — opens after 5 consecutive failed requests
  (one count per request, not per retry), skips Gemini for 60s, then allows a
  trial request.
- **Structured error classification** (`app/core/llm_errors.py`) — provider
  exceptions are mapped to `model_gone`, `auth_failed`, `bad_request`
  (permanent: no retry) or `timeout`, `rate_limited`, `upstream_5xx`
  (transient: retried). When both providers fail, the error carries both
  classified causes.

### Caching
- **Redis, exact-match** — the key is an MD5 hash of the normalized
  (lower-cased, trimmed) question, the `database_id` and **the `user_id`**.
  Per-user scoping prevents one user receiving another's cached rows.
- **1-hour TTL**.
- **Fails open** — a Redis outage degrades to a cache miss rather than an
  error (covered by a test).

### Audit
- Every request outcome (success, LLM failure, validation rejection,
  execution error) is written to DynamoDB (`app/utils/audit.py`): question,
  generated SQL, latency, provider, cache hit, success flag and error.
- Points at **DynamoDB Local** (`docker-compose.yml`, `localhost:8002`) by
  default; set `DYNAMODB_ENDPOINT_URL=` (empty) to use real AWS credentials.
  The table is created on startup if missing.
- Writes **fail open** so an audit outage cannot block queries, but each
  failure is logged at `ERROR` and counted (`audit_failure_count()`).

### Observability
- **OpenTelemetry tracing** (`app/core/telemetry.py`) — one server span per
  HTTP request via `FastAPIInstrumentor` (health and docs routes excluded),
  ASGI protocol-event spans filtered out, 100% sampling, batched export.
- **GenAI semantic-convention spans** (`app/core/genai_span.py`) on both LLM
  clients: provider, request/response model, temperature, max tokens, input /
  output / reasoning / cached tokens, finish reason, attempt sequence and
  `error.type`. The convention version (`1.37.0`) is recorded on every span.
- **Request-level outcome attributes** on the root span: cache hit, final
  provider, guard verdict (`allowed` / `blocked` / `llm_failed`), rows
  returned, hashed question, user and database IDs.
- **Request correlation** — a valid inbound `X-Request-ID` is reused,
  otherwise one is generated; it is echoed on every response and included in
  every log line.
- **Consistent error contract** — errors return
  `{code, message, request_id}` with no internal details:

  | Code | HTTP |
  |---|---|
  | `INVALID_QUERY` | 400 |
  | `SQL_VALIDATION_FAILED` | 502 |
  | `LLM_PROVIDER_FAILURE` | 502 |
  | `DATABASE_EXECUTION_ERROR` | 500 |
  | `INTERNAL_SERVER_ERROR` | 500 |

---

## API

| Method | Path | Description |
|---|---|---|
| `POST` | `/query` | Body `{question, database_id, user_id}` → `{query_id, sql_generated, results, rows_returned, execution_time_ms, cache_hit, llm_provider, message}` |
| `GET` | `/health` | `{status, app}` |
| `GET` | `/` | Liveness message |
| `GET` | `/docs` | Swagger UI |

```bash
curl -s localhost:8000/query -H 'Content-Type: application/json' \
  -d '{"question":"Top 5 customers by revenue","database_id":"db_ecommerce","user_id":"user_123"}'
```

**Schema note:** the schema sent to the model is currently the hardcoded
`SAMPLE_SCHEMA` in `app/api/query.py` (`customers`, `orders`, `products`).
`database_id` scopes the cache and audit records but does not yet select a
different database or schema; every query runs against `DATABASE_URL`.

---

## Known issues found and fixed

Documented because the process matters more than the result:

| Issue | Impact | Status |
|---|---|---|
| Cache key omitted `user_id` | Two users asking the same question shared a cache entry, so the second received the first's result rows | Fixed, with regression tests |
| Real table name sent in schema hints | Anonymization was undone inside the same prompt that applied it | Fixed, with a regression test |
| Primary model retired | Every Gemini call failed; the fallback masked it | Fixed |
| Fallback model end-of-life | Both providers dead; the service returned errors with no signal | Fixed |
| Permanent errors were retried | A retired model consumed all three attempts and the full backoff sequence before failing over | Fixed |
| `LIMIT ALL` bypassed the row cap | Valid PostgreSQL for "no limit". The presence check saw the keyword; the value check silently skipped when its regex found no digits, so an unbounded query passed a validator whose purpose is bounding queries | Fixed, with regression tests |

The model-retirement issues are why [LogWatch](https://github.com/BhavanaBasavaraj/logwatch)
exists: every layer of resilience worked exactly as designed, and none of
them could report that the thing they protected against had become
permanent. The GenAI spans above are the instrumentation LogWatch consumes.

---

## Roadmap

Not implemented. Listed here rather than described as features:

- **Authentication** — `user_id` is taken from the request body and trusted.
  Config carries JWT settings and `app/api/auth.py` exists, but it is empty
  and nothing is enforced
- **Rate limiting** — `RATE_LIMIT_PER_DAY` is configured but not applied
- **Dynamic schemas** — introspect the target database per `database_id`
  instead of the hardcoded sample schema; persist the mappings encrypted
  (the `SchemaMapping` model exists but is unused, and Alembic is initialised
  with no migrations)
- **Read-only database role** — safety currently rests on the validator
  alone; a read-only connection would add defence in depth
- **Statement timeout** — `QUERY_TIMEOUT` is configured but no server-side
  timeout is enforced
- **Stronger validation** — the validator is regex-based; parsing the SQL
  (and `EXPLAIN` checks for full scans) would catch cases it cannot, such as
  side-effecting function calls inside a `SELECT`
- **Async I/O and pooling** — the `/query` handler is `async` but calls the
  LLM SDKs, Redis and `psycopg2` synchronously, and opens a new database
  connection per query
- **Fallback resilience** — the NIM fallback has no retries or breaker of
  its own
- **Audit queue** — audit writes are counted and logged on failure, but not
  queued and retried
- **OTLP export** — spans currently go to the console exporter; an OTLP
  exporter to a collector is next
- **Semantic caching** — the cache is exact-match; embedding-based
  similarity would let near-identical questions share an entry
- **Containerizing the app** — `docker-compose.yml` runs the dependencies
  (Postgres, Redis, DynamoDB Local); the API runs on the host and the
  `Dockerfile` is empty
- **Housekeeping** — remove the hidden `/test-unhandled-error` route, the
  empty placeholder modules (`app/api/admin.py`, `app/utils/security.py`,
  `app/utils/monitoring.py`) and unused dependencies; align the prompt's
  "maximum 1000 rows" with the validator's 10,000 cap

---

## Running locally

### 1. Start the dependencies

```bash
docker compose up -d     # Postgres :5434, Redis :6380, DynamoDB Local :8002 (all on 127.0.0.1)
```

### 2. Configure `.env`

The app's built-in defaults point at Postgres `5432` and Redis `6379`, so
set these to match the compose ports:

```dotenv
DATABASE_URL=postgresql://queryguard:local-dev-only@localhost:5434/queryguard
REDIS_URL=redis://localhost:6380
GEMINI_API_KEY=your-gemini-key
NVIDIA_API_KEY=your-nvidia-key
# optional
DYNAMODB_ENDPOINT_URL=http://localhost:8002   # default; empty = real AWS
OTEL_ENABLED=true                             # console span exporter
OTEL_CAPTURE_CONTENT=false                    # keep prompt text out of spans
```

### 3. Create the sample tables

Queries are generated against `customers(id, name, email, revenue, created_at)`,
`orders(id, customer_id, total, status, created_at)` and
`products(id, name, price, category, stock)`. Create and seed these in the
`queryguard` database; no seed script is included yet.

### 4. Run

```bash
python3 -m venv venv
venv/bin/pip install -r requirements-dev.txt
venv/bin/uvicorn app.main:app --reload
```

API docs at http://localhost:8000/docs

---

## Testing

```bash
GEMINI_API_KEY=test NVIDIA_API_KEY=test venv/bin/python -m pytest tests/ -q
```

32 tests. No Postgres, Redis, DynamoDB or real API keys are needed: the LLM,
cache and database calls are mocked. A placeholder `GEMINI_API_KEY` must be
set (in the environment or `.env`) because the Gemini client is created at
import time.

| File | Tests | Covers |
|---|---|---|
| `test_validator.py` | 15 | Deny list, LIMIT rules incl. `LIMIT ALL`, stacked statements, comment and literal handling |
| `test_privacy_proxy.py` | 3 | Schema anonymization, sub-token-safe de-anonymization (`C1` vs `C12`), table/column name collisions |
| `test_cache.py` | 4 | Fail-open behaviour; key isolation by user and database |
| `test_integration.py` | 5 | Health/root, full pipeline, cache hit skips the model, LLM input contains no real table names |
| `test_dx.py` | 5 | Error contract shape, 502 on validation failure, request-ID reuse, validator details and real schema names kept out of the client error body (logged server-side only), Redis-offline resilience |

---

## Tech stack

FastAPI · Pydantic v2 · PostgreSQL (psycopg2) · Redis · DynamoDB (boto3) ·
Google Gen AI SDK · OpenAI SDK (NVIDIA NIM) · OpenTelemetry · pytest ·
Docker Compose

---

## A note on metrics

This README previously carried figures for cache hit rate and uptime that
were never measured. They have been removed rather than revised. Measured
replacements will come from
[LogWatch](https://github.com/BhavanaBasavaraj/logwatch), which consumes this
service's OpenTelemetry spans and records latency, token usage, cost and
provider fallback rates per request.

---

## Author

**Bhavana Basavaraj**
[GitHub](https://github.com/BhavanaBasavaraj) · [LinkedIn](https://www.linkedin.com/in/bhavanamb/)
