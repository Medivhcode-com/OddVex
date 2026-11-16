# Deployment plan (Vercel, Neon, Resend)

Last updated: 2026-11-16 · Status: **plan only. Nothing here has been executed, purchased or approved.**

This plans the Founder's stated hosting preference: Vercel for the web app and the API, Neon for PostgreSQL, Resend
for email. The preference is recorded in `docs/product/DECISION_LOG.md`. It is not an approval.

How to read vendor statements in this document:

- **Repo fact**: proven by a file in this repository. The file is cited.
- **To confirm with vendor docs**: a capability this plan depends on that has not been checked against the vendor's
  current documentation. Nobody should treat it as true until someone has checked and recorded the link.

## 1. Before any of this

Nothing below may start until each of these is recorded in `docs/product/DECISION_LOG.md` with who, what and when.

| # | Approval | Gate | Decides |
|---|---|---|---|
| 1 | Create paid (or paid-capable) accounts with Vercel, Neon and Resend, and accept the plan each is on | G-02 | Founder |
| 2 | Accept each vendor's terms and data-processing agreement; confirm each may be used for a gambling-adjacent product | G-10 | Founder with counsel |
| 3 | Add each vendor as a sub-processor of personal data (email addresses, bet records, IP addresses in logs) | G-13 | Founder with counsel |
| 4 | Create production secrets (JWT secret, database credentials, email API key) and decide who may read them | G-09 | Founder |
| 5 | First production deploy, and the deploy process itself | G-03 | Founder |
| 6 | DNS cut-over for oddvex.com | G-03 | Founder |
| 7 | Send any email to a real person | G-06 | Founder |
| 8 | Publish Terms, Privacy and Responsible gambling pages as final (they are unreviewed drafts) | G-10 | Founder with counsel |

Also needed first, with no gate but no owner yet:

- [ ] Confirm who owns the oddvex.com domain registration and where its DNS is hosted. To be decided: Founder.
- [ ] Decide the staging hostname and the API hostname (this plan assumes `api.oddvex.com`). To be decided: Founder.
- [ ] Budget envelope (ROADMAP Q-07). To be decided: Founder.

## 2. Target architecture

```
                         Browser                              Mobile app (Expo)
                            |                                        |
                            | HTTPS, cookie ov_session               | HTTPS, Authorization: Bearer <JWT>
                            v                                        |
   +------------------------------------------------+               |
   | Vercel project "oddvex-web" (apps/web)         |               |
   | Next.js 16: marketing pages, /app/*,           |               |
   | server actions, /api/ov/* proxy route          |               |
   +------------------------+-----------------------+               |
                            | HTTPS, server to server               |
                            | Authorization: Bearer <JWT>           |
                            v                                        v
   +---------------------------------------------------------------------------+
   | Vercel project "oddvex-api" (services/api)                                |
   | FastAPI: /health, /v1/*                                                   |
   | State held in process memory today: rate limiter, cache, alert throttle   |
   +------------------+--------------------------------+-----------------------+
                      | PostgreSQL over TLS            | HTTPS (not built yet)
                      v                                v
            +-------------------+            +-------------------+
            | Neon PostgreSQL   |            | Resend            |
            | one database per  |            | transactional     |
            | environment       |            | email             |
            +-------------------+            +-------------------+

   Scheduler (does not exist) --runs--> scripts/evaluate_alerts.py --> Neon
   Release step (does not exist) --runs--> alembic upgrade head     --> Neon
```

Repo facts behind the diagram:

| Fact | Source |
|---|---|
| The browser never holds the token. It is in an `HttpOnly`, `SameSite=Lax` cookie named `ov_session` | `apps/web/src/lib/session.ts`, `apps/web/src/lib/api.ts` |
| Client components reach the API only through `/api/ov/*`, which allows a fixed list of `/v1` prefixes and rejects cross-origin writes | `apps/web/src/app/api/ov/[...path]/route.ts` |
| The web server reaches the API at `ODDVEX_API_URL` (server-only) | `apps/web/src/lib/api.ts` |
| The mobile app calls the API directly with a bearer token | `apps/mobile/src/api/client.ts`, `apps/mobile/README.md` |
| The API allows browser origins from `ODDVEX_CORS_ORIGINS` only, without credentials | `services/api/src/oddvex_api/main.py` |
| Rate limiting, caching and the alert-evaluation throttle are in process memory | `services/api/src/oddvex_api/ratelimit.py`, `cache.py`, `alerts/throttle.py` |
| No email is sent by any code path | `services/api/README.md`, "Notifications" |

## 3. Environments

| Environment | Purpose | Web | API | Database | Data | Who can reach it |
|---|---|---|---|---|---|---|
| Preview | One per pull request, for review | Preview deployment | Preview deployment, or shared staging API (to be decided: engineering) | Throwaway database or branch per preview (to confirm with vendor docs) | Synthetic only | Team only. Access protection to confirm with vendor docs |
| Staging | Rehearse deploys, migrations and rollback | Fixed staging hostname | Fixed staging hostname | Separate database, separate credentials | Synthetic only. Never a copy of production | Team only |
| Production | Real users | oddvex.com | `api.oddvex.com` (assumed) | Separate project or database, separate credentials | Real user data once G-03 is approved | Public |

Rules for all three:

- `ODDVEX_ENV=production` for staging and production, so the production safety checks in
  `services/api/src/oddvex_api/config.py` run in both (strong JWT secret, no `*` in CORS, no table auto-create, API
  docs off). Preview may use `development`.
- A different `ODDVEX_JWT_SECRET` per environment, so a token from one is rejected by the others.
- No production data in preview or staging (SECURITY_BASELINE BK-09, BK-10).
- While any environment is public and still on synthetic data, the "Synthetic data" label stays visible. The API
  reports `data_mode: "synthetic"` from `/health` and `/v1/meta`.

## 4. Deploying the web app (apps/web)

Repo facts:

- Next.js 16 with the App Router, built by `pnpm --filter @oddvex/web build` from the repository root.
- It is a pnpm workspace package and depends on `packages/types`.
- `next.config.ts` sets `output: "standalone"`, which the Dockerfile uses.
- It sends `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` and `Permissions-Policy`. It sends **no**
  Content-Security-Policy and no HSTS header.

Planned steps (not executed):

| Step | Action | Gate |
|---|---|---|
| 1 | Create the project, connect the GitHub repository, set the root directory to `apps/web` | G-02 |
| 2 | Confirm the install and build commands work for a pnpm monorepo with a workspace dependency | To confirm with vendor docs |
| 3 | Confirm whether `output: "standalone"` must be removed or is ignored on this host. If it must change, that is a code change by the web owner, not something to patch at deploy time | To confirm with vendor docs |
| 4 | Set the environment variables in section 7 for each environment | G-09 for production |
| 5 | Deploy to preview, then staging. Run the smoke test in section 10 | G-02 |
| 6 | Production deploy | G-03 |

Open points:

- `NEXT_PUBLIC_*` values are inlined at build time, so each environment needs its own build. Promotion of one build
  across environments: to confirm with vendor docs.
- Whether the host adds HSTS on its own: to confirm with vendor docs. CSP is a code gap either way (see
  `docs/compliance/THREAT_MODEL.md`).

## 5. Deploying the API (services/api)

Repo facts:

- Python 3.13 (`requires-python = ">=3.13"` in `services/api/pyproject.toml`), FastAPI, SQLAlchemy 2, psycopg 3.
- The package uses a `src/` layout. The ASGI app is `oddvex_api.main:app`, built lazily on first access.
- There is **no** Vercel configuration in the repository: no `vercel.json`, no function entrypoint file, no
  `requirements.txt`.
- The only tested way to run the API outside a developer machine is the Docker image, whose start command is
  `alembic upgrade head && uvicorn ...` (`services/api/Dockerfile`).

What must be confirmed before choosing how the API runs on Vercel:

| Question | Why it matters | Status |
|---|---|---|
| Is Python 3.13 a supported runtime? | The package refuses older versions | To confirm with vendor docs |
| Can a FastAPI app in a `src/` layout installed from `pyproject.toml` be deployed without restructuring? | No entrypoint or requirements file exists | To confirm with vendor docs |
| Can the existing Docker image be run as is? | It is the only CI-tested artifact | To confirm with vendor docs |
| How many instances run, and how long does one live? | Rate limiter, cache and alert throttle are per process. With more than one instance, or short-lived instances, the effective limits are looser and reset often | To confirm with vendor docs |
| Does `argon2-cffi` (native code) install on the runtime? | Password hashing depends on it | To confirm with vendor docs |
| What are the request duration and body-size limits? | `GET /v1/me/export` builds the whole export in memory; `ODDVEX_MAX_BODY_BYTES` defaults to 65536 | To confirm with vendor docs |
| What does `X-Forwarded-For` look like when it reaches the app, and how many proxies append to it? | `ODDVEX_TRUST_PROXY=true` uses the **last** entry and is only safe behind exactly one trusted proxy (`ratelimit.py`) | To confirm with vendor docs |

Consequences already known from the code, whatever the answers:

1. **Migrations cannot stay in the start command** if the API does not run from the Docker image. See section 6.
2. **Rate limiting needs a shared store** before more than one instance serves traffic. The code says so
   (`ratelimit.py` docstring, `services/api/README.md` "Limitations"). Adding a store is a code change and, if the
   store is paid, G-02.
3. **Web sign-in and sign-up share one rate-limit bucket today.** The web app calls `/v1/auth/login` and
   `/v1/auth/register` from server actions (`apps/web/src/lib/auth-actions.ts` through `api()` in
   `apps/web/src/lib/api.ts`), which do not forward the visitor's address. The API therefore sees the web server's
   address for every web user, and the limit is 10 per minute per address by default. This needs an engineering
   decision before real traffic. It is listed in the runbook under "Rate-limit complaints".
4. **Database connections.** `make_engine` creates a normal SQLAlchemy pool with `pool_pre_ping=True`
   (`db/session.py`). Whether to use the database vendor's pooled connection string, and what pool size suits
   short-lived instances, is to confirm with vendor docs and then test in staging.

Planned steps (not executed):

| Step | Action | Gate |
|---|---|---|
| 1 | Answer the questions above and record the links | None |
| 2 | Add whatever entrypoint or configuration the chosen method needs. This is a change to `services/api`, by its owner, through a pull request | None |
| 3 | Create the project, set the environment variables in section 7 | G-02, G-09 |
| 4 | Deploy to staging with `ODDVEX_ENV=production`. Confirm it refuses to start with a weak or missing `ODDVEX_JWT_SECRET` | G-02 |
| 5 | Run migrations as a release step (section 6), then the smoke test (section 10) | G-02 |
| 6 | Production deploy | G-03 |

## 6. Database and migrations

Repo facts:

- Migrations are Alembic revisions 0001 to 0003 in `services/api/alembic/versions/`. All three are additive.
  Each has a `downgrade()` that drops what it added.
- Alembic reads the URL from `DATABASE_URL`, or from `-x url=...` (`services/api/alembic/env.py`).
- `postgres://` and `postgresql://` URLs are rewritten to use psycopg 3 (`db/session.py`).
- In production the app never creates tables on its own (`should_auto_create_tables` in `config.py`).
- The full test suite runs on PostgreSQL 16 in CI. `docker-compose.yml` uses PostgreSQL 17. **Neither is necessarily
  the version Neon runs.** Pick a version and test against it. To be decided: engineering.

Migration procedure for a release (not executed anywhere yet):

1. Read every new migration. Classify it:
   - **Additive** (new table, new nullable column, new index): may run without a gate.
   - **Destructive** (drop or rewrite a table or column that holds data, irreversible transform, bulk delete):
     **stop. G-08. Founder approval and a verified backup first.**
2. Confirm a recent backup or restore point exists for the target database (section 9).
3. Run `alembic upgrade head` against the target database **as its own release step, before the new application
   code takes traffic.** In `services/api`: `DATABASE_URL=<target> alembic upgrade head`. Where this step runs
   (a CI job with a protected environment, or an operator's machine) is to be decided: engineering, and needs G-09
   because it uses a production credential.
4. Run `alembic current` and confirm it prints the expected head revision.
5. Deploy the application.
6. Never run `alembic downgrade` in production without G-08. Every existing downgrade drops data.

Rule for writing migrations from now on: a release must be able to roll the application back without rolling the
schema back. That means new code tolerates the old schema for one release, or old code tolerates the new schema
(expand, then contract in a later release). See `ROLLBACK_PLAN.md`.

Neon items to confirm with vendor docs: supported PostgreSQL versions; pooled versus direct connection strings and
which one migrations must use; TLS parameters required in the URL; whether a database can be branched for previews;
behaviour when a database has been idle (cold start latency against the web app's 8 second API timeout in
`apps/web/src/lib/api.ts`).

## 7. Environment variables

Names only. Values are never written in this repository. "Secret" means it must live in the host's secret store and
must not be exposed to the browser or to preview builds from forks.

### API (`services/api/.env.example`, `services/api/src/oddvex_api/config.py`)

| Variable | Secret | Production notes |
|---|---|---|
| `ODDVEX_ENV` | No | `production` for staging and production |
| `DATABASE_URL` | **Yes** | Contains the database password |
| `ODDVEX_JWT_SECRET` | **Yes** | At least 32 characters. The app refuses to start in production with the built-in development value |
| `ODDVEX_JWT_TTL_MINUTES` | No | Default 60 |
| `ODDVEX_CORS_ORIGINS` | No | Explicit list. `*` is refused in production. Only needed for browser callers; the web app calls server to server |
| `ODDVEX_TRUST_PROXY` | No | Only `true` behind exactly one trusted proxy. See section 5 |
| `ODDVEX_RATE_LIMIT_ENABLED` | No | Leave `true` |
| `ODDVEX_RATE_LIMIT_AUTH_PER_MINUTE` | No | Default 10 |
| `ODDVEX_RATE_LIMIT_ASSISTANT_PER_MINUTE` | No | Default 20 |
| `ODDVEX_RATE_LIMIT_WINDOW_SECONDS` | No | Default 60 |
| `ODDVEX_STALE_LIVE_SECONDS` | No | Default 120 |
| `ODDVEX_STALE_PREGAME_SECONDS` | No | Default 900 |
| `ODDVEX_SYNTHETIC_SEED` | No | Only meaningful while the synthetic provider is in use |
| `ODDVEX_ADMIN_EMAILS` | No, but sensitive | Grants the admin role. Treat changes as an access change (G-09). See the runbook |
| `ODDVEX_AUTO_SEED_DEMO` | No | Ignored in production. Leave unset |
| `ODDVEX_DEMO_PASSWORD` | **Yes** if a demo account is ever seeded outside development | The documented default is public. Never use it on a reachable environment |
| `ODDVEX_DB_AUTO_CREATE` | No | Always off in production regardless of value |
| `ODDVEX_SYNC_MAX_ATTEMPTS` | No | Default 3 |
| `ODDVEX_ALERT_EVAL_MIN_SECONDS` | No | Default 30 |
| `ODDVEX_MAX_BODY_BYTES` | No | Default 65536 |
| `ODDVEX_LOG_LEVEL` | No | Default `INFO` |

Not in the code yet: an email API key and sender address (email flows are in progress and write to an outbox table
instead of sending), feature-flag settings, entitlement settings. Add their names here when
`services/api/.env.example` gains them.

### Web (`apps/web/.env.example`, `apps/web/src/lib/*.ts`)

| Variable | Secret | Notes |
|---|---|---|
| `ODDVEX_API_URL` | No, but server-only | Where the Next.js server reaches the API. Must be `https://` outside local development |
| `NEXT_PUBLIC_SITE_URL` | No | Public origin for canonical URLs and the sitemap. Falls back to `https://oddvex.com` (`src/lib/site.ts`). Inlined at build time |
| `NEXT_PUBLIC_CONTACT_EMAIL` | No | Shown on `/contact` when set. Unset today, so the page shows a placeholder. Setting it publishes an address real people will write to (G-06) |
| `ODDVEX_INSECURE_COOKIES` | No | Read in `src/lib/session.ts`; **not listed in `apps/web/.env.example`**. `true` drops the `Secure` flag from the session cookie. Must never be set on a deployed environment |

### Mobile (`apps/mobile/.env.example`)

| Variable | Secret | Notes |
|---|---|---|
| `EXPO_PUBLIC_API_URL` | No | Inlined into the bundle. Must be `https://` for release builds (`apps/mobile/README.md`) |

The mobile app is not deployed by this plan. Store builds are G-04.

## 8. DNS cut-over for oddvex.com (G-03)

Not executed. Current registrar, DNS host and existing records are unknown to this repository. To be decided and
confirmed: Founder.

| Step | Action |
|---|---|
| 1 | Record the current DNS zone in full (every record, with TTL) before changing anything. Keep the copy |
| 2 | Check for existing mail records (MX, SPF, DKIM, DMARC). Do not disturb them. Email sending records for Resend are a separate change under G-06 |
| 3 | Lower the TTL on the records that will change, and wait out the old TTL |
| 4 | Add the domain to the web project and the API hostname to the API project. Record the exact records the host asks for. To confirm with vendor docs |
| 5 | Confirm certificates are issued for each hostname before switching traffic. To confirm with vendor docs |
| 6 | Set `NEXT_PUBLIC_SITE_URL`, `ODDVEX_API_URL` and `ODDVEX_CORS_ORIGINS` to the final hostnames and redeploy |
| 7 | Change the records. Founder gives the go |
| 8 | Run the smoke test in section 10 against the public hostnames |
| 9 | Watch error rates and logs. Rollback is restoring the records saved in step 1 |
| 10 | Raise the TTL again once stable |

Before step 7, decide whether the public site may launch while legal pages are drafts and data is synthetic. That is
G-10 and G-03, not an engineering call.

## 9. Scheduler for alert evaluation

**No scheduler exists.** Repo facts (`services/api/README.md`, `services/api/scripts/evaluate_alerts.py`):

- Alert rules are evaluated only when a user reads their notifications, when a client calls
  `POST /v1/alerts/evaluate`, or when `scripts/evaluate_alerts.py` runs.
- The script evaluates every user who has active rules, one transaction per user, and is idempotent and safe to run
  while the API serves requests. It exits with status 1 if any user failed.
- Without a scheduler, a `game_start` alert nobody opened the app for expires silently.

Options, none chosen. To be decided: Founder (cost, G-02) and engineering (fit).

| Option | Needs | To confirm |
|---|---|---|
| The host's scheduled-job feature calls the script or an endpoint | The script is a CLI, not an HTTP route. An authenticated internal endpoint would be new code | Whether scheduled jobs exist on the chosen plan, their minimum interval and maximum duration. To confirm with vendor docs |
| A scheduled GitHub Actions workflow runs the script against the production database | A production `DATABASE_URL` in GitHub secrets (G-09). Changes to `.github/` | Timing precision of scheduled workflows. To confirm with vendor docs |
| A small always-on worker elsewhere | Another paid service (G-02) | — |

Whatever is chosen, the interval sets how late an alert can be. That figure must be stated to users (the screens
already explain that alerts are checked when the app is opened). Do not describe alerts as "real time".

## 10. Smoke test after every deploy

Run against the environment just deployed. Replace hostnames.

| # | Check | Expect |
|---|---|---|
| 1 | `GET <api>/health` | 200, `status: "ok"`, the expected `version`, `data_mode` as expected |
| 2 | `GET <api>/v1/meta` | 200, expected `provider` |
| 3 | `GET <api>/docs` | 404 in staging and production (docs are disabled when `ODDVEX_ENV=production`) |
| 4 | `GET <api>/v1/admin/overview` without a token | 401 |
| 5 | Web `/` | 200 |
| 6 | Web `/app` | 200 or a redirect to `/login` |
| 7 | Sign up with a test address, log a bet, export data, delete the account | All succeed. Staging only, unless the Founder approves a production test account |
| 8 | Response headers on the API | `X-Request-ID`, `Strict-Transport-Security`, `X-Content-Type-Options` present |
| 9 | `alembic current` | Expected head revision |

`/health` does not query the database (`services/api/src/oddvex_api/api/data.py`). Check 7 or 9 is what proves the
database is reachable.

## 11. Backups and recovery to confirm with Neon

Targets proposed in `docs/compliance/SECURITY_BASELINE.md` (BK-01 to BK-07) are proposals awaiting Founder
confirmation, not commitments. Confirm each item with vendor docs and record the answer.

- [ ] Is point-in-time recovery available on the chosen plan, and how far back?
- [ ] Are backups or history encrypted at rest? Is the database?
- [ ] How is a restore performed: in place, or to a new database or branch? How long did a test restore take?
- [ ] Can backups be kept in a separate account or region (BK-04)?
- [ ] What happens to history when a database or project is deleted?
- [ ] Does restoring bring back deleted accounts? It will. A deletion ledger (ids only) must be re-applied after any
      restore (PRIVACY_AND_DATA section 4, step 9). **No deletion ledger exists in the code today.**
- [ ] A restore test is run in staging and its recovery time and data loss are recorded before launch (BK-05).

To be decided: recovery point and recovery time targets. Founder, against cost.

## 12. Email (Resend)

- No code sends email today. Email verification and password-reset flows are in progress in the API and write to an
  outbox table instead of sending.
- Connecting a real sender needs G-02 (account), G-09 (API key), G-06 (sending to real people), G-13 (sub-processor)
  and counsel input on sender identity and footer content (COMPLIANCE_OVERVIEW AD-08).
- Sending-domain records (SPF, DKIM, DMARC) are DNS changes. Plan them with section 8 and do not break existing mail.
- Exact records, sending limits and data retention: to confirm with vendor docs.

## 13. Cost drivers to check on the vendors' live pricing pages

No figures are given here on purpose. Check each on the vendor's current pricing page and record the date checked.
Approver for all spend: Founder (G-02).

| Vendor | Drivers to check |
|---|---|
| Vercel | Plan tier and seats; whether the plan permits commercial use; function invocations and compute time; bandwidth and data transfer; build minutes; number of projects; preview deployments; scheduled jobs; log retention; any firewall or protection features |
| Neon | Plan tier; compute time and size; storage; history or point-in-time retention window; number of projects, branches and databases; data transfer; connection limits |
| Resend | Plan tier; emails per month and per day; number of sending domains; log retention; dedicated IP if ever needed |
| GitHub | Actions minutes if scheduled jobs or deploy steps are added |
| Not chosen yet | Shared store for rate limiting; error monitoring; uptime checks; log storage beyond the host's retention |

## 14. Alternatives (trade-offs only)

| Option | In favour | Against |
|---|---|---|
| **Hostinger VPS running the existing Docker images** | Uses the two images CI already builds and smoke-tests. One long-lived API process, so the in-memory rate limiter and cache behave as written. The container's own start command runs migrations. `scripts/evaluate_alerts.py` can run from cron on the same machine, as `.env.example` suggests | The team owns the operating system, patching, TLS certificates, firewall, backups, monitoring and recovery. PostgreSQL would be self-managed unless a managed database is added. A single machine is a single point of failure. No preview environments without building them |
| **AWS** | Can run the existing images on a managed container service next to a managed PostgreSQL with scheduled jobs in the same account. Fine-grained access control | Most setup and the most to learn and secure for a small team. More moving parts to price. Easy to misconfigure |
| **Vercel + Neon + Resend (this plan)** | Least operations work. Preview deployments per pull request. Managed database | The API has no tested deployment path there yet. In-memory rate limiting, cache and throttle do not fit short-lived or multiple instances. Migrations and the alert scheduler need a home. Several capabilities above are still to confirm |

A mixed option (web on Vercel, API as the Docker image on a container host) keeps the tested image and long-lived
process. To be decided: Founder, on engineering's recommendation after section 5 is answered.
