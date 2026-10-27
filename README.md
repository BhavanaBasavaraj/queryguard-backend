# QueryGuard 🛡️
### Privacy-First AI Database Gateway

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green)](https://fastapi.tiangolo.com)
[![Redis](https://img.shields.io/badge/Redis-7.0+-red)](https://redis.io)
[![Tests](https://img.shields.io/badge/tests-30%20passing-brightgreen)](#testing)

> **Ask your database questions in plain English, without sending your
> real schema to an AI provider.**

---

## Overview

QueryGuard translates natural-language questions into validated SQL. Before
any prompt leaves the service, the database schema is anonymized: the model
sees `T1` and `C3`, never `customers` and `email`. The generated SQL is
checked against a safety validator, de-anonymized, and executed.

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
User question
↓
Schema anonymization customers → T1, email → C3
↓
LLM (Gemini → NIM fallback) sees only anonymized names + column type hints
↓
SQL validator 5 checks; rejects anything not a bounded SELECT
↓
De-anonymization T1 → customers
↓
PostgreSQL results returned to the user
A Redis cache sits in front, keyed per user, so a repeated question from the
same user skips the model entirely.

---

## What's implemented

### Privacy
- **Schema anonymization** — real table and column names are replaced with
  generic identifiers before any prompt is built. Mappings are held in
  memory per request and used to de-anonymize the returned SQL.
- **Type hints without names** — the prompt carries column *types*
  (`C2 (date)`) to improve SQL quality, never the real names. An earlier
  version leaked the real table name in the hint text; see
  [commit history](#known-issues-found-and-fixed).

### SQL safety
The validator (`app/core/validator.py`) runs five checks:
1. The statement must start with `SELECT` or `WITH`
2. No denied keywords (`DROP`, `DELETE`, `TRUNCATE`, `INSERT`, `UPDATE`,
   `ALTER`, `CREATE`, `GRANT`, `REVOKE`, `EXECUTE`)
3. A `LIMIT` clause is required
4. `LIMIT` may not exceed 10,000
5. No stacked statements (a semicolon anywhere but the end is rejected)

Checks run against SQL with comments stripped and string literals masked,
so `WHERE status = 'UPDATE'` does not trigger a false positive and
`/* DROP */` cannot hide a keyword from the scanner.

### Reliability
- **Two providers** — Google Gemini (`gemini-3.6-flash`) primary,
  NVIDIA NIM (`nvidia/nemotron-3.5-bolt-e4b`) fallback
- **Circuit breaker** — opens after 5 consecutive failures, waits 60s, then
  allows one trial request before closing or re-opening
- **Retries** — up to 3 attempts with exponential backoff and jitter,
  **transient failures only**
- **Structured error classification** — provider exceptions are mapped to
  `model_gone`, `auth_failed`, `rate_limited`, `timeout`, `upstream_5xx` or
  `bad_request`. Permanent failures skip retries entirely, since retrying a
  retired model cannot succeed.

### Caching
- **Redis, exact-match** — the key is a hash of the normalized question,
  the database id, and **the user id**. Per-user scoping prevents one user
  receiving another's cached result rows.
- **Fails open** — a Redis outage degrades to a cache miss rather than an
  error.

### Audit
- Query audit logging is implemented against DynamoDB (`app/utils/audit.py`),
  recording the generated SQL, execution time, provider, and outcome.
- **Not yet exercised.** No AWS resources have been provisioned, and audit
  writes fail open: when DynamoDB is unreachable the failure is logged as a
  warning and the request proceeds. Running this against DynamoDB Local is
  on the roadmap.

---

## Known issues found and fixed

Documented because the process matters more than the result:

| Issue | Impact | Status |
|---|---|---|
| Cache key omitted `user_id` | Two users asking the same question shared a cache entry, so the second received the first's result rows | Fixed, with regression tests |
| Real table name sent in schema hints | Anonymization was undone inside the same prompt that applied it | Fixed |
| Primary model retired (Sept 2025) | Every Gemini call failed; the fallback masked it | Fixed |
| Fallback model end-of-life (Aug 2026) | Both providers dead; the service returned errors for months with no signal | Fixed |
| Permanent errors were retried | A retired model cost 3 attempts and ~7s of backoff per request | Fixed |
| `LIMIT ALL` bypassed the row cap | Valid PostgreSQL for "no limit". The presence check saw the keyword; the value check silently skipped when its regex found no digits, so an unbounded query passed a validator whose purpose is bounding queries | Fixed, with regression tests |

The last two are why [LogWatch](https://github.com/BhavanaBasavaraj/logwatch)
exists: every layer of resilience worked exactly as designed, and none of
them could report that the thing they protected against had become
permanent.

---

## Roadmap

Not implemented. Listed here rather than described as features:

- **Authentication** — config carries JWT settings; no auth is enforced
- **Rate limiting** — a per-day limit is configured but not applied
- **Read-only database role** — safety currently rests on the validator
  alone; a read-only connection would add defence in depth
- **Statement timeout** — no server-side query timeout is enforced
- **Audit failure visibility** — audit writes currently fail open and
  silently; they should be surfaced or queued
- **`EXPLAIN` validation** — rejecting plans that would full-scan
- **Semantic caching** — the cache is exact-match; embedding-based
  similarity would let near-identical questions share an entry
- **Persisted, encrypted schema mappings** — currently in-memory only
- **Containerization** — `Dockerfile` and `docker-compose.yml` are stubs
- **Measured metrics** — cache hit rate, cost per query, provider fallback
  rate and latency percentiles are being instrumented in
  [LogWatch](https://github.com/BhavanaBasavaraj/logwatch)

---

## Running locally

Requires PostgreSQL and Redis.

```bash
python3 -m venv venv
venv/bin/pip install -r requirements-dev.txt
cp .env.example .env        # then fill in GEMINI_API_KEY and NVIDIA_API_KEY
venv/bin/uvicorn app.main:app --reload
```

API docs at http://localhost:8000/docs

## Testing

```bash
venv/bin/python -m pytest tests/ -q
```

30 tests covering the validator, the privacy proxy, cache key isolation,
and request integration.

---

## A note on metrics

This README previously carried figures for cache hit rate and uptime that
were never measured. They have been removed rather than revised. Measured
replacements will come from
[LogWatch](https://github.com/BhavanaBasavaraj/logwatch), which instruments
this service with OpenTelemetry and records latency, token usage, cost and
provider fallback rates per request.

---

## Author

**Bhavana Basavaraj**
[GitHub](https://github.com/BhavanaBasavaraj) · [LinkedIn](https://www.linkedin.com/in/mb-bhavana-906a55221/)
