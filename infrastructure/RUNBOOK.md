# Operations runbook

Last updated: 2026-11-16 · Status: **written from the code. Never exercised against a deployed environment, because
none exists.** Treat every procedure as untested until it has been rehearsed in staging.

Scope: the FastAPI service (`services/api`), the Next.js app (`apps/web`) and the database. Incident handling,
severity and communication are in `docs/compliance/INCIDENT_RESPONSE.md`. Release rollback is in
`ROLLBACK_PLAN.md`.

Commands assume a shell in `services/api` with the environment variables of the target environment loaded, or a
shell inside the API container (where the working directory is `/app` and `scripts/` and `alembic/` are present).

## 1. What does not exist

Read this first. Several things a runbook normally leans on are missing.

| Missing | Effect | Gate to add it |
|---|---|---|
| Any deployed environment | Nothing to operate yet | G-02, G-03 |
| Monitoring, alerting, uptime checks, error tracking | Failures are found by people, not by tools | G-02 |
| On-call roster | Section 12 is a template with blanks | Founder |
| Background worker or scheduler | Alerts only fire when a user opens the app or the script is run by hand | G-02 if paid |
| Feature flags and kill switches | In progress in the API. Until they are in `services/api/README.md`, the only "off switch" is a deploy | None |
| Email | Nothing sends. Password reset and email verification are in progress and write to an outbox table. A forgotten password cannot be recovered today | G-06 |
| Shared rate-limit store | Limits are per process | G-02 if paid |
| Database health in `/health` | `/health` answers `ok` even when the database is down | None (code change) |
| Deletion ledger | A restore brings deleted accounts back with nothing to re-delete them from | None (code change) |
| Status page | No way to tell users about an incident except the site itself | G-02 |

## 2. Health checks

| Check | Command | Healthy | Notes |
|---|---|---|---|
| Liveness | `curl -fsS <api>/health` | 200, `{"status":"ok","version":"...","data_mode":"synthetic","server_time":"..."}` | Does **not** touch the database. Used by the Docker `HEALTHCHECK` |
| Metadata | `curl -fsS <api>/v1/meta` | 200 with `data_mode`, `provider`, `version`, `server_time`, `notice` | Also does not touch the database |
| Database reachable | `alembic current` | Prints the head revision | Or sign in with a known account: login reads the database |
| Provider | `GET <api>/v1/admin/overview` with an admin token | `provider_health.status` is `ok` | Also returns account, bet and sync-connection counts and the 25 most recent audit entries |
| Web | `curl -fsS -o /dev/null -w "%{http_code}\n" <web>/` and `<web>/app` | 200 (or a redirect to `/login` for `/app`) | Same checks as the CI `docker` job |
| Version deployed | `version` in `/health` | Matches the release | The value is the package version (`0.1.0` today), not a commit id. Two different commits can report the same version. To be decided: engineering, whether to expose the commit |

`data_mode` is hard-coded to `"synthetic"` in `/health` and `/v1/meta` (`services/api/src/oddvex_api/api/data.py`).
When a real provider is connected this must change in code. Do not use it yet as proof of which provider is live.

## 3. Logs and request ids

The API writes one JSON line per request to standard output (`logging_config.py`, `middleware.py`).

Access line fields: `ts`, `level`, `logger` (`oddvex.access`), `message` (`request`), `request_id`, `method`, `path`,
`status`, `duration_ms`, `client_ip`.

Other lines to know:

| `logger` | `message` | Meaning |
|---|---|---|
| `oddvex.app` | `startup` | Process started. Carries `env` and `provider` |
| `oddvex.app` | `demo_seed` | Demo account was seeded at startup. Should never appear in production |
| `oddvex.access` | `unhandled_error` | An exception escaped a route. Carries `request_id`, `method`, `path` and an `exc` stack trace. The client got a 500 with code `internal_error` |

Following one request:

1. Every API response has an `X-Request-ID` header. If the caller sent an `X-Request-ID` of 8 to 64 characters from
   `A-Z a-z 0-9 . _ -`, it is reused; otherwise the API generates one.
2. Search the logs for that `request_id`.
3. If the request changed data, the same id is in `audit_log.request_id`. Admins see recent audit entries on
   `/app/admin`.

Limits:

- **The web app does not forward a request id to the API.** A web page error cannot be tied to an API log line by id
  today. The web error screen shows Next.js's own `digest` ("Reference ..."), which matches the web server's logs,
  not the API's. Correlate by time and path.
- `client_ip` in the access line is the direct peer address. It ignores `ODDVEX_TRUST_PROXY`. Behind a proxy it is
  the proxy's address. Audit rows and the rate limiter use `client_ip()` from `ratelimit.py`, which does honour the
  setting.
- Logs contain IP addresses and paths. They are personal data. Retention is to be decided (PRIVACY_AND_DATA
  section 3 proposes 30 to 90 days): Founder with counsel.
- Uvicorn's own access log is separate from the JSON lines and is plain text.

## 4. Common failures

### 4.1 API unreachable

| | |
|---|---|
| What users see (web) | In the app: "OddVex can't reach its data service" with a "Try again" button (`apps/web/src/app/app/error.tsx`). In forms and client components: "OddVex can't reach its data service right now. Try again in a moment." (HTTP 503 `api_unavailable` from `/api/ov/*`) |
| What users see (mobile) | The screen's error state. A saved session survives |
| Cause candidates | API process down; wrong `ODDVEX_API_URL`; API slower than the web timeouts (8 s for server fetches, 10 s for the proxy); database down (routes that read the database fail while `/health` still passes) |
| Check | `curl <api>/health` from outside, then from where the web server runs. Check API logs for `startup` and for `unhandled_error`. Run `alembic current` |
| Fix | Restart or redeploy the API. If it will not start in production, read the first error: it refuses to start when `ODDVEX_JWT_SECRET` is missing, is the development value or is shorter than 32 characters, or when `ODDVEX_CORS_ORIGINS` contains `*` |
| Marketing pages | Static pages keep working without the API |

### 4.2 Provider degraded

Today the only provider is `SyntheticProvider`, which always reports `ok` and has no external dependency, so this
cannot happen yet. The procedure matters once a licensed provider exists (G-01).

| | |
|---|---|
| Signal | `provider_health.status` of `degraded` or `down` on the admin overview; prices marked stale across the board |
| Built-in protection | The API, not the client, marks a quote stale (`ODDVEX_STALE_LIVE_SECONDS`, `ODDVEX_STALE_PREGAME_SECONDS`). Stale, suspended and unavailable quotes are excluded from best price and consensus (ADR-0002) |
| What to do | Do not hide the stale labels. Do not raise the stale thresholds to make data look fresh. Follow INCIDENT_RESPONSE 5.4 and 5.7 |
| Missing | A per-feed kill switch and freshness monitoring |

### 4.3 Migration failure

| | |
|---|---|
| Signal | `alembic upgrade head` exits non-zero. In the Docker image the container then never starts uvicorn, because the start command is `alembic upgrade head && exec uvicorn ...` |
| First | Stop. Do not edit the database by hand. Do not run `alembic downgrade` (G-08: every existing downgrade drops tables or columns) |
| Check | `alembic current` and `alembic history`. On PostgreSQL, DDL in a failed migration is normally rolled back with its transaction, so the schema should still be at the previous revision. Confirm, do not assume |
| Fix | Keep or redeploy the previous application version, which matches the previous schema. Fix the migration in a pull request. Re-run in staging first |
| If the schema is half-applied | Treat as an incident (INCIDENT_RESPONSE 5.8). Restoring from backup needs Founder approval |

### 4.4 Rate-limit complaints ("Too many attempts")

How it works (`ratelimit.py`, `auth/router.py`, `assistant/router.py`):

- Two buckets, both **per IP address**: `auth` (register, login and password change together, default 10 per
  minute) and `assistant` (default 20 per minute). Sliding window of `ODDVEX_RATE_LIMIT_WINDOW_SECONDS`.
- A blocked request gets HTTP 429, code `rate_limited`, a `Retry-After` header and
  `details.retry_after_seconds`. The web and mobile apps show "Too many attempts. Wait a minute, then try again."
- Counters are in process memory. A restart clears them. Each process has its own.

Known causes of false positives:

| Cause | Why | Status |
|---|---|---|
| All web sign-ins share one bucket | Web login, sign-up and password change are server actions that call the API from the web server and forward no client address, so the API sees one IP for every web user | Open. Needs an engineering decision before real traffic. Not fixed |
| Many users behind one address | Offices, campuses, mobile carriers | Inherent to per-IP limits |
| `ODDVEX_TRUST_PROXY` wrong | `false` behind a proxy: everyone shares the proxy's address. `true` with no proxy, or more than one: the client can choose the address it is counted under | Set only after confirming what `X-Forwarded-For` contains on the chosen host |

What to do:

1. Find the 429 lines in the access log and look at `path` and volume.
2. Ask the user to wait for the number of seconds in the message.
3. Raising `ODDVEX_RATE_LIMIT_AUTH_PER_MINUTE` weakens brute-force protection for everyone. It is a configuration
   change to a production environment: get approval from whoever owns production configuration (to be decided:
   Founder).
4. Never set `ODDVEX_RATE_LIMIT_ENABLED=false` in production.

### 4.5 Sync failures

Only the mock sync provider exists. No real sportsbook is connected.

| Symptom | Meaning | Action |
|---|---|---|
| HTTP 502 `sync_failed`, with `details.run_id`, `details.retryable`, `details.attempts` | The provider failed on every attempt (`ODDVEX_SYNC_MAX_ATTEMPTS`, default 3). A failed run is recorded and the user gets a `sync_finished` notification | If `retryable`, the user can press "Sync now" again. Re-running never duplicates bets |
| HTTP 409 `sync_conflict`, `details.retryable: true` | Two imports of the same connection ran at once. The loser wrote nothing | Retry |
| A user asks for run history | `GET /v1/sync/connections/{id}/runs` | Shows status, attempts, counts, error message |

The mock provider has a deliberate failure switch for demos and tests. A failure on the mock is not an outage.

### 4.6 Alerts not firing

**Most likely cause: nothing evaluated them. There is no worker.** (`services/api/README.md`, "Alert evaluation".)

Rules are evaluated only when:

1. the user reads `GET /v1/notifications` or `GET /v1/notifications/unread-count` (at most once per
   `ODDVEX_ALERT_EVAL_MIN_SECONDS` per user, default 30, tracked per process), or
2. a client calls `POST /v1/alerts/evaluate` ("Check now" on mobile), or
3. someone runs `scripts/evaluate_alerts.py` (section 9).

Checklist:

| Question | Where to look |
|---|---|
| Is the rule `active`? | `GET /v1/alerts`. `triggered` rules fired once and must be set again. `expired` rules lost their event. `paused` rules are off |
| Did the condition hold at the moment of an evaluation? | Prices are not stored. A price that touched the threshold and moved away between two evaluations was never seen |
| Was it a `game_start` rule nobody evaluated before the game began? | It expired without a notification. This is documented behaviour |
| Is that notification kind switched off? | `GET /v1/me/notification-preferences`. A disabled kind creates no notification, but the rule still changes state |
| Does the user expect a push or an email? | There is none. Notifications are in-app only |
| Did the script fail? | It prints `... N failed.` and exits 1. Failures per user go to standard error |

### 4.7 Sign-in problems after a change

| Symptom | Cause |
|---|---|
| Every user is signed out at once | `ODDVEX_JWT_SECRET` changed (section 7) |
| One user is signed out everywhere | They changed their password. All earlier tokens are rejected by design |
| A user is signed out after an hour | Token lifetime (`ODDVEX_JWT_TTL_MINUTES`, default 60). There are no refresh tokens |
| "I forgot my password" | No recovery exists today. See `docs/product/SUPPORT_READINESS.md` |

## 5. Rolling back a deploy

Full procedure and criteria: `ROLLBACK_PLAN.md`. Short form:

1. Decide using the triggers in `ROLLBACK_PLAN.md` section 2.
2. Redeploy the previous known-good build of the affected app. On the chosen host this is whatever its "promote a
   previous deployment" action is (to confirm with vendor docs). With Docker, start the previous image tag.
3. Do not touch the database unless the release included a migration. If it did, section 6.
4. Run the smoke test in `DEPLOYMENT_PLAN.md` section 10.
5. Record what happened.

**Hazard for the Docker image.** The container runs `alembic upgrade head` before it starts uvicorn. An **older**
image does not contain the newer migration files, so against a database already at a newer revision Alembic cannot
find that revision, the command fails, and the container never starts serving. Checked on
2026-11-16 with a scratch SQLite database stamped with an unknown revision: `alembic upgrade head` exits non-zero
with "Can't locate revision". It has not been rehearsed with the real images. Until it is
rehearsed in staging, plan a Docker rollback across a migration as: start the old image with its command
overridden to run uvicorn only (`uvicorn oddvex_api.main:app --host 0.0.0.0 --port 8000`). That is safe only
because migrations so far are additive.

## 6. Rolling back a migration

**Default: do not.** Roll the application back and leave the schema where it is. Migrations 0001 to 0003 are
additive, so older application code runs against the newer schema (with the Docker caveat in section 5).

A schema downgrade is a destructive migration (G-08). Each existing `downgrade()` drops data:

| Downgrade | Drops |
|---|---|
| 0003 to 0002 | `alert_rules`, `notifications`, `notification_preferences`, `stake_reminders` and everything in them |
| 0002 to 0001 | `watchlist_items`; `users.token_version`, `users.password_changed_at`; `bets.settled_by`; `bet_legs.outcome_key` |
| 0001 to base | Every table |

A revision 0004 (feature flags, plans, account status, email tokens and outbox) is in progress in the working tree
and is not merged or documented in `services/api/README.md` yet. Its header says it is additive. Add it to this
table when it lands.

If the Founder approves a downgrade:

1. Confirm a restore point exists and has been tested (`DEPLOYMENT_PLAN.md` section 11).
2. Stop the application or put it in a state where it does not write.
3. `alembic downgrade <revision>` with the exact target revision. Never `base`.
4. `alembic current` to confirm.
5. Deploy the application version that matches that revision.
6. Record approval, time, operator and outcome in `docs/product/DECISION_LOG.md`.

## 7. Rotating the JWT secret

What it is: `ODDVEX_JWT_SECRET` signs every access token with HS256 (`auth/security.py`). One secret, no key id,
no support for two valid secrets at once.

What rotation does:

- **Every existing token becomes invalid immediately.** Every user on web and mobile is signed out.
- Web: the next request reads as signed out and `/app/*` redirects to `/login`. The stale cookie is harmless.
- Mobile: the next authenticated call gets 401, the app clears SecureStore and opens the log in screen.
- Passwords are unaffected. Users sign in again.
- Nothing is lost. Unsaved form input on screen at that moment is.

When: on any suspicion that the secret leaked (INCIDENT_RESPONSE 5.2), when someone with access leaves, and on
whatever schedule the Founder sets (to be decided). Rotation is the only way to sign out all users at once.

Procedure (G-09: creating and changing a production secret needs Founder approval):

1. Generate a new random value of at least 32 characters with a cryptographic generator. Do not reuse a value from
   another environment. Do not paste it into chat, tickets or this repository.
2. Set it in the host's secret store for the one environment being rotated.
3. Restart or redeploy the API so every instance picks it up. Mixed instances would accept different tokens.
4. Check `/health`. In production the app refuses to start if the value is too short.
5. Sign in with a test account and confirm an old token now returns 401 `invalid_token`.
6. Record who, when and why in `docs/product/DECISION_LOG.md`. Never record the value.

The web app does not hold the secret. Only the API does.

## 8. Granting and removing admin

Mechanism (`config.py`, `auth/router.py`, `deps.py`):

- `ODDVEX_ADMIN_EMAILS` is a comma-separated list. Matching is case-insensitive on the whole address.
- An account whose email is on the list gets `role = "admin"` when it **registers**, or the next time it
  **logs in**. The role is then stored in the `users` table.
- Admin routes check the stored role on every request, not the token. Today the only admin route is
  `GET /v1/admin/overview`, shown on `/app/admin`. It is read-only. Admin user management is in progress.

To grant (G-09: this is production access):

1. Founder approves the specific person and address. Record it in the decision log.
2. Add the address to `ODDVEX_ADMIN_EMAILS` for that environment. Restart or redeploy the API.
3. The person logs out and logs in again (or registers).
4. Confirm `/app/admin` loads for them and returns 404 for a normal account.

To remove:

1. Remove the address from `ODDVEX_ADMIN_EMAILS` and restart. **This alone does not remove the role.** The code only
   promotes; it never demotes.
2. Until admin user management exists, demotion needs a direct database update of that user's `role` to `user`.
   That is a manual change to production data: Founder approval (G-09), two people present, exact statement
   reviewed first, and an entry in the decision log.
3. The change takes effect on the person's next request. No token rotation is needed.

Risks to keep in mind:

- **There is no email verification.** If an address is on the list before its owner has registered, whoever
  registers that address first becomes admin. Only list addresses that already have an account you control, or
  register the account first.
- Admin accounts have no MFA.
- Granting the role and reading the admin overview are **not** written to the audit log today.

## 9. Scripts

### `scripts/seed_demo.py`

Creates `demo@oddvex.test` with sample bets, alert rules and notifications. Safe to run more than once.

```bash
cd services/api
.venv/bin/python scripts/seed_demo.py
```

- Password: the value of `ODDVEX_DEMO_PASSWORD`. The default is published in the README. Never run this against a
  reachable environment with the default.
- Refuses to run when `ODDVEX_ENV=production` unless `--allow-production` is passed (exit code 2). **Do not pass
  that flag** without Founder approval (G-09): it creates a known account in production. The only expected reason
  is a store-review demo account, which needs its own decision (`docs/marketing/STORE_SUBMISSION_PREP.md`).
- Outside production it creates missing tables first.
- `ODDVEX_AUTO_SEED_DEMO=true` does the same at API startup and is ignored in production.

### `scripts/evaluate_alerts.py`

Evaluates the alert rules of every user who has active ones.

```bash
cd services/api
.venv/bin/python scripts/evaluate_alerts.py --dry-run   # report only, saves nothing
.venv/bin/python scripts/evaluate_alerts.py             # evaluate and save
```

- Output: `N user(s), N rule(s) evaluated, N fired, N expired, N failed.`
- Exit status 1 if any user failed. Each failing user is named on standard error with the exception type.
- Idempotent. Safe while the API is serving. One transaction per user, so one failure does not stop the rest.
- Uses `DATABASE_URL`, `ODDVEX_DATA_PROVIDER` and `ODDVEX_SYNTHETIC_SEED` from the environment, and builds the same
  provider as the API would (`build_provider`). Run it with the same environment as the API.
- Delivers in-app notifications only.
- Nothing runs it on a schedule. See `DEPLOYMENT_PLAN.md` section 9.

### Migrations

```bash
cd services/api
.venv/bin/alembic current
.venv/bin/alembic history
.venv/bin/alembic upgrade head      # additive only without G-08
```

## 10. Things never to do

- Run `alembic downgrade` in production without G-08.
- Edit production data by hand without Founder approval and a second person.
- Copy production data to staging, preview or a laptop.
- Put a secret value in a ticket, a chat message, a log line or this repository.
- Turn off rate limiting, the stale labels or the "Synthetic data" label to make a problem go away.
- Pass `--allow-production` to `seed_demo.py` on your own authority.
- Send email to users during an incident without Founder approval (G-06).

## 11. After any production change

Record in `docs/product/DECISION_LOG.md` or the incident record: what changed, who approved, who did it, when,
how it was verified, and how to undo it.

## 12. On-call escalation template

Fill in before the first real user. Until then there is no on-call.

| Role | Name | Contact (primary) | Contact (backup) | Hours covered |
|---|---|---|---|---|
| First responder | ____________ | ____________ | ____________ | ____________ |
| Second responder | ____________ | ____________ | ____________ | ____________ |
| Incident commander | ____________ | ____________ | ____________ | ____________ |
| Founder (spend, user and regulator communication, taking the service offline) | ____________ | ____________ | ____________ | ____________ |
| Counsel (notification duties) | ____________ | ____________ | ____________ | ____________ |
| Hosting vendor support | ____________ | Plan and support channel: ____________ | | |
| Database vendor support | ____________ | Plan and support channel: ____________ | | |
| Email vendor support | ____________ | Plan and support channel: ____________ | | |
| Data provider support | ____________ | Not chosen | | |

Escalation steps:

| Step | Trigger | Who | Within |
|---|---|---|---|
| 1 | Alert or report received | First responder acknowledges | ______ minutes |
| 2 | Not acknowledged | Second responder | ______ minutes |
| 3 | SEV1 or SEV2 declared (INCIDENT_RESPONSE section 2) | Incident commander and Founder notified | ______ minutes |
| 4 | Personal data may be involved | Founder contacts counsel | ______ |
| 5 | Restore from backup, destructive change or user communication proposed | Founder decides | Before acting |

Incident record:

```
Incident id:            ____________
Declared by / at (UTC): ____________
Severity:               SEV__
Summary:                ____________
Environment:            ____________
Release / version:      ____________
Request ids / evidence: ____________
Incident commander:     ____________
Scribe:                 ____________
Timeline (UTC):
  __:__  ____________
Containment taken:      ____________
Approvals obtained:     ____________ (who, when, for what)
User impact:            ____________
Personal data involved: yes / no / unknown
Resolved at (UTC):      ____________
Review scheduled:       ____________
```
