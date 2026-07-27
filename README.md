# los-inmaduros-fastapi

[![FastAPI](https://img.shields.io/badge/FastAPI-0.139-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-D71F00)](https://www.sqlalchemy.org/)
[![Tests](https://img.shields.io/badge/tests-119%20passing-brightgreen)](#usage)
[![README style: standard](https://img.shields.io/badge/readme%20style-standard-brightgreen)](https://github.com/RichardLitt/standard-readme)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](#license)

> Production backend for **Los Inmaduros Rollers Madrid** — a FastAPI port of a live Express API, migrated without breaking the frontend.

REST API that powers an inline-skating community in Madrid: predefined routes, skate meetups
("route calls"), attendance, photo covers, reviews, favorites and moderation. This repository is
the **migration of the original Node + TypeScript (Express) backend to Python (FastAPI)**, done
against a frozen API contract so the deployed Next.js frontend keeps working with **zero changes**.

- 🌐 **Live API:** https://los-inmaduros-fastapi.onrender.com — interactive docs at [`/api-docs`](https://los-inmaduros-fastapi.onrender.com/api-docs)
- 💻 **Frontend it serves:** https://los-inmaduros-rollers.vercel.app

## Table of Contents

- [Security](#security)
- [Background](#background)
- [Install](#install)
- [Usage](#usage)
- [API](#api)
- [Architecture](#architecture)
- [Maintainers](#maintainers)
- [Contributing](#contributing)
- [License](#license)

## Security

- **Authentication** via [Clerk](https://clerk.com/) — every protected endpoint validates a JWT
  (`Authorization: Bearer <token>`); a just-in-time *user-sync* mirrors the Clerk identity locally.
- **Secrets** live only in environment variables, never in the repo. The Supabase **service-role
  key** is used server-side exclusively (file uploads); the browser never sees it.
- **Rate limiting** ([slowapi](https://github.com/laurentS/slowapi)) on auth and creation endpoints,
  keyed on the real client IP (`X-Forwarded-For`) so it works correctly behind the proxy.
- **Input validation** with Pydantic v2 on every request; fine-grained permissions
  (organizer / owner / admin) enforced in the service layer.

## Background

The app already existed and worked in production (V2, Express + Prisma). The goal of this project
was to **re-implement the backend in FastAPI as a portfolio-grade, professional codebase** while the
public Next.js frontend kept running untouched. Two principles drove the work:

1. **The API contract is sacred.** Same routes, same request/response shapes, same status codes, so
   the frontend never noticed the swap. The contract is the single source of truth.
2. **Migrate *and* improve.** Every design flaw spotted in the legacy code was surfaced with
   evidence, decided on, and recorded as a numbered decision (D-x) — never changed silently. A few
   examples shipped this way:
   - Error responses now use the `message` field the frontend actually reads (the old `error` field
     meant real error texts never reached the UI).
   - The route catalogue went from an N+1 query to a single aggregated query.
   - `PUT` → `PATCH` with true partial-update semantics; unified permission-before-state check order.
   - Datetimes serialize exactly like `Date.toISOString()` (`...Z`) to avoid timezone drift.

Other engineering highlights:

- **Existing database, mapped faithfully.** SQLAlchemy 2.0 models mirror the real Prisma-created
  schema (table/column names, native PG enums, array columns) — verified by an Alembic
  `autogenerate` diff that comes back **empty**. No table was ever recreated.
- **Tests written alongside the code.** The suite never calls external services and never leaves
  residue in the shared database: identities are faked via `dependency_overrides`, the Clerk SDK and
  Telegram/Storage are mocked, and every DB write runs inside a transactional savepoint that rolls
  back on teardown — guarded by an automated residue check.
- **Background scheduler** (APScheduler) transitions route-call statuses
  (`SCHEDULED → ONGOING → COMPLETED`) with an idempotent catch-up design robust to the free-tier
  host sleeping.
- **Telegram notifications** (direct Bot API, env-gated, non-blocking) announce route-call
  create / edit / cancel / delete.

### Built with

FastAPI · Pydantic v2 · SQLAlchemy 2.0 (sync) + Alembic · PostgreSQL (Supabase) · Clerk ·
Supabase Storage · APScheduler · slowapi · httpx · pytest · uv · Ruff

## Install

**Prerequisites:** [uv](https://docs.astral.sh/uv/) (which also manages the pinned **Python 3.12**).

```bash
git clone https://github.com/Adriasu09/los-inmaduros-fastapi.git
cd los-inmaduros-fastapi
uv sync
```

Create your environment file from the template and fill in the values:

```bash
cp .env.example .env
```

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | ✅ | PostgreSQL connection string (Supabase **session pooler**, `postgresql://…`) |
| `ENVIRONMENT` | — | `development` (default) or `production` |
| `CORS_ORIGINS` | — | Comma-separated allowed origins (default `http://localhost:3000`) |
| `CLERK_SECRET_KEY` | — | Clerk auth (protected endpoints, dev test-token) |
| `CLERK_WEBHOOK_SECRET` | — | Enables the Clerk `user.updated` webhook |
| `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` | — | Supabase Storage (route-call cover uploads) |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | — | Telegram notifications (disabled if unset) |
| `WEBSITE_URL` | — | Public frontend base URL used in Telegram links |
| `SCHEDULER_ENABLED` | — | Background status scheduler (default `true`) |

> The database already exists on Supabase. Alembic is stamped at a baseline that mirrors the live
> schema — there are **no migrations to run** against it. Never run destructive DDL against it.

## Usage

Run the development server (auto-reload):

```bash
uv run fastapi dev src/main.py
```

…or with uvicorn directly (the production start command):

```bash
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Then open the interactive OpenAPI docs at **http://127.0.0.1:8000/api-docs** and the health check at
`/health` (a real `SELECT 1` against the database).

Run the test suite:

```bash
uv run pytest
```

**Response envelope.** Every response follows a fixed shape the frontend depends on:

```jsonc
// success
{ "success": true, "data": { }, "count": 17, "pagination": { } }
// error
{ "success": false, "message": "Route call not found", "errors": { "field": ["…"] } }
```

**Authentication.** Send a Clerk JWT as `Authorization: Bearer <token>`. In development,
`POST /api/auth/test-token` mints a token from an email for manual testing (404 in production).

## API

Full interactive reference at [`/api-docs`](https://los-inmaduros-fastapi.onrender.com/api-docs).
Overview of the migrated core:

| Method | Route | Description | Auth |
|---|---|---|---|
| `GET` | `/health` | Health check + DB ping | Public |
| `POST` | `/api/auth/test-token` | Dev-only JWT generator (404 in prod) | Public |
| `POST` | `/api/webhooks/clerk` | Clerk `user.updated` sync (svix-verified) | Signature |
| `GET` | `/api/routes` | Predefined routes with avg rating + counts | Public |
| `GET` | `/api/routes/{slug}` | Route detail (paginated reviews, active photos) | Public |
| `POST` | `/api/route-calls` | Create a route call | Auth |
| `GET` | `/api/route-calls` | List with filters + pagination | Public |
| `GET` | `/api/route-calls/{id}` | Detail (organizer, meeting points, attendees) | Public |
| `PATCH` | `/api/route-calls/{id}` | Edit (organizer, while `SCHEDULED`) | Auth |
| `PATCH` | `/api/route-calls/{id}/cancel` | Cancel | Auth |
| `DELETE` | `/api/route-calls/{id}` | Delete (only with no attendances) | Auth |
| `POST` | `/api/route-calls/{id}/attendances` | Join a route call | Auth |
| `DELETE` | `/api/route-calls/{id}/attendances` | Cancel my attendance | Auth |
| `GET` | `/api/route-calls/{id}/attendances` | List confirmed attendees | Public |
| `GET` | `/api/route-calls/{id}/attendances/check` | Am I attending? | Auth |
| `GET` | `/api/attendances/my-attendances` | My confirmed attendances | Auth |
| `POST` | `/api/photos` | Upload a route-call cover photo | Auth |

## Architecture

Domain-driven layout — one package per contract module, each with `models` / `schemas` / `service`
/ `router`, and thin HTTP routers over a service layer that owns the business rules:

```
src/
├── main.py            # app factory: CORS, routers, exception handlers, lifespan
├── core/              # config, database (engine + session), exceptions, base schemas
├── auth/              # Clerk deps, user-sync, dev test-token, webhook
├── routes/            # predefined routes (read-only)
├── route_calls/       # route calls: CRUD + status rules
├── attendances/       # join / cancel / list / check
├── photos/            # cover-photo upload (Supabase Storage)
├── common/            # scheduler, rate limiting, Telegram notifications, storage, pagination
└── ...                # reviews, favorites, app_config (roadmap)
tests/                 # mirrors the modules; transactional, no external calls
```

## Maintainers

[Adriana Suárez (@Adriasu09)](https://github.com/Adriasu09) — bootcamp final project (Factoría F5 / FemCoders).

## Contributing

This is a personal portfolio / bootcamp project, but feedback is welcome. Open an
[issue](https://github.com/Adriasu09/los-inmaduros-fastapi/issues) to discuss a change, or send a PR
against the `develop` branch. Please keep the [API contract](docs/api-contract.md) intact, follow the
existing module structure, and add tests alongside any new code.

## License

[MIT](LICENSE) © 2026 Adriana Suárez
