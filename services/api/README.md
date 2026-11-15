# OddVex API

Backend for OddVex, a sports-betting **intelligence** product: odds comparison, player-prop
research, betting math, bet tracking and a rule-based assistant. It never accepts, places or
facilitates wagers and never moves money.

**All sports data in this build is synthetic.** Teams, players, sportsbooks, prices and
statistics are fictional and generated in-process. No real data provider is connected, no
network calls are made at runtime, and every data response carries `data_mode: "synthetic"`.

## Run

Requires Python 3.13.

```bash
cd services/api
python -m venv .venv && .venv/bin/pip install -e ".[dev]"   # or: uv venv && uv pip install -e ".[dev]"
.venv/bin/alembic upgrade head                 # optional locally: tables are auto-created outside production
.venv/bin/python scripts/seed_demo.py          # optional demo account
.venv/bin/uvicorn oddvex_api.main:app --reload --port 8000
```

- Interactive docs: http://localhost:8000/docs (disabled in production)
- Demo login after seeding: `demo@oddvex.test` / `oddvex-demo-2026` (override with
  `ODDVEX_DEMO_PASSWORD`). Development convenience only.
- Docker: `docker build -t oddvex-api .` then run with `DATABASE_URL` and `ODDVEX_JWT_SECRET`
  set. The image runs `alembic upgrade head` and then uvicorn on port 8000 as a non-root user.

## Test and lint

```bash
.venv/bin/pytest                                  # temp SQLite database per test
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/mypy src                                # optional
.venv/bin/python scripts/export_openapi.py        # regenerate openapi.json after any schema change
.venv/bin/python scripts/export_openapi.py --check
```

To run the **whole suite** against PostgreSQL, point `ODDVEX_TEST_DATABASE_URL` at a
**throwaway** database. Every table in it is dropped before each test.

```bash
ODDVEX_TEST_DATABASE_URL=postgresql+psycopg://oddvex:oddvex@localhost:5432/oddvex_test .venv/bin/pytest
```

Every test that goes through the app then uses that database. Tests that are about SQLite files
(the Alembic CLI, table auto-creation) keep using a temporary SQLite file, and the
`0001 -> 0002` upgrade/downgrade test runs once on SQLite and once more on the external database.
The database must use UTF-8 encoding (the official `postgres` image does; a cluster created with
`initdb` under the `C` locale needs `-E UTF8`).

In GitHub Actions, add a `postgres:16` service with `POSTGRES_USER: oddvex`,
`POSTGRES_PASSWORD: oddvex`, `POSTGRES_DB: oddvex_test`, port `5432:5432` and a `pg_isready`
health check, then run the command above with `working-directory: services/api`.

`openapi.json` is committed. CI regenerates it and fails on a diff, and `packages/types` is
generated from it, so re-export (and run `pnpm types:generate` at the repo root) whenever a
route or response model changes. Treat the schema as a contract: add fields, do not rename them.

## Configuration

Everything comes from the environment (a local `.env` file is also read). See `.env.example`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `ODDVEX_ENV` | `development` | `development`, `test` or `production` |
| `DATABASE_URL` | `sqlite:///./oddvex_dev.db` | SQLAlchemy URL. `postgres://` and `postgresql://` use psycopg 3 |
| `ODDVEX_JWT_SECRET` | dev-only value | HS256 signing secret. **Production refuses to start with the default or a secret shorter than 32 characters** |
| `ODDVEX_JWT_TTL_MINUTES` | `60` | Access token lifetime |
| `ODDVEX_CORS_ORIGINS` | `http://localhost:3000` | Comma-separated CORS allowlist. `*` is rejected in production |
| `ODDVEX_TRUST_PROXY` | `false` | Use the last `X-Forwarded-For` entry (the one your proxy appends) as the rate-limit client IP. Only behind exactly one trusted proxy |
| `ODDVEX_RATE_LIMIT_ENABLED` | `true` | Turn the limiter off (tests) |
| `ODDVEX_RATE_LIMIT_AUTH_PER_MINUTE` | `10` | Per-IP limit shared by register and login |
| `ODDVEX_RATE_LIMIT_ASSISTANT_PER_MINUTE` | `20` | Per-IP limit on the assistant |
| `ODDVEX_RATE_LIMIT_WINDOW_SECONDS` | `60` | Sliding window length |
| `ODDVEX_STALE_LIVE_SECONDS` | `120` | Live quotes older than this are stale |
| `ODDVEX_STALE_PREGAME_SECONDS` | `900` | Pre-game quotes older than this are stale |
| `ODDVEX_SYNTHETIC_SEED` | `20260101` | Seed of the synthetic data generator |
| `ODDVEX_ADMIN_EMAILS` | empty | Emails that get the `admin` role at registration or next login |
| `ODDVEX_AUTO_SEED_DEMO` | `false` | Seed the demo account on startup. Ignored in production |
| `ODDVEX_DEMO_PASSWORD` | `oddvex-demo-2026` | Demo account password (documented dev default) |
| `ODDVEX_DB_AUTO_CREATE` | unset | Create tables on startup. On by default outside production, always off in production |
| `ODDVEX_SYNC_MAX_ATTEMPTS` | `3` | Fetch attempts per import run |
| `ODDVEX_MAX_BODY_BYTES` | `65536` | Largest request body accepted (minimum 1024). Larger requests get `413 payload_too_large` |
| `ODDVEX_LOG_LEVEL` | `INFO` | Log level |

## API

JSON, `snake_case`, ISO-8601 UTC timestamps, string ids. Everything is under `/v1` except
`/health`. List endpoints return bare JSON arrays. Probabilities, holds, ROI and CLV are
fractions (`0.05` is 5%) unless the field name ends in `_percent`. Money is a JSON number
rounded to cents.

Errors always use one envelope, including validation errors and 404s:

```json
{"error": {"code": "validation_error", "message": "Request validation failed", "details": [...]}}
```

| Group | Routes |
| --- | --- |
| Meta | `GET /health`, `GET /v1/meta`, `GET /v1/leagues`, `GET /v1/sportsbooks` |
| Events | `GET /v1/events`, `GET /v1/events/{id}`, `GET /v1/events/{id}/odds`, `GET /v1/events/{id}/line-history` |
| Players | `GET /v1/players`, `GET /v1/players/{id}`, `GET /v1/players/{id}/props`, `GET /v1/props` |
| Calculators | `POST /v1/quant/convert`, `/no-vig`, `/ev`, `/parlay`, `/clv` (each returns `steps`) |
| Auth | `POST /v1/auth/register`, `POST /v1/auth/login`, `GET /v1/me`, `DELETE /v1/me`, `POST /v1/me/password`, `GET /v1/me/export` |
| Bets | `GET/POST /v1/bets`, `GET /v1/bets/summary`, `POST /v1/bets/auto-settle`, `GET/PATCH/DELETE /v1/bets/{id}`, `POST /v1/bets/{id}/settle` |
| Watchlist | `GET/POST /v1/watchlist`, `GET /v1/watchlist/events`, `DELETE /v1/watchlist/{id}` |
| Sync | `GET /v1/sync/providers`, `GET/POST /v1/sync/connections`, `POST .../{id}/sync`, `GET .../{id}/runs`, `DELETE .../{id}?delete_data=` |
| Assistant | `POST /v1/assistant/query` |
| Admin | `GET /v1/admin/overview` |

Behaviour worth knowing:

- **Best price.** `is_best` and `best` only consider books that are `open` and not stale. For
  spread and total, prices are only compared between books on the consensus (most common)
  line. The consensus is the mean no-vig probability of those same books.
- **Finished events.** Their markets are reported as `unavailable` with no outcomes. Line
  history still runs up to the close.
- **Hit rate.** Historical frequency with a Wilson 95% interval. Games that land exactly on the
  line are pushes and are excluded from the sample. It is never presented as a prediction.
- **Bets.** `status` is `pending` or `settled`; `result` carries the outcome. Odds are accepted
  as American, decimal or fractional and stored as decimal. Every bet query is filtered by the
  authenticated user, so another user's bet id returns 404.
- **Bet list.** `GET /v1/bets` takes `status`, `sport`, `market` (any leg), `sportsbook` (exact,
  case-insensitive), `bet_type`, `sort` (`placed_at`, `stake`, `profit`, each with a `-` prefix
  for descending; default `-placed_at`), `limit` (1 to 1000, default 500) and `offset`. Pending
  bets have no profit and sort last either way. An unknown `sort` is a 422.
- **Structured legs.** A leg may carry `outcome_key` (`home`, `away`, `draw`, `over`, `under`)
  next to `event_id`, `market` and, for spread and total, `line`. A spread `line` is the handicap
  of the selected side. Such a leg is validated when the bet is created or its legs are replaced:
  the event must exist (`422 unknown_event`), offer the market (`422 market_not_available`) and
  the outcome must fit it (`422 invalid_selection`; `draw` only where the league is 3-way).
  `league` and `event_label` are filled in from the event when left out. Legs without
  `outcome_key` are free text, exactly as before, and `event_id` on them is not checked. Each leg
  reports `gradeable`.
- **Auto-settle.** `POST /v1/bets/auto-settle` looks at the caller's pending bets. A bet whose
  legs are all gradeable and whose events are all final is graded from the final scores and
  settled through the same code as a manual settle, with `settled_by: "auto"` (manual settles
  are `"user"`; bets imported already settled have `null`). Everything else is returned under
  `skipped` with `not_gradeable`, `event_not_final`, `event_unavailable` or
  `manual_result_required` (a bet with its own price where a leg pushed). Calling it again
  settles nothing new. Rules: `docs/QUANT_METHODOLOGY.md`.
- **Watchlist.** Teams, players and events, at most 200 per user. Adding validates the id
  against the provider (`404 not_found`), and adding the same thing twice returns the existing
  item with 200 instead of 201. Items embed the current `team`, `player` or `event`; when the
  provider no longer has it (an old event) the embed is null and `available` is false.
  `GET /v1/watchlist/events` lists live and upcoming events for watched teams, watched players'
  teams and directly watched events, live first.
- **Password change.** `POST /v1/me/password` takes `current_password` and `new_password`
  (10 to 128 characters, different from the current one) and returns a `TokenResponse` with a
  **new token** (200, not 204), because every token issued before the change is rejected with
  `401 invalid_token` from then on, including the one that made the request. A wrong current
  password is `400 invalid_credentials` with a neutral message. It shares the auth rate limit.
- **Data export.** `GET /v1/me/export` returns one JSON document (`format_version: 1`) with the
  profile, bets, watchlist, sync connections, import runs and the caller's own audit entries. It
  never contains the password hash. Each export is itself audited.
- **Sync.** Re-running an import never duplicates a bet: bets are keyed on user + provider +
  external bet id. A provider failure that survives the retries is recorded as a failed run and
  returned as `502 sync_failed` with `details.run_id` and `details.retryable`. Two imports of
  the same account at the same moment cannot both write: the one that loses the race gets
  `409 sync_conflict` (`details.retryable: true`), writes nothing, and can simply be retried.
- **Request size.** Bodies over `ODDVEX_MAX_BODY_BYTES` are refused with `413 payload_too_large`
  in the usual envelope, whether the size is declared or the body is streamed.
- **Account deletion.** `DELETE /v1/me` removes the user, bets, legs, watchlist, sync
  connections and import runs. The audit log keeps an entry with the opaque user id only.

## Architecture

A modular monolith. One process, one database.

```
src/oddvex_api/
  main.py            app factory, middleware, routers, OpenAPI post-processing
  config.py          settings from the environment; production safety checks
  quant/             pure betting math and grading. No I/O, no clock. Every number comes from here
  providers/         SportsDataProvider protocol, SyntheticProvider, vendor-payload normalizer
  board.py           read models: odds comparison, best price, consensus, prop research
  api/               public data routes, calculators, admin
  auth/              argon2id passwords, HS256 JWT, register/login/me, password change
  account/           data export
  bets/              tracker: schemas, service (settlement, auto-settlement, summary), routes
  watchlist/         watched teams, players and events
  sync/              SyncProvider protocol, MockSyncProvider, idempotent import
  assistant/         intent router, data tools, Explainer protocol + TemplateExplainer
  db/                SQLAlchemy 2 models, portable UTC datetime type, session factory
  errors.py middleware.py ratelimit.py cache.py logging_config.py deps.py
alembic/             migrations (0001: users, bets, bet_legs, sync_connections, sync_import_runs, audit_log;
                     0002: watchlist_items, users.token_version/password_changed_at, bets.settled_by,
                     bet_legs.outcome_key)
scripts/             export_openapi.py, seed_demo.py
docs/QUANT_METHODOLOGY.md
```

- Routes are thin. Math lives in `quant/`, read models in `board.py`, domain rules in each
  module's `service.py`.
- The provider and sync contracts are `Protocol`s, so a licensed data vendor or a real
  account-linking provider can be added without touching routes. Provider records carry
  `provider`, `provider_id` and `fetched_at`.
- Cross-cutting: request id on every response and log line, one JSON log line per request,
  security headers, CORS allowlist, request body size limit, in-memory per-IP sliding-window
  rate limit, audit log for auth events, password changes, bet create/settle/auto-settle/delete,
  watchlist changes, sync, data export and account deletion.

## What is synthetic or mocked

| Thing | Status |
| --- | --- |
| Leagues, teams, players, sportsbooks, events, scores | Synthetic. Fictional names, seeded, relative to the current time so there are always live, upcoming and final events |
| Odds, lines, line history, prop offers, game logs | Synthetic. A simple internally consistent model with a margin and noise. No book or prop has a real edge |
| Stale / suspended / unavailable books | Simulated on purpose. One book (`oldmill`) is always stale |
| Sportsbook sync | `MockSyncProvider` only: a fictional account with a fixed bet history and a simulated failure switch. No credentials, no real sportsbook |
| Assistant | Keyword/regex intent router and templates. **No language model is connected** |
| `data/fixtures/*.json` | Synthetic vendor-format payloads for the provider-normalization contract tests |
| Demo account | Seeded sample bets, development only. Four of the pending ones have structured legs on already finished synthetic events, so auto-settle has something to settle |

## Limitations

- No real odds, scores or statistics. Nothing here should be used to make a betting decision.
- Rate limiting and caching are in process memory. With several workers each has its own
  counters; move them to a shared store before scaling out.
- JWT access tokens only: no refresh tokens, no email verification, no password reset (a
  forgotten password cannot be recovered), no per-session logout. Tokens are revoked in two
  cases only: changing the password invalidates every earlier token, and deleting the account
  invalidates all of them.
- Auto-settlement grades full-game moneyline, spread and total from the provider's final score.
  Props, futures, half results, voids and cash-outs stay manual, and the score is synthetic.
  It runs when the client calls it; there is no background job.
- The watchlist stores provider ids. A watched event the provider no longer serves stays on the
  list as `available: false` until the user removes it.
- The data export is built in memory in one response; fine for a personal bet history, not
  designed for very large accounts.
- Age is a self-attestation checkbox (`age_confirmed`), not verification.
- Odds are not persisted; they are generated on request. The `providers` contract is where an
  `odds_snapshots` table would attach.
- Bets are single-currency numbers with no currency code.
- The Docker image and the PostgreSQL path are covered by configuration and tests described
  above, not by a production deployment. Deploying is a Founder approval gate.
- Migrations run on container start. That is fine while they are additive; a destructive
  migration needs Founder approval first (see `PROJECT_CONSTITUTION.md`).
