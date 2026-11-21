# Operations runbook

Last updated: 2026-11-21 · Status: **written from the code at release `2b0c7c1` and from the deploys of the private
preview on the Hostinger VPS.** Deploys through `ops.sh` have run on the server (`docs/product/BUILD_STATUS.md`).
Restore, rollback, the automatic put-back, secret rotation and the first administrator have not been done on the
server: treat those procedures as untested there until they have been rehearsed.

Scope: the FastAPI service (`services/api`), the Next.js app (`apps/web`), the database, the worker and the backup
container, as run on the preview (`hostinger/compose.yaml`). Incident handling, severity and communication are in
`docs/compliance/INCIDENT_RESPONSE.md`. When to roll back is in `ROLLBACK_PLAN.md`. The server itself, the ops
container and every action are described in `hostinger/README.md`; this runbook does not repeat its details.

Nobody has a shell on the server. Every operation is an `ACTION` of `hostinger/ops.sh`, sent to the one-shot ops
container (`hostinger/ops.compose.yaml`) through Hostinger's Docker Manager. Commands written as `alembic ...` or
`python scripts/...` below are for a developer machine (in `services/api`, with that environment loaded) or are what
an action runs inside a container on the server.

## 1. What exists and what does not

| Thing | State | Effect |
|---|---|---|
| Deployed environment | The private preview: `preview.oddvex.com` (password) and `api-preview.oddvex.com` (no password, open to the internet). Production mode, synthetic data | Real people can create accounts on the API. Treat its database as holding personal data |
| Containers | `db` (PostgreSQL 17), `oddvex-api`, `oddvex-web`, `worker`, `backup`; the migration container runs once per deploy | `oddvex-api` and `oddvex-web` are on the server's shared proxy network; the rest only on the project's own network |
| Background worker | The `worker` container runs `scripts/evaluate_alerts.py` and `scripts/grade_picks.py` every two minutes | Alerts fire without the app open. A failed pass is logged and the loop goes on |
| Backups | The `backup` container writes one dump a day to `/opt/oddvex/backups`, kept 14 days by default. Every deploy that finds a schema dumps first | The dumps are on the same disk as the database: no protection against losing the server |
| Feature flags | Stored in the database, defaults in code; switched with `PUT /v1/admin/flags/{key}` | Needs an administrator. The preview has none (section 8) |
| Monitoring, alerting, uptime checks, error tracking | None | Failures are found by people. `ACTION=status` is the only health report |
| On-call roster | None. Section 12 is a template with blanks | Founder |
| Email | Nothing is sent. Emails are written to the `email_outbox` table. `email_flows` is off in production | Nobody can verify an address or reset a password on the preview |
| Shared rate-limit store | None. All limits and sign-in counts are in the API process's memory | A restart of the API clears them |
| Deletion ledger | None | A restore brings deleted accounts back with nothing to re-delete them from (`ROLLBACK_PLAN.md` section 5.4) |
| Status page | None | No way to tell users about an incident except the site itself |
| Secret rotation | No action for it (section 7) | A leaked secret can be contained only by stopping the stack |

## 2. Health checks

| Check | How | Healthy | Notes |
|---|---|---|---|
| Everything at once | `ACTION=status` | Containers running and healthy; `api health: 200`; `web home: 200`; database revision as expected; a daily dump less than 26 hours old; "no OddVex container answers to 'api' or 'web'" | Changes nothing. Also lists the images kept for a rollback, the databases kept by restores and the last five operations |
| API liveness | `curl -fsS https://api-preview.oddvex.com/health` | 200 with `"status":"ok"` and `"database":"ok"` | `/health` runs `SELECT 1`. With the database down it still answers **200**, with `"status":"degraded"` and `"database":"error"`. Read the fields, not the status code. The image's Docker `HEALTHCHECK` and the probes in `ops.sh` check the status code only, so they report a healthy API while the database is down |
| Metadata | `curl -fsS https://api-preview.oddvex.com/v1/meta` | 200 with `data_mode`, `provider`, `version`, `server_time`, `notice` | `data_mode` comes from the provider (`synthetic` on the preview). Does not touch the database |
| Web | `https://preview.oddvex.com/` | 401 without the password, 200 with it | `/app` answers 200 or a redirect to `/login` |
| Provider and counts | `GET /v1/admin/overview` with an admin token | `provider_health.status` is `ok` | Needs an administrator. Each read writes one `admin.read` audit row |
| Version deployed | `ACTION=status`, "running images" | The image tag is the short commit of the release | `version` in `/health` is the package version (`0.1.0`), the same for every commit |

## 3. Logs and request ids

The API writes JSON lines to standard output (`logging_config.py`, `middleware.py`). One line per request, logger
`oddvex.access`, message `request`, with `request_id`, `method`, `path`, `status`, `duration_ms` and `client_ip`.
**The query string is not logged**: the line has the path only. uvicorn's own access log is off, twice over: the
preview's compose file starts uvicorn with `--no-access-log`, and `configure_logging` removes the access logger's
handlers whatever the start command says. The API container that ran before release `4092395` did write uvicorn's
access log, with query strings; that container was removed by the `4092395` deploy, and whether its log went with it
depends on Docker's log driver on the server, which has not been checked.

Other lines to know:

| `logger` | `message` | Meaning |
|---|---|---|
| `oddvex.app` | `startup` | Process started. Carries `env` and `provider` |
| `oddvex.app` | `demo_seed` | Demo account seeded at startup. Never appears in production |
| `oddvex.access` | `unhandled_error` | An exception escaped a route. Carries `request_id`, `method`, `path` and a stack trace in which the message of a database error is withheld (no bound values). The client got `500 internal_error` |
| `oddvex.health` | `health_database_check_failed` | `/health` could not run `SELECT 1` |

Following one request:

1. Every API response has an `X-Request-ID` header. A caller's `X-Request-ID` of 8 to 64 characters from
   `A-Z a-z 0-9 . _ -` is reused; otherwise the API makes one.
2. The web server gives every page request a request id and sends it to the API with each call it makes for that
   page. The web app's error screen shows "Reference <id>": the request id of the failed API call, or the digest
   Next.js made when there was no API call (`docs/architecture/ADR-0003-web-architecture.md`).
3. Search the API log for that `request_id`. If the request changed data, the same id is in `audit_log.request_id`.

Reading the logs on the server: no `ops.sh` action prints the API's or the web server's log. A failed deploy prints
their last 40 lines; `ACTION=status` prints the last lines of the backup container. Anything else goes through the
Hostinger panel (to confirm). `compose.yaml` sets no log size limit or retention for the containers; the Docker
daemon's defaults on this server were not checked.

Limits:

- `client_ip` in the request line is the direct peer: on the preview that is the shared Caddy or the web container,
  never the visitor. Audit rows, the rate limits and the sign-in counts use `client_ip()` from `ratelimit.py`, which
  takes the forwarded address because the preview runs with `ODDVEX_TRUST_PROXY=true` (section 4.4).
- Logs contain IP addresses and paths. They are personal data. Retention is to be decided (PRIVACY_AND_DATA section 3
  proposes 30 to 90 days): Founder with counsel.
- The shared Caddy keeps its own logs, which this project does not control.

## 4. Common failures

### 4.1 API unreachable

| | |
|---|---|
| What users see (web) | In the app: "OddVex can't reach its data service" with a "Try again" button (`apps/web/src/app/app/error.tsx`). In forms and client components: `503 api_unavailable` from `/api/ov/*`, "OddVex can't reach its data service right now. Try again in a moment." |
| What users see (mobile) | The screen's error state. A saved session survives |
| Cause candidates | API container down or restarting; database down (`/health` then says `degraded`); API slower than the web timeouts (8 s for server fetches, 10 s for the bridge); the API container killed for memory (limit 768 MB) |
| Check | `ACTION=status`: container states, `api health`, database revision. From outside: `/health` and read `status` and `database` |
| Fix | A container that exited is restarted by Docker (`restart: unless-stopped`). If it will not start, read the first error in its log: in production the API refuses to start when `ODDVEX_JWT_SECRET` is missing, the development value or shorter than 32 characters, or when `ODDVEX_CORS_ORIGINS` contains `*`. A bad release: `ROLLBACK_PLAN.md` |
| Marketing pages | Prerendered pages keep working without the API |

### 4.2 Provider degraded

The only provider on the preview is `SyntheticProvider`, which has no external dependency and always reports `ok`,
so this cannot happen there yet. The procedure matters once a licensed provider exists (G-01).

| | |
|---|---|
| Signal | `provider_health.status` of `degraded` or `down` on the admin overview; prices marked stale across the board |
| Built-in protection | The API, not the client, marks a quote stale (`docs/architecture/ADR-0002-data-and-freshness.md`). Stale, suspended and unavailable quotes are excluded from best price and consensus |
| What to do | Do not hide the stale labels. Do not raise the stale thresholds to make data look fresh. Follow INCIDENT_RESPONSE 5.4 and 5.7 |
| Missing | A per-feed kill switch and freshness monitoring |

### 4.3 Migration failure

Migrations are a deploy step (section 5): `ACTION=deploy` takes a dump, then runs `alembic upgrade head` once in a
one-shot `migrate` container, and replaces the containers only if that succeeded. The API container on the preview
never migrates when it starts: the compose file overrides the image's command.

| | |
|---|---|
| Signal | The deploy ends with `DEPLOY FAILED: the migration step failed`. No container was replaced: the previous release is still serving |
| What the output says | Whether the revision changed before the failure. If it did, or could not be read, it prints the name of the pre-deploy dump and the three lines that restore it |
| First | Stop. Do not edit the database by hand. Do not run a downgrade (G-08: every downgrade drops tables or columns; section 6) |
| Check | `ACTION=status` shows the revision. On PostgreSQL, DDL in a failed migration is normally rolled back with its transaction, so the revision should be the old one. Confirm, do not assume |
| Fix | Fix the migration in a pull request and deploy again. If the schema is half-applied: incident (INCIDENT_RESPONSE 5.8) and `ROLLBACK_PLAN.md` section 5.2 |

### 4.4 Rate limits and sign-in refusals ("Too many attempts")

How it works (`ratelimit.py`, `auth/router.py`, `assistant/router.py`, `config.py`):

- Per IP address: `auth` (register, login, password change and the email routes, default 10 a minute) and
  `assistant` (default 20 a minute), over `ODDVEX_RATE_LIMIT_WINDOW_SECONDS` (60).
- Per account, for failed logins, over `ODDVEX_ACCOUNT_LIMIT_WINDOW_SECONDS` (900, so 15 minutes): 8 failures for one
  email from one client network (`ODDVEX_LOGIN_MAX_FAILURES`) refuse that email from that network only; 50 failures
  for one email from all networks together (`ODDVEX_LOGIN_MAX_FAILURES_PER_EMAIL`) refuse that email from everywhere.
  A network is an IPv4 address or an IPv6 /64. The counts are kept for an address whether or not it has an account.
- Per user, whatever the address: 120 bet and sync writes a minute, 2,000 a day, 10 data exports an hour, 8 streamed
  responses at once.
- A refused request gets HTTP 429, code `rate_limited`, a `Retry-After` header and `details.retry_after_seconds`. The
  web and mobile apps show "Too many attempts" with when to try again.
- Everything is counted in the API process's memory. A restart clears every count.

Known causes of refusals:

| Cause | Why | What to do |
|---|---|---|
| Someone sent 50 failed logins for a user's email | The per-email ceiling refuses that email from every network for up to 15 minutes. That is the price of stopping guessing spread over many addresses | Wait out the window (the 429 says how long). Or restart the API, which clears every count, including the attacker's. Or raise `ODDVEX_LOGIN_MAX_FAILURES_PER_EMAIL`, which makes guessing against every account easier. **On the preview neither the restart nor the setting is one step:** `ops.sh` has no restart action (`ACTION=stop` then `ACTION=deploy` restarts every container, with a short outage; not rehearsed for this), and the setting is not passed by `hostinger/compose.yaml` nor accepted by `ACTION=setenv`, so changing it there needs a change to those two files first. With `email_flows` off there is no password reset to fall back on |
| Many users behind one address | Offices, campuses, mobile carriers | Inherent to per-IP limits |
| `ODDVEX_TRUST_PROXY` wrong | `false` behind a proxy: everyone shares the proxy's address. `true`: the API believes `X-Forwarded-For` from any peer | On the preview it is `true`. Visitors reach the API only through Caddy or the web server, which send the visitor's address. But any container on the server's shared proxy network can call the API directly with an invented address, so it is never refused by the per-IP or per-network limits and writes that address into audit rows. The per-email ceiling and the per-user limits still apply. See `docs/compliance/THREAT_MODEL.md` S-6 |

Changing a limit is a configuration change to a production environment: decide who owns production configuration
first (DECISION_LOG O-10). Never set `ODDVEX_RATE_LIMIT_ENABLED=false` in production.

### 4.5 Sync failures

Only the mock sync provider exists. No real sportsbook is connected.

| Symptom | Meaning | Action |
|---|---|---|
| HTTP 502 `sync_failed`, with `details.run_id`, `details.retryable`, `details.attempts` | The provider failed on every attempt (`ODDVEX_SYNC_MAX_ATTEMPTS`, default 3). A failed run is recorded and the user gets a `sync_finished` notification | If `retryable`, the user can press "Sync now" again. Re-running never duplicates bets |
| HTTP 409 `sync_conflict`, `details.retryable: true` | Two imports of the same connection ran at once. The loser wrote nothing | Retry |
| A user asks for run history | `GET /v1/sync/connections/{id}/runs` | Shows status, attempts, counts, error message |

The mock provider has a deliberate failure switch for demos and tests. A failure on the mock is not an outage.

### 4.6 Alerts not firing

Rules are evaluated when:

1. the `worker` container's loop runs `scripts/evaluate_alerts.py`, every two minutes on the preview;
2. the user reads `GET /v1/notifications` or `GET /v1/notifications/unread-count` (at most once per
   `ODDVEX_ALERT_EVAL_MIN_SECONDS` per user, default 30, tracked per process);
3. a client calls `POST /v1/alerts/evaluate` ("Check now" on mobile).

Checklist:

| Question | Where to look |
|---|---|
| Is the worker running? | `ACTION=status`: the `worker` container. Its log has `evaluate_alerts failed` when a pass failed |
| Is the rule `active`? | `GET /v1/alerts`. `triggered` rules fired once and must be set again. `expired` rules lost their event. `paused` rules are off |
| Did the condition hold at the moment of an evaluation? | Prices are not stored. A price that touched the threshold and moved away between two evaluations, up to two minutes apart, was never seen |
| Is that notification kind switched off? | `GET /v1/me/notification-preferences`. A disabled kind creates no notification, but the rule still changes state |
| Does the user expect a push or an email? | There is none. Notifications are in-app only |

### 4.7 Sign-in problems after a change

| Symptom | Cause |
|---|---|
| Every user is signed out at once | `ODDVEX_JWT_SECRET` changed (section 7) |
| Some users are signed out after a restore | The restored dump holds the accounts as they were: an account created after the dump no longer exists, and one that logged out or changed its password after it has an older token version, so its current tokens are refused |
| One user is signed out everywhere | They changed their password or logged out: both end every session of the account by design |
| A user is signed out after an hour | Token lifetime (`ODDVEX_JWT_TTL_MINUTES`, default 60). There are no refresh tokens |
| `401 account_suspended` | An administrator suspended the account |
| "I forgot my password" | No recovery on the preview: `email_flows` is off and an administrator cannot reset a password. See `docs/product/SUPPORT_READINESS.md` section 3.6 |

### 4.8 Backups failing

| | |
|---|---|
| Signal | `ACTION=status` warns that the newest daily dump is more than 26 hours old and prints the last lines of the backup container, which say `BACKUP FAILED` with the count of failures in a row |
| Behaviour | A failed dump deletes nothing and is tried again after an hour. Old dumps are deleted only after a new one was written, is not empty and reads back |
| Check | Disk space on the server (nothing here watches it); whether `db` is healthy |
| Nothing alerts | Nobody is told unless someone runs `ACTION=status` |

## 5. Deploying and going back

Full detail: `hostinger/README.md`, sections "What a deploy does" and "Going back". When to roll back:
`ROLLBACK_PLAN.md`.

| Action | Variables | Use |
|---|---|---|
| `status` | | Read the state. Changes nothing. Send it after `restore`, `admin` and `stop`, so that a restart of the ops project repeats something harmless |
| `deploy` | `REF` (default `main`) | Ship a release |
| `rollback` | `REF` (required), `OPS_REF` (default `main`) | Run an earlier release again |
| `restore` | `DUMP`, `CONFIRM` | Replace the database with a dump |
| `setenv` | `KEY`, `VALUE` | Change one allow-listed, non-secret setting in `/opt/oddvex/.env` |
| `admin` | `EMAIL` | Make a listed address the administrator (section 8) |
| `caddy` | | Add the OddVex block to the shared Caddy (done once, on 2026-11-18) |
| `stop` | | Stop the stack, keeping the database volume and the dumps |

A deploy, in order: refuses to build with less than about 2.5 GB of memory free; builds both images in a separate
build container limited to 2 GB of memory and one CPU, and stops before touching anything if the build fails; dumps
the database (`predeploy-<time>-<old>-to-<new>.dump`, checked readable, newest five kept); applies migrations in the
one-shot `migrate` container while the old release keeps serving; removes containers of the old service names `api`
and `web`; starts the new release and waits until it is healthy and answers through the shared network.

**The automatic put-back.** If the new release does not become healthy, the deploy starts the previous release's
images again, says `THE PREVIOUS RELEASE ... WAS PUT BACK` (or why nothing was put back), and ends with status 2. A
migration applied in that deploy is **not** undone: the previous release then runs on the newer schema, which works
only while migrations are additive. The output names the pre-deploy dump and the three lines that would restore it.
Restoring is a decision, not automatic (`ROLLBACK_PLAN.md` section 5.4). The put-back has not happened on the server.

The build ceiling: `ops.sh` reads the limits back from Docker before it builds and stops if they are missing or the
server lacks cgroup v2 with private cgroup namespaces. That the ceiling holds a build step that needs more than 2 GB
is expected from how Docker and cgroup v2 work; it has not been observed on the server. `ODDVEX_BUILD_LIMITS=off`
builds without it and says so; it is not the normal way.

After a deploy: run the smoke test in `DEPLOYMENT_PLAN.md` section 10 and record the deploy (section 11).

Restore (`ACTION=restore`): without `CONFIRM` it only shows the dump. With `CONFIRM` equal to `DUMP` it dumps the live
database first (`prerestore-<time>.dump`), loads the chosen dump into a new database, stops the API, worker, backup
and web containers, swaps the two databases by name, starts the same containers again, and keeps the replaced
database as `oddvex_replaced_<time>`. The same request sent twice does not restore twice. It is rehearsed in tests
against PostgreSQL 16, not on the server.

## 6. Rolling back a migration

**Default: do not.** Roll the application back (`ACTION=rollback`) and leave the schema where it is. Migrations 0001
to 0007 are additive, so an older release runs against the newer schema, and on the preview an older image starts
even when the database is ahead of it, because the API container does not migrate at start.

A schema downgrade is a destructive migration (G-08). No action runs one. Each existing `downgrade()` drops data:

| Downgrade | Drops |
|---|---|
| 0007 to 0006 | `community_reserved_handles`; `community_reports.target_text_snapshot` and `target_summary_snapshot` |
| 0006 to 0005 | `bets.client_request_id` and its unique index |
| 0005 to 0004 | The seven community tables (`community_profiles`, `community_picks`, `community_comments`, `community_follows`, `community_likes`, `community_blocks`, `community_reports`); `users.search_key`; `bets.sportsbook_key` |
| 0004 to 0003 | `feature_flags`, `email_tokens`, `email_outbox`; `users.plan`, `users.status`, `users.email_verified_at`, `users.last_login_at`. Losing `users.status` lifts every suspension |
| 0003 to 0002 | `alert_rules`, `notifications`, `notification_preferences`, `stake_reminders` and everything in them |
| 0002 to 0001 | `watchlist_items`; `users.token_version`, `users.password_changed_at`; `bets.settled_by`; `bet_legs.outcome_key` |
| 0001 to base | Every table |

To go back to the data as it was before a deploy, restoring that deploy's pre-deploy dump is the tool, not a
downgrade. It discards everything written since the dump; that is the Founder's decision (`ROLLBACK_PLAN.md` 5.4).

## 7. Settings and secrets

`/opt/oddvex/.env` (mode 600) holds the database password, the JWT secret, the public URL and the settings listed in
`hostinger/README.md`, section "Settings". `ACTION=setenv` changes one of `ODDVEX_CONTACT_EMAIL`,
`ODDVEX_ADMIN_EMAILS`, `ODDVEX_PASSWORD_HASH_CONCURRENCY`, `ODDVEX_PASSWORD_HASH_WAIT_SECONDS` and
`ODDVEX_BACKUP_KEEP_DAYS`, and refuses every other key. A change takes effect at the next `ACTION=deploy`. Any other
API setting reaches the container only if `hostinger/compose.yaml` passes it; today it passes `ODDVEX_ENV`
(`production`), the database URL, the JWT secret, the CORS origin, the web base URL, the admin list,
`ODDVEX_TRUST_PROXY` and the two hashing settings.

### Rotating the JWT secret

What it is: `ODDVEX_JWT_SECRET` signs every access token with HS256 (`auth/security.py`). One secret, no key id, no
support for two valid secrets at once. Rotation signs every user out on web and mobile at once; passwords are
unaffected and nothing is lost except unsaved input on screen.

**There is no action for it on the preview.** `ACTION=setenv` refuses the secrets, and nobody has a shell to edit
`/opt/oddvex/.env`. Rotating needs either a new `ops.sh` action (a code change, through a pull request) or direct
access to that file, which this setup does not give. Do not delete `/opt/oddvex/.env` to get a new one: the next
deploy would generate a new database password as well, and the existing database keeps the old one, so the API could
no longer connect. On a suspected leak (INCIDENT_RESPONSE 5.2) until a rotation action exists: `ACTION=stop` takes
OddVex offline, then decide with the Founder (G-09).

When a rotation action exists, the procedure is: generate at least 32 random characters on the server, never paste
them anywhere; deploy so every container picks the value up; check `/health`; confirm an old token now gets
`401 invalid_token`; record who, when and why in `docs/product/DECISION_LOG.md`, never the value.

The web app does not hold the secret. Only the API does.

## 8. Granting and removing admin

The rule (`deps.py`, `sync_admin_role`): an account is an administrator exactly when its address is in
`ODDVEX_ADMIN_EMAILS` **and** its email address is verified. The rule is applied at login, when an address is
confirmed and on **every token use**:

- A listed, verified account is promoted at its next request (`role.granted` in the audit log). No new login is
  needed.
- An account that holds the role without meeting the rule is demoted at its next request (`role.removed`, with the
  reason `not_in_admin_emails` or `email_not_verified`). A direct database update of `users.role` does not last: the
  next request puts the role back in line with the rule.
- Matching is case-insensitive on the whole address. The API reads the list at start, so a change needs a deploy.
- Listing an address gives nobody the role by itself. Having registered a listed address first gains nothing.

What an administrator can do (`api/admin.py`, `community/admin_router.py`, the web pages under `/app/admin`): read the
overview, list and search every user with their email address, suspend and unsuspend accounts (not their own and not
another administrator's), set a user's plan, export or delete a user's account with a reason, read the audit log and
the email outbox, switch **any** feature flag, and moderate community reports while `community` is on. Turning on
`premium_gating` is a pricing decision and `community` or `community_leaderboard` need the reviews in the roadmap, so
granting the role delegates the ability to take those Founder decisions. Every change is audited with the acting
administrator; reads of the overview, the user list, the email outbox and the report queue write one `admin.read`
row each; reading the audit log and the flag list is not recorded.

The preview has no administrator: `ODDVEX_ADMIN_EMAILS` is empty on the server.

To grant (G-09: this is production access):

1. The Founder approves the specific person and address. Record it in the decision log. Do not use
   `support@oddvex.com` or any other published address: this repository is public and names it, so it is the first
   address a stranger would register. Use a personal address that only the administrator reads.
2. `ACTION=setenv` with `KEY=ODDVEX_ADMIN_EMAILS` and `VALUE=<address>`. It warns if the address is the contact
   address.
3. `ACTION=deploy`, so the API runs with the new list.
4. `ACTION=admin` with `EMAIL=<address>`. It runs `python scripts/bootstrap_admin.py --email <address>` in the API
   container. The script refuses an address that is not listed. For a listed address it creates the account, or
   **takes over the account that exists, whoever registered it**: new random password, address marked verified,
   every earlier token and email link ended, suspension lifted, role given, `admin.bootstrap` written to the audit
   log. The password is printed once.
5. Sign in with that password and change it. Then send `ACTION=status`: the printed password stays in the output of
   the `admin` run until the ops container is replaced by the next run or removed.
6. Confirm `/app/admin` loads for that account and answers 404 for a normal one.

Every `ACTION=admin` run sets and prints another new password and ends the previous one.

To remove:

1. `ACTION=setenv` with `KEY=ODDVEX_ADMIN_EMAILS` and the list without the address (an empty `VALUE` for none).
2. `ACTION=deploy`. The account is demoted at its next request (`role.removed`). No database update and no token
   rotation are needed.

Risks to keep in mind:

- An address that is listed but whose account was registered by someone else is harmless until `ACTION=admin` runs,
  and `ACTION=admin` takes the account over. The person who registered it loses access to it.
- A deploy that loses the list (an empty `ODDVEX_ADMIN_EMAILS`) demotes every administrator at their next request.
- Administrators have no second factor (THREAT_MODEL S-3). Who the first administrator is, and whether MFA comes
  first, is open (DECISION_LOG O-12).
- A deploy refuses a commit without `services/api/scripts/bootstrap_admin.py` while the list holds an address: older
  releases gave the role to whoever used an account with a listed address. `ACTION=rollback` does not check this, so
  empty the list before rolling back to such a release.

## 9. Scripts

All of these are in `services/api/scripts/` and in the API image (`/app/scripts`).

### `bootstrap_admin.py`

Section 8. On the preview it is run only through `ACTION=admin`. Exit status 0 when the account is ready, 1 when it
was refused or failed, 2 for a wrong command line. Safe while the API is serving.

### `evaluate_alerts.py` and `grade_picks.py`

Run by the `worker` container every two minutes on the preview. `evaluate_alerts.py` evaluates the alert rules of
every user who has active ones and prints `N user(s), N rule(s) evaluated, N fired, N expired, N failed.`; exit status
1 if any user failed, each named on standard error with the exception type. `grade_picks.py` grades pending community
picks. Both are idempotent and safe while the API is serving, use the same environment as the API, and take
`--dry-run` to report without saving. They deliver in-app notifications only.

### `seed_demo.py`

Creates `demo@oddvex.test` with sample bets, alert rules and notifications. Safe to run more than once.

- Password: the value of `ODDVEX_DEMO_PASSWORD`. The default is published in the README. Never run this against a
  reachable environment with the default.
- Refuses to run when `ODDVEX_ENV=production` unless `--allow-production` is passed (exit code 2). Do not pass that
  flag without Founder approval (G-09): it creates a known account in production. No action runs it on the preview.
- `ODDVEX_AUTO_SEED_DEMO=true` does the same at API startup and is ignored in production.

### Migrations

On the preview only `ACTION=deploy` runs migrations. On a developer machine:

```bash
cd services/api
.venv/bin/alembic current
.venv/bin/alembic history
.venv/bin/alembic upgrade head      # additive only without G-08
```

## 10. Things never to do

- Run a migration downgrade in production without G-08.
- Edit production data by hand without Founder approval and a second person.
- Copy production data, or a dump from `/opt/oddvex/backups`, to staging, preview, a laptop or a ticket.
- Put a secret value in a ticket, a chat message, a log line or this repository.
- Turn off rate limiting, the stale labels or the "Synthetic data" label to make a problem go away.
- Pass `--allow-production` to `seed_demo.py` on your own authority.
- List a published address in `ODDVEX_ADMIN_EMAILS`.
- Send email to users during an incident without Founder approval (G-06).
- Change the shared Caddyfile other than through `ACTION=caddy`, or touch another project's containers: the server
  is shared.

## 11. After any production change

Record in `docs/product/DECISION_LOG.md`, `docs/product/BUILD_STATUS.md` or the incident record: what changed, who
approved, who did it, when, how it was verified, and how to undo it. `ops.sh` also appends one line per deploy,
rollback, restore, setenv and admin run to `/opt/oddvex/ops.log` on the server; `ACTION=status` shows the last five.

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
