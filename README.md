# QueryGuard 🛡️
### Privacy-First AI Database Gateway

[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green)](https://fastapi.tiangolo.com)
[![Redis](https://img.shields.io/badge/Redis-7.0+-red)](https://redis.io)
[![AWS](https://img.shields.io/badge/AWS-ECS%20%7C%20RDS%20%7C%20DynamoDB-orange)](https://aws.amazon.com)

> **Ask your database anything in plain English — without ever exposing sensitive data to an AI.**

---

## Overview

QueryGuard is an enterprise-grade AI gateway that lets users query databases using natural language while ensuring **zero PII exposure** to any external AI provider. It acts as an intelligent middleware layer between your users and your database — translating English questions into safe, validated SQL without the AI ever seeing real table names, column names, or sensitive data.

---

## The Problem

Companies want to use AI to make databases accessible to non-technical users. But this creates serious risks:

- 🔴 **Privacy Leak** — The AI sees real schema names like `users`, `credit_cards`, `ssn`
- 🔴 **Destructive Queries** — AI might generate `DELETE` or `DROP` commands that destroy data
- 🔴 **Cost Explosion** — Every query hits the AI API, even repeated identical questions
- 🔴 **Single Point of Failure** — If OpenAI goes down, the entire system stops

---

## The Solution

QueryGuard sits between the user and the AI as a **privacy-preserving smart gateway**:

```
User → QueryGuard → [Anonymized Schema] → AI → [Safe SQL] → Read-Only DB → Results
```

The AI never sees `users` or `email` — it only sees `T1` and `C3`. QueryGuard handles all translation, validation, caching, and failover invisibly.

---

## Features

### 🔒 Privacy Protection
- **Schema Anonymization** — Real table/column names replaced with generic identifiers (`users → T1`, `email → C3`) before sending to any AI provider
- **Bidirectional Mapping** — Encrypted mappings stored in AWS Secrets Manager; results de-anonymized before returning to the user
- **Zero PII Exposure** — Verified through query logs; the AI never touches real schema

### 🛡️ Security
- **SQL Deny List** — Blocks all destructive operations: `DROP`, `DELETE` without `WHERE`, `TRUNCATE`
- **EXPLAIN PLAN Validation** — Rejects queries that would perform full table scans
- **Read-Only Replica Execution** — All queries run on a read-only RDS replica; data modification is physically impossible
- **JWT Authentication** — All API endpoints secured with token-based auth
- **Rate Limiting** — 100 queries per user per day to prevent abuse

### ⚡ Performance & Cost
- **Redis Semantic Caching** — Similar queries (not just exact matches) served from cache, reducing AI API calls by ~70%
- **Query Timeout** — 30-second hard limit per query
- **Row Limit** — Maximum 10,000 rows returned per query

### 🔄 Reliability
- **Multi-LLM Orchestration** — Google Gemini as primary, NVIDIA NIM (Llama 3.3 70B) as automatic fallback
- **Circuit Breaker Pattern** — Auto-switches to backup AI when error rate exceeds 10%
- **Retry Logic** — 3 attempts with exponential backoff before failover
- **99%+ Uptime** — Maintained despite individual provider outages

### 📊 Observability
- **Full Audit Trail** — Every query logged to DynamoDB with execution time, SQL generated, and success/failure status
- **CloudWatch Metrics** — Real-time tracking of latency, error rate, and cache hit rate
- **Cost Tracking** — Per-query AI API cost monitoring
- **Grafana Dashboards** — Visual monitoring of system health and usage

---

## Author

**Bhavana Basavaraj**  
[GitHub](https://github.com/BhavanaBasavaraj) · [LinkedIn](https://www.linkedin.com/in/mb-bhavana-906a55221/)

---

_Built to demonstrate enterprise AI integration, cloud architecture, and privacy-first system design._
