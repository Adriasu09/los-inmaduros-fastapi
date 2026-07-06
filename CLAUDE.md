# CLAUDE.md — Los Inmaduros Rollers Madrid · FastAPI Backend

> Permanent context for Claude Code. **Read this file in full before writing any code.**
> This repo is the migration of the Express backend (Node + TypeScript) to **FastAPI (Python)**.

## 1. What this project is

Web app for an inline-skating community in Madrid: predefined routes, skate meetups (route-calls),
attendance, reviews, favorites and photos with moderation. The project **already exists and works**
(V2 in Express); here we port it to FastAPI **without breaking the frontend**.

- Frontend (NOT touched from this repo): Next.js 16 + Clerk + TanStack Query, deployed on Vercel.
- Database: PostgreSQL on Supabase (the same one the current Express backend uses).
- Bootcamp final project (Factoría F5). Code freeze on **July 25**; presentation on July 27.
- The author is a junior developer: comment the code clearly and explain non-obvious decisions
  in your summaries.

## 2. GOLDEN RULE (non-negotiable)

**The API contract is sacred.** FastAPI must expose the SAME routes, with the SAME
request/response shapes as the current Express API. The full contract lives in
`docs/api-contract.md` — it is the single source of truth. If the reference code contradicts
the contract, the contract wins. If you find a genuine ambiguity, ASK before deciding.

Easy ways to break the contract (watch out for these):
- Every response is wrapped in an envelope: `{ "success": bool, "data": ..., "message"?: str, "count"?: int, "pagination"?: {...} }`.
- Gallery routes hang under `/api/photos/...` (e.g. `/api/photos/routes/{slug}/gallery`),
  even though the Express code comments claim otherwise.
- Error codes matter: 400 validation/invalid state, 401 no identity, 403 no permission,
  404 not found, 409 conflict (duplicates).

### Controlled contract changes (never silent ones)

The contract is the starting point, not a prison. If you spot a real bug, a bad practice or a
clear improvement that would require changing the contract or touching the frontend:
1. **Do NOT implement it on your own.**
2. Add it at the end of your summary as `IMPROVEMENT PROPOSAL:` explaining what would change
   in the contract and what would need to be adjusted in the frontend.
3. The author decides. If approved, it gets recorded as a D-x decision, `docs/api-contract.md`
   is updated, and a frontend task is created on the Kanban board.

Real example already applied through this process: D5 (review DELETE widened from
"author only" to "author or ADMIN").

## 3. Stack and confirmed decisions (D1–D9)

| Piece | Tool |
|---|---|
| Framework | FastAPI |
| ORM + migrations | SQLAlchemy 2.0 (sync) + Alembic |
| Validation | Pydantic v2 (+ pydantic-settings for the .env) |
| Auth | Clerk — `clerk-backend-api` SDK, `authenticate_request` method |
| Storage | Supabase Storage via `supabase-py` with the **service role key** (server-side only) |
| Scheduler | APScheduler |
| Rate limiting | slowapi |
| Tests | pytest + httpx (TestClient) |

Recorded decisions (summary; full detail lives in Notion):
- **D1**: replicate `POST /api/auth/test-token` in development ONLY (404 in production). Used to
  authenticate in Postman and in the tests.
- **D2**: photos = publish-then-moderate. They are born `ACTIVE` and visible; admins moderate afterwards.
- **D3**: gallery endpoints are the LAST thing in the photos module (P2 priority).
- **D4**: route-call DELETE: the backend allows organizer or ADMIN (same as Express);
  the "admin only" restriction belongs to the frontend UI.
- **D5**: review DELETE: the author **or an ADMIN** (deliberate improvement over Express, which
  only allowed the author). Editing remains author-only.
- **D6**: do NOT use the native Clerk↔Supabase integration or RLS. All data access goes through
  this API. Storage uses the service role key.
- **D7**: EVERYTHING SYNCHRONOUS. `def` routes (no `async def` with blocking I/O) and sync
  SQLAlchemy. FastAPI runs `def` routes in a threadpool; that is enough at this scale. Do not
  introduce asyncpg/AsyncSession.
- **D8**: (frontend, does not apply to this repo) pnpm + Vitest; no Vite as build tool.
- **D9**: Telegram notification on route-call creation, WITHOUT N8N: direct call to the Bot API
  (`sendPhoto` with the cover image + caption, or `sendMessage` when there is no image) from
  `shared/notifications.py`, fired with BackgroundTasks from the route-calls service.
  P2 and disabled by default: without `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` in the .env,
  it does nothing.

## 4. Architecture: domain-based structure

One package per contract module. Each module contains `models.py`, `schemas.py`, `service.py`,
`router.py` (+ `exceptions.py` if needed). Cross-cutting concerns live in `core/` and `shared/`.

```
src/
├── main.py               # app factory: CORS, routers, exception handlers
├── core/
│   ├── config.py         # Settings (pydantic-settings)
│   ├── database.py       # engine, SessionLocal, Base, get_db
│   ├── exceptions.py     # NotFoundError, ForbiddenError, ConflictError, BadRequestError + handlers
│   └── schemas.py        # generic ApiResponse[T] + Pagination
├── auth/                 # deps: get_current_user, require_admin, optional_auth + user-sync + test-token
├── routes/
├── route_calls/
├── attendances/
├── reviews/
├── favorites/
├── photos/
├── app_config/           # the contract's "config" module (named differently to avoid clashing with core/config.py)
└── shared/
    ├── storage.py        # Supabase Storage (service role key)
    ├── scheduler.py      # APScheduler: SCHEDULED -> ONGOING -> COMPLETED
    ├── rate_limit.py     # slowapi: auth_limiter, creation_limiter
    ├── notifications.py  # Telegram Bot API notification (D9, optional, env-gated)
    └── pagination.py     # shared page/limit helper + pagination block
tests/                    # mirrors the modules: test_auth.py, test_route_calls.py, ...
docs/                     # api-contract.md + gherkin/*.feature (do NOT edit: they are the spec)
reference/express-backend # clone of the old Express backend, READ-ONLY, in .gitignore
```

## 5. Code conventions

- **Layer separation (SOLID)**: the router only speaks HTTP (declares deps, calls the service,
  returns the envelope). The service concentrates business rules and fine-grained permissions
  (organizer/owner/admin → raises ForbiddenError). Models know nothing about HTTP.
- **Errors**: services raise domain exceptions (`core/exceptions.py`); a global handler converts
  them to HTTP with the envelope (`success: false`). Never `raise HTTPException` inside a service.
- **Naming**: code, classes, functions and comments in **English**. Endpoints identical to the contract.
- **Auth**: `get_current_user` validates the Clerk JWT (`authenticate_request`) and performs the
  user-sync (looks up by `clerkId`; creates the user with role USER if missing). `require_admin`
  builds on it. `optional_auth` for endpoints that behave differently with/without a session.
- **Database**: the database ALREADY EXISTS on Supabase with tables created by Prisma
  (Prisma-style table/column names). SQLAlchemy models must map the REAL existing names
  (use `__tablename__` and `mapped_column(name=...)` according to what is actually in the DB;
  verify against `reference/express-backend/prisma/schema.prisma`). The Alembic strategy is
  decided in task T-07: first option, autogenerated initial migration + `alembic stamp head`
  over the existing DB. **NEVER drop or recreate tables that hold data.**
- **Tests written alongside the code** (bootcamp requirement, never cut): each module is done
  when its tests pass. The `.feature` files in `docs/gherkin/` are the specification for each
  suite; turn every Scenario into at least one test. Authenticate in tests via
  `POST /api/auth/test-token`.
- **Git**: GitFlow. One `feature/<module>` branch per module; small commits in English
  (`feat:`, `fix:`, `test:`, `docs:` convention).

## 6. Per-module workflow (in this order)

1. Read `docs/api-contract.md` (the module's section) and `docs/gherkin/<module>.feature`.
2. Check the reference implementation in `reference/express-backend/src/modules/<module>/`
   (validation = what Zod validates; service = the real business rules).
3. Write: models → schemas → service → router → register the router in `main.py`.
4. Write the module's tests and run them until they pass.
5. Verify against the contract: exact routes, envelope, error codes.
6. Summarize what you did and which decisions you made, for human review.

## 7. What NOT to do

- Do not change routes, response shapes or status codes of the contract **on your own**
  (use the "Controlled contract changes" process from section 2).
- Do not port the N8N webhook as it exists in the Express `route-calls.controller.ts`. The
  Telegram notification DOES exist (D9, task T-49, P2), but it is implemented differently:
  `shared/notifications.py` calling the Telegram Bot API directly with httpx
  (`sendPhoto` with `photo=<public cover image URL>` + `caption` when there is an image;
  `sendMessage` otherwise), invoked with BackgroundTasks from the service — never from a router.
  Requirements: clean the Tiptap HTML out of the caption (convert `<strong>`→`<b>`, `<em>`→`<i>`,
  strip `<p>` and any other tags Telegram does not support), truncate the caption to 1024
  characters with the website link at the end, short timeout (2-3s) and error capture: a Telegram
  failure must NEVER break route-call creation. Add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
  as optional settings in `core/config.py` and `.env.example`.
- Do not use async/await with SQLAlchemy or asyncpg (D7).
- Do not use the Supabase anon key on the server; only the service role key from the .env (D6).
- Do not touch the `docs/` or `reference/` folders (they are the spec and read-only reference).
- Do not add heavy dependencies without justifying them.
- Do not invent fields or endpoints that are not in the contract.

---

## Per-module prompt template (paste this in each Claude Code session)

```
Let's migrate the <MODULE> module following CLAUDE.md.

1. Read docs/api-contract.md (the <MODULE> section) and docs/gherkin/<MODULE>.feature.
2. Check the reference implementation in reference/express-backend/src/modules/<MODULE>/
   (especially *.validation.ts and *.service.ts for the real business rules).
3. Implement in this order: models (if missing) → schemas → service → router → register in main.py.
4. Write the module's tests (at least one test per Scenario in the .feature file) and run them.
5. When done: show me a summary of the endpoints implemented, the business rules applied and
   the test results. If the contract and the reference code contradict each other on anything,
   STOP and ask me before deciding.
```
