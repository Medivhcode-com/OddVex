# OddVex API

Backend for OddVex, a sports-betting **intelligence** product: odds comparison, player-prop
research, betting math, bet tracking with analytics, a market-discrepancy ("value") screen,
alerts with in-app notifications, a rule-based assistant and, behind a feature flag that is
off by default, a community for discussing research. It never accepts, places or
facilitates wagers and never moves money. **There is no billing and no payment code, and no
email is ever sent**: plans are set by an administrator and emails are written to a table
(see [What is stubbed](#what-is-stubbed-no-billing-no-real-email)).

**All sports data in this build is synthetic.** Teams, players, sportsbooks, prices and
statistics are fictional and generated in-process. No real data provider is connected, no
network calls are made at runtime, and every data response carries `data_mode: "synthetic"`.

## Run

Requires Python 3.13.

```bash
cd services/api
python -m venv .venv && .venv/bin/pip install -e ".[dev]"   # or: uv venv && uv pip install -e ".[dev]"
.venv/bin/alembic upgrade head                 # optional locally: tables are auto-created outside production
.venv/bin/python scripts/seed_demo.py          # optional demo account (bets, alert rules, notifications)
ODDVEX_ADMIN_EMAILS=admin@oddvex.test .venv/bin/python scripts/seed_demo.py   # ...and an administrator
.venv/bin/python scripts/seed_demo.py --with-community   # ...and fictional community profiles (turns the two community flags on in that database)
.venv/bin/python scripts/evaluate_alerts.py    # optional: evaluate every user's alert rules once
.venv/bin/python scripts/grade_picks.py        # optional: grade pending community picks once
.venv/bin/uvicorn oddvex_api.main:app --reload --port 8000
```

- Interactive docs: http://localhost:8000/docs (disabled in production)
- Demo login after seeding: `demo@oddvex.test` / `oddvex-demo-2026` (override with
  `ODDVEX_DEMO_PASSWORD`). Development convenience only. The demo user's email counts as
  verified.
- Administrator: there is no default one. `scripts/seed_demo.py` creates `admin@oddvex.test`
  (same password, email counted as confirmed) **only** when `ODDVEX_ADMIN_EMAILS` lists that
  address. Any other listed address becomes an administrator once its email is verified, and
  never before. Where no confirmation link can be followed (production), the operator runs
  `python scripts/bootstrap_admin.py --email <address>` (see "Admin role" below).
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
`0001 -> 0002`, `0002 -> 0003`, `0003 -> 0004` and `0004 -> 0005` upgrade/downgrade tests run
once on SQLite and once more on the external database. One test (two concurrent alert evaluations creating a single notification)
needs real concurrent writers and only runs against PostgreSQL.
The database must use UTF-8 encoding (the official `postgres` image does; a cluster created with
`initdb` under the `C` locale needs `-E UTF8`). A throwaway local cluster is enough, for example
`initdb -D /tmp/pg -E UTF8 --locale=C -U oddvex --auth=trust`, `pg_ctl -D /tmp/pg -o "-p 54329" start`,
`createdb -p 54329 -U oddvex oddvex_test`: the `C` locale is the one where SQL `lower()` only
folds ASCII, which the case-insensitive filters are tested against.

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
| `ODDVEX_TRUST_PROXY` | `false` | Use the last `X-Forwarded-For` entry (the one your proxy appends) as the client IP for rate limiting, for the login lockout's client network and for audit rows. Only behind exactly one trusted proxy |
| `ODDVEX_RATE_LIMIT_ENABLED` | `true` | Turn the limiter off (tests) |
| `ODDVEX_RATE_LIMIT_AUTH_PER_MINUTE` | `10` | Per-IP limit shared by register, login and password change |
| `ODDVEX_RATE_LIMIT_ASSISTANT_PER_MINUTE` | `20` | Per-IP limit on the assistant |
| `ODDVEX_RATE_LIMIT_WINDOW_SECONDS` | `60` | Sliding window length |
| `ODDVEX_ACCOUNT_LIMIT_WINDOW_SECONDS` | `900` | Window of the per-account limits below |
| `ODDVEX_LOGIN_MAX_FAILURES` | `8` | Failed logins for one email from one client network (an IPv4 address, or the /64 prefix of an IPv6 address) inside that window before further attempts for that email from that network get `429`. Other networks are not affected |
| `ODDVEX_LOGIN_MAX_FAILURES_PER_EMAIL` | `50` | Failed logins for one email from all networks together inside that window before every attempt for that email gets `429`. For guessing spread over many addresses |
| `ODDVEX_EMAIL_REQUESTS_PER_WINDOW` | `3` | Verification emails per user and password-reset emails per address inside that window |
| `ODDVEX_EMAIL_PROVIDER` | `outbox` | `outbox`: write emails to the `email_outbox` table, send nothing. `resend`: a stub; the app refuses to start (`NotImplementedError`). Real email needs Founder approval |
| `ODDVEX_WEB_BASE_URL` | `http://localhost:3000` | Base of the links in emails (`/verify-email?token=`, `/reset-password?token=`) |
| `ODDVEX_EMAIL_VERIFICATION_TTL_HOURS` | `24` | Lifetime of an email confirmation link |
| `ODDVEX_PASSWORD_RESET_TTL_MINUTES` | `60` | Lifetime of a password reset link |
| `ODDVEX_STALE_LIVE_SECONDS` | `120` | Live quotes older than this are stale |
| `ODDVEX_STALE_PREGAME_SECONDS` | `900` | Pre-game quotes older than this are stale |
| `ODDVEX_SYNTHETIC_SEED` | `20260101` | Seed of the synthetic data generator |
| `ODDVEX_ADMIN_EMAILS` | empty | The addresses that may hold the `admin` role. Listing an address gives nobody the role by itself: an account gets it only when its address is listed **and** verified, in every environment. An address taken off the list loses it at its next login or token use. `scripts/bootstrap_admin.py` makes a listed address an administrator where nothing can be verified through the API; the seed script creates `admin@oddvex.test` only if it is listed |
| `ODDVEX_AUTO_SEED_DEMO` | `false` | Seed the demo account on startup. Ignored in production |
| `ODDVEX_DEMO_PASSWORD` | `oddvex-demo-2026` | Demo account password (documented dev default) |
| `ODDVEX_DB_AUTO_CREATE` | unset | Create tables on startup. On by default outside production, always off in production |
| `ODDVEX_SYNC_MAX_ATTEMPTS` | `3` | Fetch attempts per import run |
| `ODDVEX_MAX_BETS_PER_USER` | `5000` | Most bets one account can hold, manual and imported together. At the cap `POST /v1/bets` answers `409 bet_limit_reached` and an import stops adding |
| `ODDVEX_RATE_LIMIT_USER_WRITES_PER_MINUTE` | `120` | Bet and sync writes one user can make in a minute, from any address |
| `ODDVEX_RATE_LIMIT_USER_WRITES_PER_DAY` | `2000` | The same, in 24 hours (counted in hourly buckets) |
| `ODDVEX_RATE_LIMIT_EXPORT_PER_HOUR` | `10` | `GET /v1/me/export` requests one user can make in an hour |
| `ODDVEX_RATE_LIMIT_USER_STREAMS_AT_ONCE` | `8` | Streamed responses (`GET /v1/bets` and the export) one user can have in progress at the same moment |
| `ODDVEX_ALERT_EVAL_MIN_SECONDS` | `30` | Minimum seconds between two alert evaluations triggered by one user reading their notifications. `0` evaluates on every read (tests) |
| `ODDVEX_COMMUNITY_PICKS_PER_DAY` | `20` | Community picks one user can post in 24 hours |
| `ODDVEX_COMMUNITY_COMMENTS_PER_HOUR` | `30` | Community comments one user can post in an hour |
| `ODDVEX_COMMUNITY_REPORTS_PER_HOUR` | `10` | Reports one user can file in an hour |
| `ODDVEX_COMMUNITY_FOLLOWS_PER_HOUR` | `60` | New follows one user can make in an hour |
| `ODDVEX_COMMUNITY_GRADE_MIN_SECONDS` | `15` | Minimum seconds between two grading passes triggered by reading the community. `0` grades on every read (tests) |
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
| Meta | `GET /health`, `GET /v1/meta`, `GET /v1/leagues`, `GET /v1/sportsbooks`, `GET /v1/flags` |
| Events | `GET /v1/events`, `GET /v1/events/{id}`, `GET /v1/events/{id}/odds`, `GET /v1/events/{id}/line-history` |
| Players | `GET /v1/players`, `GET /v1/players/{id}`, `GET /v1/players/{id}/props`, `GET /v1/props` |
| Calculators | `POST /v1/quant/convert`, `/no-vig`, `/ev`, `/parlay`, `/clv` (each returns `steps`) |
| Value | `GET /v1/value` |
| Auth | `POST /v1/auth/register`, `POST /v1/auth/login`, `POST /v1/auth/logout`, `GET /v1/me`, `DELETE /v1/me`, `POST /v1/me/password`, `GET /v1/me/export`, `GET /v1/me/entitlements` |
| Email flows | `POST /v1/auth/verify-email/request`, `POST /v1/auth/verify-email/confirm`, `POST /v1/auth/password-reset/request`, `POST /v1/auth/password-reset/confirm` |
| Alerts | `GET/POST /v1/alerts`, `POST /v1/alerts/evaluate`, `PATCH/DELETE /v1/alerts/{id}` |
| Notifications | `GET /v1/notifications`, `GET /v1/notifications/unread-count`, `POST /v1/notifications/{id}/read`, `POST /v1/notifications/read-all`, `DELETE /v1/notifications/{id}` |
| Preferences | `GET/PUT /v1/me/notification-preferences`, `GET/PUT /v1/me/stake-reminder` |
| Bets | `GET/POST /v1/bets`, `GET /v1/bets/summary`, `GET /v1/bets/analytics`, `POST /v1/bets/auto-settle`, `GET/PATCH/DELETE /v1/bets/{id}`, `POST /v1/bets/{id}/settle` |
| Watchlist | `GET/POST /v1/watchlist`, `GET /v1/watchlist/events`, `DELETE /v1/watchlist/{id}` |
| Sync | `GET /v1/sync/providers`, `GET/POST /v1/sync/connections`, `POST .../{id}/sync`, `GET .../{id}/runs`, `DELETE .../{id}?delete_data=` |
| Assistant | `POST /v1/assistant/query` |
| Community (flag `community`) | `GET /v1/community/guidelines`, `PUT/GET /v1/community/profile`, `GET /v1/community/profiles/{handle}`, `POST/GET /v1/community/picks`, `GET/DELETE /v1/community/picks/{id}`, `GET /v1/community/feed`, `PUT/DELETE /v1/community/picks/{id}/like`, `POST/GET /v1/community/picks/{id}/comments`, `DELETE /v1/community/comments/{id}`, `POST/DELETE /v1/community/follows/{handle}`, `GET /v1/community/following`, `GET /v1/community/followers`, `PUT/DELETE /v1/community/blocks/{handle}`, `GET /v1/community/blocks`, `POST /v1/community/reports`, `GET /v1/community/leaderboard` (also flag `community_leaderboard`) |
| Admin | `GET /v1/admin/overview`, `GET /v1/admin/users`, `POST /v1/admin/users/{id}/suspend`, `POST /v1/admin/users/{id}/unsuspend`, `PUT /v1/admin/users/{id}/plan`, `POST /v1/admin/users/{id}/export`, `POST /v1/admin/users/{id}/delete`, `GET /v1/admin/flags`, `PUT /v1/admin/flags/{key}`, `GET /v1/admin/audit`, `GET /v1/admin/email-outbox` |
| Moderation (admin, flag `community`) | `GET /v1/admin/community/overview`, `GET /v1/admin/community/reports`, `POST /v1/admin/community/reports/{id}/resolve` |
| Dev (404 in production) | `GET /v1/dev/email-outbox/latest?to=` |

### Feature flags

Global on/off switches. The defaults live in code (`flags/catalog.py`); an administrator can
override one with `PUT /v1/admin/flags/{key}`, which stores a row in `feature_flags`. A stored
override always wins over the default, in every environment. Clients
read `GET /v1/flags` (public) → `{"flags": {"community": false, ...}}`. A route behind a flag
that is off answers `404 feature_disabled` with `details.flag`. In code:
`dependencies=[Depends(require_flag("key"))]`.

| Flag | Default | Gates |
| --- | --- | --- |
| `community` | off | Every `/v1/community/*` and `/v1/admin/community/*` route. **Off until user-generated content and moderation have been reviewed**: the threat model lists community as a review trigger, the guidelines need the same counsel review as the other policy pages, and someone has to be there to work the report queue. Turning it on is a launch decision, not a default |
| `community_leaderboard` | off | `GET /v1/community/leaderboard`, in addition to `community`. **Off until a responsible-gambling review approves leaderboards** (`docs/compliance/RESPONSIBLE_GAMBLING.md`, section 8: a review gate "before build"; the roadmap allows leaderboards "only if RG review approves"). A ranking of bettors is the part of a community most likely to push people to bet more, so it has its own switch |
| `value_screen` | on | `GET /v1/value` |
| `tracker_analytics` | on | `GET /v1/bets/analytics` |
| `email_flows` | on, **off when `ODDVEX_ENV=production`** | The four email-flow routes and the verification email queued at registration. It has no say in the admin role, which needs a verified address whether the flag is on or off. Off in production because no email provider is connected there: a reset request would be accepted and go nowhere. Turn it on in production only together with a real sender |
| `premium_gating` | off | Whether plan entitlements are enforced. **Turning it on is a pricing decision: Founder approval first** |

### Plans and entitlements (no billing)

`users.plan` is `free` or `premium`, default `free`, shown as `plan` on the user object.
**The only way a plan changes is an administrator calling `PUT /v1/admin/users/{id}/plan`.**
There is no purchase, checkout, subscription or payment route, no payment provider and no
price anywhere in this codebase. Pricing, payment terms and activating billing are Founder
approval gates (`PROJECT_CONSTITUTION.md`, section 3).

`GET /v1/me/entitlements` → `{plan, preview, features: {key: {enabled, limit}}}`, computed
from one catalog, `entitlements/catalog.py`: `alerts.max_active` (100), `value_screen`,
`tracker_analytics`, `odds_history_hours` (48). While `premium_gating` is off, `preview` is
`true` and every feature is enabled for everyone. The enforcement helper
`require_entitlement("feature")` exists and answers `403 plan_required` with
`details: {feature, plan, required_plan}` (403, not 402: nothing can be paid for), but **no
route uses it**, and the shipped catalog gives both plans the same thing, so nothing is gated
even with the flag on. Which feature is premium-only is a packaging decision nobody has made;
the tests exercise the helper with a premium-only feature that exists only in the tests.

Behaviour worth knowing:

- **Best price.** `is_best` and `best` only consider books that are `open` and not stale. For
  spread and total, prices are only compared between books on the consensus (most common)
  line. The consensus is the mean no-vig probability of those same books.
- **Stale quotes.** One rule (`Board.is_stale`) decides it for event markets, prop offers,
  the best moneyline in event lists and the best price used by alerts and community picks. A
  quote is stale when it is older than the threshold (`ODDVEX_STALE_PREGAME_SECONDS`,
  `ODDVEX_STALE_LIVE_SECONDS`), has no timestamp, has a timestamp more than 60 seconds in the
  future, or, in a live game, was last updated before the score last changed (the provider
  reports that time as `Event.score_updated_at`; without it only the age rule applies). A stale
  quote is still listed with `is_stale: true`, but it is never marked best and never counts
  in a consensus.
- **Prop board filters.** `GET /v1/props?league=&market=`: an unknown `league` is a 422. A
  `market` that is not a prop market of the chosen league (of any league without `league`) is
  answered with an empty list; a blank `market` means no filter. The board is cached for 10
  seconds per filter combination, keyed on the validated values, and nothing is cached for a
  value that does not exist.
- **Parlay calculator.** `POST /v1/quant/parlay` always returns the combined price. A combined
  probability is only computed when every active leg carries a `win_probability` and the
  active legs are from distinct known events (a single active leg needs no `event_id`).
  `probability_status` says which case applies, as one of `computed`,
  `needs_leg_probabilities`, `same_event_legs`, `unverified_legs`,
  `no_active_legs` (when several apply: `no_active_legs`, then `same_event_legs`, then
  `unverified_legs`, then `needs_leg_probabilities`). `probability_note` is the same reason
  as a sentence. `steps` ends with a combined-probability line only when one was computed.
- **Vendor payloads.** `providers/normalize.py` is the seam for a future data vendor; no feed
  is connected to it. It rejects a payload instead of guessing: a priced quote without
  `updatedAt`, a timestamp more than 60 seconds after the fetch time, a line or statistic
  that is not a finite number in plain decimal form, sides that do not fit the market, spread
  lines that are not mirrored, total lines that differ or are not above 0, negative or
  fractional scores, an identifier that is not a short text or a whole number, a text with
  control or invisible characters, a league the API does not serve, the same team on both
  sides, two keys for the same statistic, and values far outside any real range (a price
  beyond +/-1,000,000, a line or score beyond 1,000, a statistic beyond 100,000). A number
  sent as text may have 40 characters, a timestamp 64, and an identifier, a label or the
  clock of a live event 200; a longer one is rejected without being parsed, so a field of
  any size is refused at once. Rejections are counted per provider, record type and reason
  (`rejection_counts()`) and logged as `provider_payload_rejected` with those three values,
  never with the payload.
- **Finished events.** Their markets are reported as `unavailable` with no outcomes. Line
  history still runs up to the close.
- **Hit rate.** Historical frequency with a Wilson 95% interval. Games that land exactly on the
  line are pushes and are excluded from the sample. It is never presented as a prediction.
- **Bets.** `status` is `pending` or `settled`; `result` carries the outcome. Odds are accepted
  as American, decimal or fractional and stored as decimal. Every bet query is filtered by the
  authenticated user, so another user's bet id returns 404.
- **What a bet can hold.** Prices are stored with six decimal places and at most ten digits
  before the point, money in cents with at most twelve. A bet is rounded to that and checked
  completely before anything is written, on create, update, settle and import: a price (of a
  leg, of the bet, or a closing price) that would be stored as 1.000000 or less is
  `422 invalid_decimal_odds`; a price or a combined parlay price above 9999999999.999999 is
  `422 odds_out_of_range`; a stake that would be stored as 0.00 is `422 invalid_stake` (0.005
  still rounds up to 0.01); a stake and price, or a settlement, that would pay more than
  999999999999.99 is `422 payout_out_of_range`. Every write route builds its answer before it
  commits, so a request that ends in an error has stored nothing. A row written before these
  checks (a price of exactly 1.000000 or a stake of 0.00) still loads in the list, the
  summary, the analytics and the export: its price is read as the shortest price there is,
  1.000001 (shown as `decimal: 1.0`, `american: -100000000`), a stake of 0 has a potential
  payout and profit of 0, and no CLV is computed from such a price. It cannot be settled as
  it is (422); it can be edited or deleted. The rules are in `bets/storage.py`. A bet with
  its own price is not checked for the product of its leg prices; when that product (taken
  or closing) is above 9999999999.999999 the bet has no CLV (`clv: null`) and is left out of
  the CLV averages.
- **Bet cap.** An account holds at most `ODDVEX_MAX_BETS_PER_USER` bets (default 5,000), manual
  and imported together. At the cap `POST /v1/bets` answers `409 bet_limit_reached` with
  `details.max_bets`, like the watchlist and alert caps. Editing, settling and deleting still
  work. An import takes the provider's bets in order and stops adding at the cap: the run
  succeeds, its `error_message` says how many bets were left out and why (the number is also
  `fetched_count - imported_count - duplicate_count`), and a later import is offered them
  again. Creates and imports of one account that arrive together wait for each other on a
  row lock, so the cap is exact on PostgreSQL. SQLite (development) has no row locks: there,
  requests that arrive together can each see room, and the cap can be passed by as many
  bets as there are requests in progress at that moment.
- **Repeating a create safely.** `POST /v1/bets` takes an optional `client_request_id` (8 to 64
  characters from `A-Z a-z 0-9 _ -`). The first request with an id stores the bet and answers
  201. A later request from the same account with the same id answers 200 with the bet stored
  the first time: no second bet, audit entry or staking reminder, even if the repeated body
  differs and even when the retry arrives while the first request is still running (a unique
  index on `bets (user_id, client_request_id)` decides). That includes the case where the
  first request takes the account's last free place: the retry is answered with the stored
  bet, not with `409 bet_limit_reached`. A repeat is still a request: one whose body does not
  pass the request schema is a 422 and one over the write limit is a 429, like any other
  create. The id is not part of the response and is free again once the bet is deleted.
  Imported bets have none.
- **Write and export limits.** Bet writes (create, edit, delete, settle, auto-settle) and sync
  writes (connect, import, disconnect) share a limit per user id, whatever the address:
  `ODDVEX_RATE_LIMIT_USER_WRITES_PER_MINUTE` and `ODDVEX_RATE_LIMIT_USER_WRITES_PER_DAY`.
  `GET /v1/me/export` has its own, `ODDVEX_RATE_LIMIT_EXPORT_PER_HOUR`. Over a limit the answer
  is `429 rate_limited` with `Retry-After`. A request that passes the limit counts whether
  or not it then succeeds (a 422 or a 404 counts). A request refused by a ceiling is not
  counted by that ceiling; the per-minute ceiling is checked first, so a request the daily
  ceiling refuses has been counted for its minute. In memory, per process, and off with `ODDVEX_RATE_LIMIT_ENABLED=false`, like the other
  limiters. The dependency is `ratelimit.user_rate_limit("writes")`. These limits cover the
  bet and sync routes only: the other routes that write for a signed-in user (watchlist,
  alert rules, notifications, the staking reminder) have their caps on stored items but no
  per-user write limit yet.
- **In progress at once.** Two things are also limited by how many one account has running at
  the same moment, because each holds memory for as long as it runs. Streamed responses
  (`GET /v1/bets` and `GET /v1/me/export` together): at most
  `ODDVEX_RATE_LIMIT_USER_STREAMS_AT_ONCE` (default 8); a response counts from its start
  until it has been sent in full or the client has gone. Auto-settle: one per account; a call
  that arrives while another is still running is not started. Both answer
  `429 rate_limited` with `Retry-After: 1`. In memory, per process, and off with
  `ODDVEX_RATE_LIMIT_ENABLED=false` (`ratelimit.take_user_stream_slot`,
  `ratelimit.user_exclusive`).
- **Bet list.** `GET /v1/bets` takes `status`, `sport`, `market` (any leg), `sportsbook` (exact,
  case-insensitive for any script: see "Case-insensitive matching" below), `bet_type`, `sort` (`placed_at`, `stake`, `profit`, each with a `-` prefix
  for descending; default `-placed_at`), `limit` (1 to 1000, default 500) and `offset`. Pending
  bets have no profit and sort last either way. An unknown `sort` is a 422. The page is
  streamed: one statement decides which bets are on it and in what order (their ids), then
  the bets are read and sent 50 at a time, each batch in a database session of its own. The
  response is still one JSON array of `BetOut`, without a `Content-Length`. A request holds
  one batch in memory, not the page, and no database connection while the client reads. A
  bet deleted while its page is being sent is left out of that page. As with the export, a
  page whose batches cannot all be read ends without its closing bracket and does not
  parse; the status is already 200 by then.
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
  settles nothing new. One call settles at most 200 bets, oldest first, reading pending bets
  100 at a time; when it stops there with pending bets left unexamined the response carries
  `has_more: true` and the next call continues (the field is left out otherwise). One account
  runs one auto-settle at a time (see "In progress at once"). Rules:
  `docs/QUANT_METHODOLOGY.md`.
- **Summary and analytics.** `GET /v1/bets/summary` and `GET /v1/bets/analytics` read a few
  columns per bet and per leg (`bets.service.load_bet_facts`), never the mapped bets with
  their notes and selections, so their memory grows with the number of bets only.
- **Watchlist.** Teams, players and events, at most 200 per user. Adding validates the id
  against the provider (`404 not_found`), and adding the same thing twice returns the existing
  item with 200 instead of 201. Items embed the current `team`, `player` or `event`; when the
  provider no longer has it (an old event) the embed is null and `available` is false.
  `GET /v1/watchlist/events` lists live and upcoming events for watched teams, watched players'
  teams and directly watched events, live first.
- **Alert rules.** Owner-scoped, at most 100 active per user (`409 alerts_full`; 500 of any
  state). `POST /v1/alerts` takes a `kind` and that kind's fields, nothing else:

  | `kind` | Fields | Fires when |
  | --- | --- | --- |
  | `price_at_least` | `event_id`, `market` (moneyline, spread, total), `outcome_key`, `line` (spread and total only), `threshold`, `odds_format` (default american) | the best open, non-stale price for that outcome, among books quoting exactly that line, is at or above the threshold |
  | `line_move` | `event_id`, `market` (spread, total), `outcome_key`, `min_move` (points) | the consensus line is `min_move` or more away from `baseline_line`, the consensus line when the rule was armed, in either direction |
  | `game_start` | `event_id` or `team_id`, `minutes_before` (5 to 1440) | a matching upcoming event starts within that many minutes |
  | `game_final` | `event_id` or `team_id` | a matching event is final; the notification carries the score |

  The best price is `Board.best_price`, the same code the odds endpoint uses. The event must
  exist (`422 unknown_event`) and not be over (`422 event_not_open`; a `game_start` rule also
  needs it not to have started), the market and outcome must fit it (`422 market_not_available`,
  `422 invalid_selection`), a team must exist (`422 unknown_team`) and a `line_move` rule needs a
  current line to start from (`422 line_not_available`). An exact duplicate of an active rule
  returns that rule with 200. States: `active`; `triggered` (an event-scoped rule fired, once);
  `expired` (the event ended or disappeared first; a `game_final` rule only expires when the
  event disappears); `paused`. Team-scoped rules stay `active` and fire once per game.
  `PATCH` with `state: paused` pauses an active rule; `state: active` resumes a paused rule or
  re-arms a triggered one (a `line_move` rule then takes the current consensus line as its new
  baseline). Each rule has a `summary` and embeds the current `event` or `team`.
- **Alert evaluation. There is no background worker.** Rules are evaluated (a) when the user
  reads `GET /v1/notifications` or `GET /v1/notifications/unread-count`, at most once per
  `ODDVEX_ALERT_EVAL_MIN_SECONDS` per user, (b) when the client calls
  `POST /v1/alerts/evaluate`, which returns `{evaluated, fired, expired}`, and (c) when
  `scripts/evaluate_alerts.py` runs (every user with active rules; `--dry-run` saves nothing).
  In practice: **an alert fires when the user opens the app or the script runs, not at the
  moment the condition becomes true.** A price that touched the threshold and moved away between
  two evaluations is not noticed; a `game_start` rule nobody evaluated before the game began
  expires without a notification. Evaluation is idempotent, and a unique constraint on
  `(user_id, dedupe_key)`, where the key contains the rule id, makes two concurrent runs create
  one notification.
- **Notifications.** In-app only: no push, email or SMS. Delivery sits behind a
  `NotificationChannel` protocol with a single `InAppChannel`, so another channel can be added
  without touching the alert engine (adding one is a Founder approval gate). Kinds:
  `price_alert`, `line_move`, `game_start`, `game_final`, `bet_settled` (one per bet settled by
  `POST /v1/bets/auto-settle`), `sync_finished` (one per import run, succeeded or failed) and
  `stake_reminder`. Each has `title`, `body`, `href` (a web route such as
  `/app/games/{event_id}?market=spread` or `/app/tracker`) and a small `data` object. The list is
  newest first with `unread`, `limit` (1 to 100, default 50) and a `before` cursor
  (`next_before` of the previous page). At most 500 are kept per user; the oldest read ones are
  removed first. The wording is neutral and factual: no instruction to bet, no urgency, American
  prices with an explicit sign, no probabilities. `tests/test_notification_copy.py` enforces
  that with a banned-phrase scan of every template.
- **Notification preferences.** `GET/PUT /v1/me/notification-preferences` holds one in-app
  switch per kind under `in_app`, all on by default. `PUT` changes the kinds it is sent and
  leaves the others alone. A disabled kind creates no notification; alert rules still fire and
  change state. There are deliberately no push, email or quiet-hours settings: nothing would
  honor them yet.
- **Staking reminder. A reminder, not a limit.** `PUT /v1/me/stake-reminder` takes
  `{"weekly_stake_threshold": number | null}` (greater than 0, at most 1,000,000; `null` turns it
  off). `GET` adds `staked_this_week` (stakes of the user's bets whose `placed_at` is in the
  current ISO week, Monday to Sunday in UTC, void bets excluded), `week_start` and `exceeded`.
  When `POST /v1/bets` or a sync import takes the weekly total from below the threshold to at or
  above it, one `stake_reminder` notification is created for that week, stating the amount
  staked, the user's own threshold and how to reach the helpline (see "Helpline facts"
  below). **OddVex never blocks, rejects or delays a bet because of it: the bet is always
  saved.** At most one reminder per user and week, even if the threshold changes or the
  notification is deleted.
- **Helpline facts.** `oddvex_api/helpline.py` is the one place that spells out a helpline:
  the National Problem Gambling Helpline is 1-800-MY-RESET (1-800-697-3738), call, or text
  800GAM (800426); it is confidential and answers 24 hours a day, every day; it is not an
  emergency service, and in a crisis the numbers are 988 (the Suicide and Crisis Lifeline,
  call or text) and 911. The module also records the date the facts were verified
  (2026-11-19). The assistant, the staking reminder, the email footer and the community
  guidelines import their wording from it, and `tests/test_audit_helpline.py` fails if any
  other module spells a number out. The number that was the national helpline before
  2026-01-29 is run by the New Jersey council and is not given anywhere.
- **Assistant: responsible-gambling replies.** `POST /v1/assistant/query` checks every message
  against fixed patterns (`assistant/safeguards.py`) before any intent is matched, so a team
  name, a player name or "my record" in the same message cannot pull in betting data. The
  rows are those of `docs/compliance/RESPONSIBLE_GAMBLING.md`, section 5:

  | The message | The answer |
  | --- | --- |
  | Crisis or self-harm language ("I want to end it tonight", "I'd be better off not being here", "I took a bunch of pills") | Only support: 988 and 911 first, then the gambling helpline, and a line asking the user to tell someone they trust. One link, to `/responsible-gambling` |
  | The user says they are under 21 ("I'm 17", "I turn 21 in March", "I'm in high school", "I was born in 2009") | OddVex is for adults 21 and over; no betting information; the helpline |
  | Distress about gambling (cannot stop, lost more than they can afford, borrowed money, hiding it) | An acknowledgement without judgement, the helpline, the weekly staking reminder and the bet tracker, the crisis line. No prices |
  | Wanting to win losses back ("how much should I bet to recover my losses?") | The distress answer, which also declines to size or pick a bet and says that chasing losses is a recognised warning sign |
  | A request for a certain winner | No result is certain; no picks or predictions; market data is offered |

  When several apply, crisis comes first, then under 21, then distress. The first three kinds
  have `intent: "support"`, `data: null`, no sources and `support: {"case": "crisis" |
  "underage" | "distress"}`; every other answer has `support: null`. The last row keeps
  `intent: "fallback"`. The wording is fixed in code and is not passed through the
  `Explainer`. Each support reply is logged as `assistant_support_reply` with the case and
  whether a token was sent: never the message, never a user id. The patterns read the
  message and, for a birth year, today's date; nothing else. Where a message could be read
  either way they lean towards the support reply ("the Tides can't lose this one" is
  declined as a request for a certain winner). The general help answer (`intent: "help"`)
  always ends with the helpline sentence, because "I need help" may not be about the
  product.
- **Value screen (market discrepancies).** `GET /v1/value?league=&market=&min_edge=&limit=`
  (public, flag `value_screen`). For every outcome of every upcoming event, the best
  open, non-stale price is compared with the mean no-vig probability of the **other** open,
  non-stale books quoting the same line. Live and finished events are never listed: in play
  each price follows the score, so two quotes taken moments apart are not comparable and their
  difference would be listed as an edge. The book with the best price is left out of its own
  consensus, and an outcome with fewer than 2 other books is skipped. `edge` is the quant
  engine's EV per unit staked at the best price if the consensus probability were true
  (`quant.value` on top of `quant.ev`); rows with `edge` above 0 and at least `min_edge`
  (default 0) are returned, largest first, with `consensus_probability`,
  `books_in_consensus`, `breakeven_probability`, `last_updated` and `stale_after_seconds`.
  The response carries `as_of`, `data_mode`, `method` and a `caveat`: a price above the
  consensus is not proof of an edge, the consensus can be wrong, limits and availability vary,
  and it is not a prediction. On the synthetic data the screen is often short or empty and
  every edge on it is small (a few percent at most): the rows come from the simulated margin
  and noise, and the synthetic model gives no book a real edge.
- **Tracker analytics.** `GET /v1/bets/analytics` (flag `tracker_analytics`) is computed only
  from the caller's settled bets: `by_odds_band` (-200 or shorter, -199 to -110, -109 to
  +100, +101 to +200, longer than +200, by the bet's rounded American price), `by_weekday`
  (UTC day the bet was placed), `by_month` (UTC month it was settled), each row with `bets`,
  `staked`, `profit`, `roi` and `win_rate` (wins / (wins + losses)); `longest_win_streak`,
  `longest_loss_streak` and `current_streak` (a push or void neither extends nor ends a
  run), with `streak_note` next to them: streaks describe the order of past results and say
  nothing about what happens next. No congratulatory or encouraging wording appears anywhere
  in the analytics (a banned-phrase test covers the strings); `average_stake`; `average_odds`
  (mean decimal odds, as a price object); `clv`
  (`sample`, `average`, `share_beating_close`, `buckets`); `stake_distribution`. Void bets
  count as bets but not towards staked, average stake or average odds, as in the summary.
  Ratios are fractions. With fewer than 30 settled bets `sample_note` says the results are
  mostly noise.
- **Email verification. No email is sent.** Registration queues a verification email in the
  outbox. `POST /v1/auth/verify-email/request` (signed in) queues a new one and
  `POST /v1/auth/verify-email/confirm` `{token}` sets `email_verified` on the user object.
  Links expire after 24 hours and work once; a new request replaces the earlier link.
  **An unverified user is not blocked from anything in this milestone.**
- **Password reset.** `POST /v1/auth/password-reset/request` `{email}` always answers `202`
  with the same body whether or not the account exists; the lookup and the email happen after
  the response has been sent, so the response is the same in content and timing.
  `POST /v1/auth/password-reset/confirm` `{token, new_password}` answers `204`, bumps
  `token_version` (every access token issued before it is rejected), marks the email verified
  and returns no token: sign in again. Links expire after 60 minutes and work once.
- **Email tokens.** 32 random bytes, URL-safe. Only the SHA-256 hash is stored
  (`email_tokens`). A used, expired, unknown or wrong-purpose token is
  `400 invalid_or_expired_token`, always with the same message.
- **Email limits.** The four routes share the per-IP auth limit. In addition a user can
  request 3 verification emails and one address 3 reset emails per 15 minutes; the reset
  limit is keyed on the address as typed, so it does not reveal whether an account exists.
- **Login throttling.** Failed logins are counted per email **and client network**: an IPv4
  address, or the /64 prefix of an IPv6 address (one host usually has a whole /64), taken
  from the client IP described under `ODDVEX_TRUST_PROXY`. After 8 failed logins for the
  same email from the same network within 15 minutes, further attempts for that email from
  that network get `429 rate_limited` (standard envelope, `Retry-After`) until the window
  moves on, even with the right password. Attempts from other networks are not affected,
  so someone who knows an email and sends wrong passwords locks out only themselves, not
  the owner. A second ceiling counts the failures for one email from all networks together
  (`ODDVEX_LOGIN_MAX_FAILURES_PER_EMAIL`, 50 in the same window): over it every attempt for
  that email gets the same `429`, which stops guessing spread over many addresses. Both are
  keyed on the email as typed, so the answer is the same for an address without an account.
  An attempt made while refused is not counted. A successful login clears the count of the
  caller's own network only; a completed password reset clears every count for the email.
  In memory, per process, like the IP limiter, and off when
  `ODDVEX_RATE_LIMIT_ENABLED=false`. What is left: someone who can send 50 failures every 15
  minutes from at least seven networks can still keep one email locked out, and in
  production the reset flow is switched off (`email_flows`), so the ways back in are to
  wait for the window, to restart the API process (the counts are in its memory) or to
  raise the ceiling. A client that reaches the API through a server which does not pass
  the visitor's address on shares that server's address with everyone else behind it.
- **Suspension.** `POST /v1/admin/users/{id}/suspend` `{reason}` sets `users.status` to
  `suspended`: the user's existing tokens get `401 account_suspended` and login gets
  `403 account_suspended` with a neutral message (only after the correct password). The data
  is kept; `unsuspend` restores access, including tokens that have not expired. An
  administrator cannot suspend themselves (`409 cannot_suspend_self`) or another
  administrator (`409 cannot_suspend_admin`).
- **Data rights of a suspended account.** A suspended user's token still works on exactly two
  routes, `GET /v1/me/export` and `DELETE /v1/me`, and on nothing else (one dependency,
  `get_data_rights_user`, used by those two routes only; a test walks every other route).
  Both calls are audited with `details.account_status: "suspended"`. A suspended account
  cannot sign in, so this only helps while it still holds an unexpired token (60 minutes by
  default), and the web and mobile apps drop the session of a suspended account. After
  that the owner asks support, and an administrator meets the request with the two routes
  below.
- **Data requests met by an administrator.** For an owner who cannot sign in (suspended,
  closed because under 21, lost password). `POST /v1/admin/users/{id}/export` `{reason}`
  returns the same document as `GET /v1/me/export` for that user, from the same code and
  streamed the same way. `POST /v1/admin/users/{id}/delete` `{reason, confirm_email}`
  deletes the account through the same function as `DELETE /v1/me`
  (`account/service.py`), so what is removed and the `account.deleted` entry that stays are
  the same; it answers `204`. `confirm_email` must be the account's address, compared as
  login compares addresses (`422 confirm_email_mismatch` otherwise, nothing deleted). Both
  work for an active and for a suspended account, and both refuse another administrator
  or the caller's own account (`409 cannot_export_admin`, `cannot_export_self`,
  `cannot_delete_admin`, `cannot_delete_self`). `reason` is required (3 to 500 characters)
  and must not contain the account's email address (`422 reason_contains_email`), because
  the audit entry stays after the account is gone. The entries are `admin.user_exported`
  and `admin.user_deleted`: the acting administrator as `user_id`, the user's opaque id as
  `entity_id`, `details.reason` and `details.account_status`, and nothing of the exported
  data. The export counts among the administrator's streamed responses in progress, not
  against the hourly export limit. Checking that a request really comes from the owner is
  up to the person handling it; the API cannot.
- **Admin.** Every route needs the `admin` role (`403 forbidden` otherwise). Every change
  (suspend, unsuspend, plan, flag) writes an audit entry with the acting administrator as
  `user_id`, the target as `entity_type`/`entity_id` and `details.before` / `details.after`
  (plus `details.reason` for a suspension). The export and the deletion of a user's account
  are audited with their reason (see above). Reads are audited too, coarsely: one `admin.read`
  row per request to the overview, the user list, the email outbox or the community report
  queue, with the resource as `entity_type` and no payload (not the search term, not the rows
  returned). Reading the audit log and the flag list is not recorded.
- **Admin role.** An account is an administrator exactly when its address is in
  `ODDVEX_ADMIN_EMAILS` **and** its email address is verified. That is the rule in every
  environment and whatever `email_flows` says: the list alone gives nobody the role, so
  having registered a listed address first gains nothing. The rule is applied at login,
  when an address is confirmed and on every token use: an account that meets it is
  promoted (`role.granted` in the audit log), and one that holds the role without meeting
  it is demoted at its next request (`role.removed`, with the reason `not_in_admin_emails`
  or `email_not_verified`). Outside production an address is verified with the link from
  the outbox. In production no link can be followed, so the first administrator comes
  from an operator command, run where the API runs (in the container:
  `python scripts/bootstrap_admin.py --email <address>`). It refuses an address that is
  not in `ODDVEX_ADMIN_EMAILS`. For a listed address it creates the account, or takes over
  the one that exists, whoever registered it: it sets a new random password, marks the
  address verified, ends every earlier token and every outstanding email link of the
  account, lifts a suspension, gives the role and writes `admin.bootstrap` to the audit
  log. The password is printed once on standard output: sign in and change it at once.
  Whoever held the address before can no longer sign in. Do not list an address that is
  published anywhere. There is still
  no second factor for administrators. `GET /v1/admin/users?q=&status=&plan=&limit=&offset=`
  returns `{items, total, limit, offset}` with `bet_count` and `last_login_at`.
  `GET /v1/admin/audit?action=&user_id=&before=&limit=` is newest first with a `next_before`
  cursor; `user_id` matches entries a user caused and entries about that user. Admin responses
  never contain password hashes, tokens or email bodies.
- **Logout.** `POST /v1/auth/logout` answers `204` and **ends every session of the account**,
  not only the one that called it: it bumps the user's token version, so every access token
  issued before it gets `401 invalid_token`, on every device. There are no per-session tokens
  to revoke one at a time. Audited as `auth.logout`.
- **Health.** `GET /health` always answers 200 while the process is up. `database` is `ok` or
  `error` from a `SELECT 1`; when it fails `status` is `degraded` instead of `ok` and the
  error is logged, never returned. `data_mode` on `/health` and `/v1/meta` is what the active
  provider reports. The response models only allow `synthetic`, so a provider reporting
  anything else is refused by response validation until that value is added to the schema on
  purpose, rather than being served under the wrong label.
- **Case-insensitive matching.** The `sportsbook` filter on `GET /v1/bets` and the admin user
  search `q` compare against keys folded in Python (`textnorm.fold`: NFKC, `str.casefold()`,
  whitespace collapsed) and stored in `bets.sportsbook_key` and `users.search_key`, which
  mapper events keep in step on every insert and update. Matching is therefore the same on
  SQLite and on PostgreSQL in any locale, for any script: `ÉCLAIR` finds `Éclair` and
  `strasse` finds `Straße`. Accents stay significant (`eclair` does not find `éclair`).
  Migration 0005 backfills both keys.
- **Dev outbox.** `GET /v1/dev/email-outbox/latest?to=&template=` returns the latest outbox
  email for an address, with `dev_link` and `token`, so a developer or an end-to-end test can
  finish a flow. It needs no sign-in and **answers `404` when `ODDVEX_ENV=production`**. Do
  not expose a non-production API with real accounts to the internet.
- **Password change.** `POST /v1/me/password` takes `current_password` and `new_password`
  (10 to 128 characters, different from the current one) and returns a `TokenResponse` with a
  **new token** (200, not 204), because every token issued before the change is rejected with
  `401 invalid_token` from then on, including the one that made the request. A wrong current
  password is `400 invalid_credentials` with a neutral message. It shares the auth rate limit.
- **Data export.** `GET /v1/me/export` returns one JSON document (`format_version: 1`) with the
  profile, bets, watchlist, sync connections, import runs and the caller's own audit entries,
  plus `alerts`, `notifications`, `notification_preferences` and `stake_reminder` (added later;
  optional for older clients) and `community` (profile, picks, comments, handles followed,
  liked pick ids, handles blocked and reports made; present with empty lists for an account
  that never used the community, and whether or not the flag is on). The profile includes
  `plan` and `email_verified`. It never contains the password hash, email tokens or outbox
  emails. Each export is itself audited. The document is streamed (`account/export.py`): bets
  are read 50 at a time, import runs and audit entries 1,000 at a time, and of the community
  part the picks 200 and the comments and reports 1,000 at a time, and written as
  they are read, and no database connection is held while the client is reading. The
  response therefore has no `Content-Length`; it is still one JSON document of the
  `AccountExportOut` schema, with the keys in the same order, to be read to the end and
  parsed once. The status is 200 as soon as the response starts. If the connection breaks
  part-way, or a batch cannot be read (for example no database connection inside 30
  seconds), the text ends there: the closing bracket is only sent last, so what arrived is
  not valid JSON and a partial export cannot be mistaken for a whole one. The batches are separate reads, not one
  snapshot: a bet whose `placed_at` is edited while its own account is being exported can be
  in that document twice or not at all. Limited to `ODDVEX_RATE_LIMIT_EXPORT_PER_HOUR`
  requests per user, and counted among the streamed responses one account can have in
  progress (see "In progress at once").
- **Sync.** Re-running an import never duplicates a bet: bets are keyed on user + provider +
  external bet id. A provider failure that survives the retries is recorded as a failed run and
  returned as `502 sync_failed` with `details.run_id` and `details.retryable`. Two imports of
  the same account at the same moment cannot both write: the one that loses the race gets
  `409 sync_conflict` (`details.retryable: true`), writes nothing, and can simply be retried.
  Imported bets count against the bet cap and are checked like bets entered by hand: a bet
  the provider sends with a price, stake or amount no column can hold, with no legs or more
  than twenty, or with an unknown type or result is left out and counted in the run's
  `error_message` (see "Bet cap" above).
- **Request size.** Bodies over `ODDVEX_MAX_BODY_BYTES` are refused with `413 payload_too_large`
  in the usual envelope, whether the size is declared or the body is streamed.
- **Account deletion.** `DELETE /v1/me` removes the user, bets, legs, watchlist, alert rules,
  notifications, notification preferences, the staking reminder, sync connections, import
  runs, email tokens and outbox emails, and all of the account's community data (see
  "Community" below). The audit log keeps an entry with the opaque user id only. An
  administrator's `POST /v1/admin/users/{id}/delete` runs the same function.
- **NUL characters.** Text with a NUL character (U+0000) in it is refused with
  `422 validation_error` (`details[0].type: "nul_character"`, `loc` naming the place)
  before the route runs, on every route: in a path value, in a query name or value, and in
  any string or key of a JSON body, in whatever encoding the body was sent. PostgreSQL
  cannot store the character, so it used to end as a failed statement and a `500`. The six
  characters `\u0000` as ordinary text are not affected.
- **Database errors in the log.** A failed statement is logged with its class, the place
  it was raised, the SQLSTATE, the table, column and constraint names the driver reports
  and the statement with its placeholders, and without the values bound to it: both
  engines run with `hide_parameters`, and the tracebacks the application writes
  (`logging_config.py`) leave out the message of every exception in a chain that contains a
  database error, because the driver's own text can quote a key or a whole row. The same
  treatment is put on uvicorn's error logger. The worker scripts print Python's standard
  traceback if they crash: no parameter list, but the driver's message as it is.

### Community (flags `community` and `community_leaderboard`, both off by default)

Research discussion, not tipping or touting. No money, no stakes or units, no paid picks, no
affiliate links, no direct messages. While `community` is off, **every** route under
`/v1/community` and `/v1/admin/community` answers `404 feature_disabled`, signed in or not.
Every route except the guidelines needs a signed-in user. Other users are identified by
handle only: no response in this module carries an email address, a display name, a plan,
a user id or anything from the bet tracker.

- **Profiles are opt-in.** `PUT /v1/community/profile` `{handle, bio?, is_public}` creates
  (201) or updates (200) the caller's profile. `handle`: 3 to 20 characters of `a-z`, `0-9`
  and `_` (`422 invalid_handle`), lowered on the way in so it is unique whatever the case
  (`409 handle_taken`), not a reserved word such as `admin`, `oddvex`, `support`,
  `moderator`, `staff`, `official`, `help`, `root` or `system`, alone or as an
  underscore-separated part (`422 handle_reserved`), and it goes through the content rules
  too. `bio`: plain text, at most 280 characters. `GET /v1/community/profile` is the caller's
  own; `GET /v1/community/profiles/{handle}` returns handle, bio, `joined` (month), follower
  and following counts, the record, `is_following`, `is_blocked` and `is_me`. A user without
  a public profile cannot post picks or comments or follow anyone (`403 profile_required`
  with `details.reason`) and is not discoverable: a private, moderated, suspended or
  blocking profile answers the same `404` as a handle that does not exist. Liking, blocking,
  reporting and reading do not need a profile.
- **Picks are structured and gradeable, nothing else.** `POST /v1/community/picks` takes
  `event_id`, `market` (moneyline, spread, total), `outcome_key`, `line` (spread and total)
  and optional `analysis` (plain text, at most 1000 characters). Any other field is a 422:
  there is no stake, no unit size, no confidence rating and no client-supplied price. The
  server records the best open, non-stale price at that moment (`Board.best_price`, the code
  the odds endpoint and the price alerts use; for spread and total among the books quoting
  exactly that line, `422 price_not_available` otherwise), the sportsbook offering it and
  `posted_at`. The event must be upcoming (`422 event_not_open`; also `unknown_event`,
  `market_not_available`, `invalid_selection`). One pick per user per event and market
  (`409 pick_exists`), 20 per user per day. `GET /v1/community/picks?handle=&event_id=&league=&status=&before=&limit=`
  and `GET /v1/community/picks/{id}` read them; `status` is `pending`, `graded` or `void`.
  The author can delete a pick only while its event is still upcoming; afterwards it stays,
  so a record cannot be tidied up (`409 pick_locked`). There is no route to edit a pick.
- **Every pick is verified; self-reported picks do not exist.** `verified` is always `true`
  because every pick is structured, timestamped by the server before the event and graded by
  the server. **Free-text picks, picks entered after the fact, imported records and
  screenshots are intentionally not supported**, so there is nothing unverified to separate
  from the verified record.
- **Grading.** Picks are graded `won`, `lost` or `push` from the final score by
  `quant.grade_leg`, the function the bet tracker's auto-settlement uses (a test grades the
  same selection both ways). There is no background worker: grading runs when someone reads
  the community (at most once per `ODDVEX_COMMUNITY_GRADE_MIN_SECONDS`) and when
  `scripts/grade_picks.py` runs (`--dry-run` saves nothing). A pick whose event the provider
  no longer serves is marked `void` seven days after the scheduled start and counts in no
  record.
- **Record.** Per profile, from graded picks only: `picks`, `wins`, `losses`, `pushes`,
  `win_rate` (wins / (wins + losses)) with its Wilson 95% interval, `average_price`, and
  `flat_stake_roi` with `units_profit`: one unit on every graded pick at the price recorded
  when it was posted (`quant/record.py`), with a `method` string saying exactly that. Below
  30 graded picks `sample_note` says the sample is too few to tell skill from luck, and
  `caveat` always says past results do not predict future results. A pick that moderators hid
  still counts, so hiding a pick's text cannot improve a record.
- **Follows.** `POST/DELETE /v1/community/follows/{handle}`, `GET /v1/community/following`,
  `GET /v1/community/followers`. You cannot follow yourself (`422 cannot_follow_self`), a
  profile you blocked (`409 profile_blocked`) or one that blocked you (`404`, like a handle
  that does not exist). Counts and lists only include public, active profiles.
- **Feed.** `GET /v1/community/feed?scope=following|everyone&before=&limit=`: picks, newest
  first, by time only. No ranking by results or popularity. People you blocked or who blocked
  you, hidden or removed content and suspended or non-public authors are left out.
- **Comments.** `POST/GET /v1/community/picks/{id}/comments`, `DELETE /v1/community/comments/{id}`
  (the author, or an administrator as a moderator action). Plain text, at most 500
  characters, **stored and returned exactly as sent: clients must escape it when rendering.**
  30 per user per hour.
- **Likes.** `PUT/DELETE /v1/community/picks/{id}/like`, idempotent; picks carry `like_count`
  and `liked_by_me`. A like notifies nobody.
- **Blocks.** `PUT/DELETE /v1/community/blocks/{handle}`, `GET /v1/community/blocks`. Blocking
  removes the follow in both directions and hides each of the two from the other everywhere:
  profile, picks, feed, comments, follower lists and the leaderboard. The blocked person is
  not told and sees a plain `404`. The blocker can still look the profile up, to unblock it.
- **Reports.** `POST /v1/community/reports` `{target_type: pick|comment|profile, target_id, reason, details?}`
  with `reason` one of `spam`, `harassment`, `inducement_to_bet`, `misleading_claims`,
  `personal_information`, `other`. For a profile `target_id` is the handle. One open report
  per reporter and target (the open one is returned with 200), 10 per user per hour, not on
  your own content, and only on something you can see. The reported person is not told.
- **Content rules** (`community/content_rules.py`, one module, a pure function). Every bio,
  analysis and comment, and every handle, is checked before it is stored:
  - links: any text containing `http://`, `https://` or `www.` is `422 links_not_allowed`.
    That removes most spam and every affiliate link;
  - everything else is `422 content_not_allowed` with `details.rule`:
    `guaranteed_outcome` ("guaranteed", "lock of the", "can't lose", "can't miss", "sure
    thing", "risk-free", "free money"), `inducement_to_bet` ("bet the house", "max bet",
    "chase" together with "losses", "win it back"), `selling_or_promotion` ("promo code",
    "sign up bonus", "cashapp", "venmo", "paypal"), `contact_solicitation` ("dm me",
    "telegram", "whatsapp") and `contact_details` (email addresses and phone-number-like
    digit runs).

  The rules match phrases on word boundaries, not intent. "Locker room", "unlock" and "the
  chase for the eighth seed" pass; "do not chase your losses" and "no result is guaranteed"
  are rejected, and so is a score followed by a year in the shape of a phone number
  ("112-108 2025"). Spelling tricks get past them. They are a first filter in front of
  reports and moderators, not a replacement.
- **Moderation.** Administrators only, every decision audited (`community.report_resolved`
  with the administrator, the report, the target, its author and the note).
  `GET /v1/admin/community/reports?status=open|resolved` is the queue, with the reported text
  as stored; `POST /v1/admin/community/reports/{id}/resolve` `{action, note}` decides one:
  `dismiss` (only that report), `hide_content` or `remove_content` (the pick, comment or
  profile disappears from every public read; its author still sees their own item with the
  text replaced by "Removed by moderators."; every other open report on it is closed with
  the same decision) or `suspend_author` (the existing account suspension, same code path, so
  an administrator cannot be suspended). `note` is required. There is no "restore" action
  yet: `hidden` and `removed` behave the same today and differ only as a label. A hidden
  profile becomes visible again when its owner changes the handle or the bio.
  `GET /v1/admin/community/overview` counts profiles, picks, comments and open reports.
- **Leaderboard.** `GET /v1/community/leaderboard?league=&window=30d|90d|all`, behind its own
  flag. Only profiles with at least 30 graded picks in the window are ranked, by the **lower
  bound of the Wilson 95% interval** of their win rate: not by the raw win rate, so a short
  lucky run cannot rank first, and not by ROI. Each row shows the sample size and the
  interval, and the response carries a `method` and a `caveat` that past results do not
  predict future results and that a ranking is not a recommendation.
- **Notifications.** Three kinds were added to the in-app system, each with its own switch
  in the preferences: `new_follower` (once per follower, ever), `pick_comment` (someone else
  commented on your pick; the comment text is not repeated) and `pick_graded`. Same copy
  rules and the same banned-phrase test as the others: facts only, no praise for a win.
- **Account lifecycle.** `DELETE /v1/me` deletes the profile, follows in both directions,
  likes, blocks, reports made, comments and **every pick, graded ones included**: no public
  record is left behind without an account. Comments and likes other people left on those
  picks go with them, and so do reports about the deleted account's content.
- **Guidelines.** `GET /v1/community/guidelines` returns the rules as a structured list (be
  civil; no guarantees or pressure to bet; no selling picks and no links; no personal
  information; 21 and over; picks are opinions, not advice) plus the helpline line, so every
  client shows one source of truth. Flag-gated like everything else, but no sign-in needed.
  The wording is a product draft and needs counsel review before the flag is turned on.

## Architecture

A modular monolith. One process, one database.

```
src/oddvex_api/
  main.py            app factory, middleware, routers, OpenAPI post-processing
  config.py          settings from the environment; production safety checks
  quant/             pure betting math and grading. No I/O, no clock. Every number comes from here
                     (value.py: best price vs. consensus; tracker.py: bands, buckets, streaks;
                     record.py: flat-stake record of graded picks)
  providers/         SportsDataProvider protocol, SyntheticProvider, vendor-payload normalizer
  board.py           read models: odds comparison, best price, consensus, prop research, value screen
  api/               public data routes, calculators, admin (overview, users and their data
                     requests, flags, audit, outbox)
  community/         profiles, picks, grading, records, follows, feed, comments, likes, blocks,
                     reports (service.py, router.py), moderation (admin_router.py), the content
                     rules (content_rules.py, pure), the guidelines and the demo seed
  auth/              argon2id passwords, HS256 JWT, register/login/me, password change,
                     email verification and password reset routes
  flags/             feature flag catalog (defaults), DB overrides, require_flag, GET /v1/flags
  entitlements/      plan catalog, require_entitlement, GET /v1/me/entitlements. No billing
  mailer/            EmailSender protocol, OutboxEmailSender, ResendEmailSender stub, email
                     templates (all wording), hashed single-use tokens, dev outbox route
  account/           data export (export.py streams the document) and account deletion
                     (service.py, shared by the owner's route and the administrator's)
  bets/              tracker: schemas, storage (what the columns can hold), service
                     (settlement, auto-settlement, summary), analytics, routes
  watchlist/         watched teams, players and events
  alerts/            alert rules: schemas, pure evaluator, service (provider facts, state), throttle, routes
  notifications/     templates (all wording), NotificationChannel + InAppChannel, preferences,
                     staking reminder, routes
  sync/              SyncProvider protocol, MockSyncProvider, idempotent import
  assistant/         responsible-gambling checks and replies (safeguards.py), intent router,
                     data tools, Explainer protocol + TemplateExplainer
  helpline.py        the helpline and crisis-line facts; every text that names one imports them
  db/                SQLAlchemy 2 models, portable UTC datetime type, session factory
  textnorm.py        caseless text keys folded in Python, the same on every database
  errors.py middleware.py ratelimit.py cache.py logging_config.py deps.py
alembic/             migrations (0001: users, bets, bet_legs, sync_connections, sync_import_runs, audit_log;
                     0002: watchlist_items, users.token_version/password_changed_at, bets.settled_by,
                     bet_legs.outcome_key;
                     0003: alert_rules, notifications, notification_preferences, stake_reminders;
                     0004: feature_flags, email_tokens, email_outbox,
                     users.plan/status/last_login_at/email_verified_at;
                     0005: community_profiles, community_picks, community_comments,
                     community_follows, community_likes, community_blocks, community_reports,
                     users.search_key, bets.sportsbook_key;
                     0006: bets.client_request_id and its unique index)
scripts/             export_openapi.py, seed_demo.py, evaluate_alerts.py, grade_picks.py,
                     bootstrap_admin.py (the first administrator; see "Admin role")
docs/QUANT_METHODOLOGY.md
```

- Routes are thin. Math lives in `quant/`, read models in `board.py`, domain rules in each
  module's `service.py`.
- The provider and sync contracts are `Protocol`s, so a licensed data vendor or a real
  account-linking provider can be added without touching routes. Provider records carry
  `provider`, `provider_id` and `fetched_at`.
- Cross-cutting: request id on every response and log line, one JSON log line per request,
  security headers, CORS allowlist, request body size limit, in-memory sliding-window rate
  limits (per IP, per account and client network for failed logins, per account for emails, and per user for community
  picks, comments, reports and follows, bet and sync writes and the data export), audit log for auth events including logout,
  email verification, password resets, every admin change, admin reads, role grants and
  removals, community posts, follows, blocks, reports and moderation decisions, password changes, bet create/settle/auto-settle/delete,
  watchlist changes, alert rule changes and firings, notification deletion, preference and
  staking-reminder changes, sync, data export and account deletion.

## What is synthetic or mocked

| Thing | Status |
| --- | --- |
| Leagues, teams, players, sportsbooks, events, scores | Synthetic. Fictional names, seeded, relative to the current time so there are always live, upcoming and final events |
| Odds, lines, line history, prop offers, game logs | Synthetic. One scoring model produces both the results and the prices: each side scores as a Poisson process, a fair price is the exact probability of the final result given the score and the time left, and final scores are drawn from the same model (`tests/test_audit_board_calibration.py` checks that every side wins as often as its price says, before the start and in play). Book prices add a margin and noise. No book or prop has a real edge |
| Stale / suspended / unavailable books | Simulated on purpose. One book (`oldmill`) is always stale. In a live game a book is stale for a few seconds after each score change, until it requotes, and it suspends a market once one outcome is more than 98% likely |
| Sportsbook sync | `MockSyncProvider` only: a fictional account with a fixed bet history and a simulated failure switch. No credentials, no real sportsbook |
| Assistant | Fixed patterns for the responsible-gambling replies, then a keyword/regex intent router and templates. **No language model is connected** |
| `data/fixtures/*.json` | Synthetic vendor-format payloads for the provider-normalization contract tests |
| Community demo data | Six fictional profiles (`fictional_fox`, `sample_sam`, `madeup_mara`, `placeholder_pat`, `notreal_nia`, `example_eli`) and the demo user's `demo_bettor`, with graded and upcoming picks, comments, follows and likes. Seeded only when the `community` flag is on in that database or `--with-community` is passed. Graded picks are written as posted before events that are final by now, priced from the synthetic line history, and graded by the API's own grading code |
| Demo account | Seeded sample bets, development only. Four of the pending ones have structured legs on already finished synthetic events, so auto-settle has something to settle. With a provider it also gets five alert rules (one price alert that is already met and fires, the others stay active) and the notifications the engine produces for them |
| Notification delivery | In-app only. No push, email or SMS provider is connected |
| Email | Not sent. See below |
| Billing | Does not exist. See below |

## What is stubbed: no billing, no real email

| Thing | What exists | What does not |
| --- | --- | --- |
| Plans | `users.plan` (`free` / `premium`), set by an administrator; an entitlement catalog and `require_entitlement`, enforced only with the `premium_gating` flag (off) and gating nothing as shipped | Prices, a purchase or subscription route, a payment provider, invoices, trials, webhooks. All of it needs Founder approval |
| Email | The verification and reset flows end to end against an `EmailSender` protocol. `OutboxEmailSender` (the default) writes `to`, `template`, `subject`, `body_text`, `created_at` and a `dev_link` to `email_outbox` | Delivery. Nothing leaves the process. `ResendEmailSender` is a class that raises `NotImplementedError("Requires Founder approval and a Resend account")`; it is only selected by `ODDVEX_EMAIL_PROVIDER=resend`, and then the app refuses to start. No email SDK is installed and no HTTP call is made |
| Email in production | `email_flows` is **off by default in production**, so the four routes answer `404 feature_disabled` and no email is queued. If an operator turns it on, the outbox row is written with the link replaced by a placeholder and `dev_link` empty, so the database never holds a usable token | A way for a real user to receive a link: **in production the verification and reset flows cannot be completed until a provider is approved and connected**, which is why the flag is off there |
| Community | Everything described under "Community", behind the `community` flag (off) and, for the leaderboard, `community_leaderboard` (off). The demo seed adds fictional profiles only when the flag is on or `--with-community` is passed | Self-reported or free-text picks, stakes or units, paid picks, links, direct messages, images, mentions, editing a pick or a comment, a "restore" moderation action, appeals, per-moderator roles, and any review of the guidelines by counsel or of the leaderboard by a responsible-gambling adviser |

## Limitations

- No real odds, scores or statistics. Nothing here should be used to make a betting decision.
- Email is not delivered, so nobody outside development can verify an address or reset a
  password yet. An administrator cannot reset a password either. The one exception is the
  operator command `scripts/bootstrap_admin.py`, which sets a new password for an address
  in `ODDVEX_ADMIN_EMAILS` and marks it verified.
- `GET /v1/dev/email-outbox/latest` is unauthenticated outside production by design.
- Flags are global: no per-user or percentage rollout. Each flagged request reads the flag
  from the database.
- Case-insensitive matching (sportsbook filter, admin search) ignores case for any script but
  not accents, and a row written by something other than the application or migration 0005
  has no key and does not match until it is next saved.
- Community: grading has no background worker (it runs on reads and from
  `scripts/grade_picks.py`), the per-user limits are in process memory like the other
  limiters, the content rules match phrases and can be evaded or over-match (see above),
  moderation has no restore action, and the feed and the leaderboard are computed per request
  without caching. The leaderboard reads every eligible profile's graded picks: fine for a
  demo, not designed for a large community. Prices are snapshots of synthetic data.
- Rate limiting and caching are in process memory. With several workers each has its own
  counters; move them to a shared store before scaling out.
- JWT access tokens only: no refresh tokens and no per-session logout. `POST /v1/auth/logout`
  ends every session of the account at once. Tokens also stop working when the password is
  changed or reset (every earlier token), when the account is suspended (until it is
  unsuspended; the two data-rights routes excepted) and when it is deleted. Password reset exists but depends on an
  email that is not delivered (see above).
- Auto-settlement grades full-game moneyline, spread and total from the provider's final score.
  Props, futures, half results, voids and cash-outs stay manual, and the score is synthetic.
  It runs when the client calls it; there is no background job.
- Alerts have no background worker (see "Alert evaluation" above): they fire when the user reads
  their notifications, the client calls `POST /v1/alerts/evaluate`, or `scripts/evaluate_alerts.py`
  runs. The per-user evaluation throttle is in process memory, like the rate limiter. Prices are
  not stored, so a condition that was only true between two evaluations is missed.
- Notifications are in-app only. Push, email and SMS need third-party services and Founder
  approval.
- The assistant's responsible-gambling replies depend on fixed patterns. They miss messages
  that are worded differently, they can fire on a message that meant something else (the
  user then gets help resources instead of the answer), and they read one message at a time:
  nothing is remembered, so a later message in the same chat is answered normally. A user who
  says they are under 21 is told OddVex is for adults 21 and over; nothing is recorded against
  an account and no account is closed, because conversations are not stored and the under-21
  procedure does not exist yet.
- The staking reminder is a reminder, never a limit. It looks at bets recorded in OddVex only,
  is checked when a bet is created or imported (not when a bet is edited, settled or deleted),
  and the "current week" is the ISO week in UTC, not the user's time zone.
- Alert rules store provider ids, like the watchlist. A rule whose event the provider no longer
  serves expires on its next evaluation.
- The watchlist stores provider ids. A watched event the provider no longer serves stays on the
  list as `available: false` until the user removes it.
- The data export is streamed and bounded in memory, but its size still grows with the
  account: the bet cap bounds the bets (about 115 MB of JSON for 5,000 bets of the largest
  size), while nothing bounds how many audit entries, import runs and community comments,
  picks and reports an account accumulates over time. Import runs, and the audit entries
  written by bet and sync routes, can only grow as fast as the per-user write limit allows
  (`ODDVEX_RATE_LIMIT_USER_WRITES_PER_DAY` a day); community posts as fast as the community
  limits allow (30 comments an hour by default). Audit entries are also written by the
  watchlist, alert, notification and staking-reminder routes, which have no per-user
  write limit: one account can add those as fast as it can send requests, and they stay
  in the database and in its export. Sign-in routes write audit entries too and are
  limited per address only.
- Nothing limits how many requests are in progress across accounts, or how many
  connections the server accepts. The per-account ceilings above bound what one account
  can hold in memory; many accounts together are bounded only by the registration limit
  and by whatever sits in front of the API.
- A request holds a database connection from the moment the signed-in user is looked up
  until it has answered, and the pool has 15 (SQLAlchemy's default: 5 plus 10 overflow).
  When more requests than that are in progress at once, from one account or from many,
  the rest wait; one that has waited 30 seconds for a connection answers `500
  internal_error`. Measured with one account sending 125 requests at the same moment
  (summary, analytics, list, export, auto-settle; 5,000 bets of the largest size): 36 of
  them answered 500 after 30 seconds, the process peaked at 228 MiB and answered normally
  afterwards. The streamed responses give their connection back between batches.
- The bet cap and the write limits are per account. They do not limit how many accounts one
  person creates; that is the registration limit's job (per IP).
- A sync import still holds the bets of one run in memory until it commits. The mock provider
  has twelve; a real provider would need to page.
- Age is a self-attestation checkbox (`age_confirmed`), not verification.
- Odds are not persisted; they are generated on request. The `providers` contract is where an
  `odds_snapshots` table would attach.
- Bets are single-currency numbers with no currency code.
- The Docker image and the PostgreSQL path are covered by configuration and tests described
  above, not by a production deployment. Deploying is a Founder approval gate.
- Migrations run on container start. That is fine while they are additive; a destructive
  migration needs Founder approval first (see `PROJECT_CONSTITUTION.md`).
