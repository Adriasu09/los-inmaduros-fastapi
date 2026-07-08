# Los Inmaduros Rollers Madrid — API Contract

> **Single source of truth** for the Express → FastAPI migration. The FastAPI backend must honor
> this contract (routes and shapes) so the frontend keeps working without changes.
> Obtained by reverse-engineering the Express V2 backend and verified against the frontend.
> Version: Phase 4 closed · decisions D1–D9 · code freeze on July 25.

## Contract conventions

- **Base URL:** everything hangs under `/api` (the frontend uses `NEXT_PUBLIC_API_URL`, e.g. `http://localhost:4000/api`).
- **Envelope:** every response has the shape `{ "success": bool, "data": ..., "message"?: str, "count"?: int, "pagination"?: {...} }`. The frontend depends on it (`ApiResponse<T>`). **Do not change.**
- **Error envelope** (approved 2026-07-07, deliberate improvement over Express): error responses are
  `{ "success": false, "message": str }`, plus `"errors": { "<field>": ["<msg>", ...] }` on validation
  errors (400). Express used the field `error`, but the frontend's `ApiErrorResponse` reads `message`
  — so with Express the real error texts never reached the UI (it always fell back to a generic
  "An error occurred"). Emitting `message` fixes that latent bug with ZERO frontend changes.
- **Auth:** Clerk. JWT in `Authorization: Bearer <token>`. In FastAPI: `get_current_user` dependency.
- **Protection levels:** *Public* (no token) · *Auth* (logged in) · *Auth + ADMIN* (admin role) ·
  *(in service)* = the fine-grained permission (organizer / owner / organizer-or-admin) is checked
  in the service layer returning 403, not in the route.
- **Status codes:** 400 validation/invalid state · 401 no identity · 403 no permission · 404 not found · 409 conflict/duplicate.

## Infrastructure / global

| Method | Route | What it does | Auth |
|---|---|---|---|
| GET | `/health` | Healthcheck + DB ping | Public |
| GET | `/api-docs` | API docs (in FastAPI: automatic OpenAPI) | Public |
| GET | `/api-docs.json` | OpenAPI spec as JSON | Public |

## auth — `/api/auth` (with `authLimiter`)

| Method | Route | What it does | Auth |
|---|---|---|---|
| POST | `/api/auth/test-token` | **DEV ONLY** (D1): generates a Clerk JWT from an email (404 in production; 400 without email; 404 if the email does not exist in Clerk) | Public |

## routes — `/api/routes`

| Method | Route | What it does | Auth |
|---|---|---|---|
| GET | `/api/routes` | Lists all predefined routes, ordered by name, with average rating and counts (_count) | Public |
| GET | `/api/routes/:slug` | Detail by slug (+ paginated reviews via `reviewsPage`/`reviewsLimit`, limited ACTIVE-only photos, average rating) | Public |

**Read-only** module: routes are seed data; there is no CRUD through the API in the MVP.

## route-calls — `/api/route-calls`

| Method | Route | What it does | Auth |
|---|---|---|---|
| POST | `/api/route-calls` | Creates a route call (predefined or custom route); born `SCHEDULED` | Auth (+ `creationLimiter`) |
| GET | `/api/route-calls` | List with filters (`status`, `upcoming`, `pace`, `routeId`, `organizerId`, `month` YYYY-MM) + pagination | Public |
| GET | `/api/route-calls/:id` | Detail (organizer, meeting points, paces, CONFIRMED attendee count) | Public |
| PUT | `/api/route-calls/:id` | Edits `title`/`description`/`image`/`dateRoute`/`paces`. Organizer only; not if `COMPLETED`/`CANCELLED` | Auth (organizer, in service) |
| PATCH | `/api/route-calls/:id/cancel` | Cancels → `CANCELLED` (record is kept). Not if already cancelled or completed | Auth (organizer or ADMIN, in service) |
| DELETE | `/api/route-calls/:id` | Hard delete. **Only if it has no attendances** (otherwise → 400 "cancel it instead"). Cascades over meeting points | Auth (organizer or ADMIN, in service; UI shows it to ADMIN only, D4) |

Creation rules: future `dateRoute` required; without `routeId` → `title` required; `paces` 1–7
from the enum (ROCA, CARACOL, GUSANO, MARIPOSA, EXPERIMENTADO, LOCURA_TOTAL, MIAUCORNIA);
`meetingPoints` 1–2 with exactly one PRIMARY (location, when present, must be a Google Maps URL).

## attendances

Nested under `/api/route-calls/:routeCallId/attendances`:

| Method | Route | What it does | Auth |
|---|---|---|---|
| GET | `.../attendances/check` | Am I attending? → `isAttending` (true only if CONFIRMED) | Auth |
| POST | `.../attendances` | Join → CONFIRMED. 400 if the route call is CANCELLED/COMPLETED; 409 if already joined; reactivates a previously CANCELLED one | Auth (+ `creationLimiter`) |
| DELETE | `.../attendances` | Cancels my attendance → CANCELLED (record kept). 404 if I have none; 400 if already cancelled | Auth |
| GET | `.../attendances` | Lists attendees (CONFIRMED only, with basic user data) | Public |

Flat under `/api/attendances`:

| Method | Route | What it does | Auth |
|---|---|---|---|
| GET | `/api/attendances/my-attendances` | My CONFIRMED attendances (with route-call and organizer data) | Auth |

Uniqueness per (routeCallId, userId); re-joining reuses the same record.

## reviews

Nested under `/api/routes/:routeId/reviews` (by the route's **UUID id**, not its slug):

| Method | Route | What it does | Auth |
|---|---|---|---|
| GET | `/api/routes/:routeId/reviews` | Route's reviews, paginated, newest first. 404 if the route does not exist | Public |
| POST | `/api/routes/:routeId/reviews` | Creates a review: integer `rating` 1–5 required, optional `comment` ≤500. One per user and route (repeat → 409). Attendance NOT required | Auth (+ `creationLimiter`) |

Flat under `/api/reviews`:

| Method | Route | What it does | Auth |
|---|---|---|---|
| GET | `/api/reviews/my-reviews` | My reviews (with their route), newest first | Auth |
| PUT | `/api/reviews/:reviewId` | Edits rating/comment. **Author only** | Auth (author, in service) |
| DELETE | `/api/reviews/:reviewId` | Deletes. **The author or an ADMIN** (D5: improvement over Express, which only allowed the author) | Auth (author or ADMIN, in service) |

## favorites

Nested under `/api/routes/:routeId/favorites`:

| Method | Route | What it does | Auth |
|---|---|---|---|
| POST | `/api/routes/:routeId/favorites` | Adds to favorites. 404 if the route does not exist; 409 if already favorited | Auth |
| DELETE | `/api/routes/:routeId/favorites` | Removes from favorites. 404 if it was not favorited | Auth |

Flat under `/api/favorites`:

| Method | Route | What it does | Auth |
|---|---|---|---|
| GET | `/api/favorites` | My favorite routes, newest first | Auth |
| GET | `/api/favorites/check/:routeId` | Boolean `isFavorite`. 404 if the route does not exist | Auth |

Uniqueness per (routeId, userId).

## photos — `/api/photos`

| Method | Route | What it does | Auth |
|---|---|---|---|
| POST | `/api/photos` | Uploads a photo (multipart, field `image`; optional `caption` ≤500; required `context`). Born `ACTIVE` (D2) | Auth (+ `creationLimiter`) |
| GET | `/api/photos` | Listing with filters (`context`, `routeId`, `routeCallId`, `status`, pagination); ACTIVE only by default | Public |
| GET | `/api/photos/my-photos` | My photos (every status except DELETED, with their moderation status) | Auth |
| GET | `/api/photos/pending-review` | Moderation queue (ACTIVE not yet reviewed) | Auth + ADMIN |
| PATCH | `/api/photos/:id/approve` | Marks as reviewed (stays visible) | Auth + ADMIN |
| PATCH | `/api/photos/:id/reject` | → REJECTED (hidden), accepts a moderation note. 400 if already DELETED | Auth + ADMIN |
| DELETE | `/api/photos/:id` | Soft-delete → DELETED (record kept) | Auth (author or ADMIN, in service) |
| GET | `/api/photos/routes/:slug/gallery` | A route's gallery (ACTIVE only). **Note: hangs under /api/photos** (P2, D3) | Public |
| GET | `/api/photos/route-calls/:id/gallery` | A route call's gallery (ACTIVE only) (P2, D3) | Public |
| PATCH | `/api/photos/route-calls/:id/cover-photo` | Route call cover photo (multipart). Organizer only | Auth (organizer, in service) |

**Upload permissions by `context`:**
- `ROUTE_GALLERY` (requires `routeId`): any registered user; the route must exist.
- `ROUTE_CALL_GALLERY` (requires `routeCallId`): only attendees with a CONFIRMED attendance.
- `ROUTE_CALL_COVER` (requires `routeCallId`): the organizer only.
- Never `routeId` and `routeCallId` at the same time (400).

Statuses: ACTIVE, FLAGGED (reserved, unused), REJECTED, DELETED.

## config — `/api/config`

| Method | Route | What it does | Auth |
|---|---|---|---|
| GET | `/api/config` | Constants: predefined `meetingPoints`, `routePaces` (emoji+label+description), `routeLevels` (BEGINNER, INTERMEDIATE, ADVANCED, EXPERT) | Public |

## Cross-cutting business rules

- **route-calls:** born SCHEDULED; `SCHEDULED → ONGOING → COMPLETED` is driven by a scheduler
  (APScheduler). The only human transition is cancelling. There is no way out of COMPLETED/CANCELLED.
- **Cancel ≠ delete:** cancelling changes the status and keeps the record; deleting is destructive
  and blocked when there are attendees.
- **Photo moderation (D2):** publish-then-moderate. Public galleries show ACTIVE only.
- **Route average rating:** computed from the reviews, not stored.
- **Telegram notification (D9):** on route-call creation, optional and env-gated; fired in the
  background and never allowed to break the creation itself.

## Decision log

| ID | Decision |
|---|---|
| D1 | Replicate `POST /api/auth/test-token` (dev-only) for Postman/pytest testing |
| D2 | Photo moderation = publish-then-moderate for the MVP |
| D3 | Gallery endpoints: migrated last within the photos module (P2) |
| D4 | Route-call delete: ADMIN-only in the UI; the backend keeps organizer-or-admin |
| D5 | Review delete: author or ADMIN (improvement over Express); editing stays author-only |
| D6 | No native Clerk↔Supabase integration, no RLS; Storage uses the service role key server-side |
| D7 | Synchronous backend: `def` routes + sync SQLAlchemy (no asyncpg/AsyncSession) |
| D8 | Frontend: pnpm yes; Vite as build no (Next ships Turbopack); Vitest + Testing Library (P2) |
| D9 | Telegram notification without N8N: direct Bot API (`sendPhoto`/`sendMessage`) in `shared/notifications.py` with BackgroundTasks; P2, disabled by default; cleans Tiptap HTML and truncates the caption to 1024 chars |

## Target stack

| Piece | Express V2 (current) | FastAPI (target) |
|---|---|---|
| Framework | Express 5 + TypeScript | FastAPI (Python) |
| ORM + migrations | Prisma | SQLAlchemy 2.0 (sync) + Alembic |
| Validation | Zod | Pydantic v2 |
| Auth | Clerk (`@clerk/express`) | Clerk (`clerk-backend-api`, `authenticate_request`) |
| Storage | Supabase Storage + multer (anon key) | supabase-py + `UploadFile` (service role key) |
| Scheduler | node-cron | APScheduler |
| Rate limiting | express-rate-limit | slowapi |
| Docs | Swagger | Automatic OpenAPI |
| Tests | Jest (~40% coverage, some broken) | pytest + httpx (broad coverage, a requirement) |
| DB | PostgreSQL (Supabase) | PostgreSQL (Supabase) — same one, unchanged |
