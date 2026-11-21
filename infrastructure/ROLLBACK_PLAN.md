# Rollback plan

Last updated: 2026-11-21 · Status: **procedure for the private preview on the Hostinger VPS. `ACTION=rollback`,
`ACTION=restore` and the automatic put-back after a failed deploy are rehearsed in tests (`hostinger/tests/`, with a
stand-in for `docker` and a real PostgreSQL 16) and have not been run on the server.**

Rehearsing this on a server is a launch requirement (`docs/compliance/LAUNCH_READINESS_CHECKLIST.md` sections 6
and 12). Until that is done and recorded, do not rely on any step here working as written.

Related: `RUNBOOK.md` (operations), `hostinger/README.md` (the actions in full, section "Going back"),
`DEPLOYMENT_PLAN.md` (the smoke test, section 10), `docs/compliance/INCIDENT_RESPONSE.md` section 5.8.

## 1. Principles

1. **Roll the application back, not the database.** A schema downgrade destroys data and is gate G-08.
2. **Every release must be reversible without a schema change.** If a release cannot meet that, it says so in its
   pull request and the Founder approves it before it ships.
3. **Stop the harm first.** A rollback does not need a root cause.
4. **Do not improvise database fixes.** Restoring from backup needs Founder approval.
5. **A rollback is a production deploy.** The person doing it must hold deploy authority under G-03. On the preview
   that is the build session, under D-019 (decision log D-021). Who holds it at a public launch: to be decided by
   the Founder (O-10).

## 2. Rollback triggers

Any one is enough. The numeric thresholds are blank on purpose: the preview has no measured traffic to set them from,
and nothing measures error rates or response times on it.
To be decided: engineering proposes, Founder confirms, before the first release.

| # | Trigger | Threshold | Decides |
|---|---|---|---|
| R-1 | The post-deploy smoke test fails (`DEPLOYMENT_PLAN.md` section 10) | Any failed check | Release owner, immediately |
| R-2 | The API will not start or `/health` fails | Any | Release owner, immediately |
| R-3 | Users cannot sign in, or signed-in pages fail | Any confirmed report that reproduces | Release owner |
| R-4 | A user can see or change another user's data | Any | Release owner, immediately. Also SEV1 |
| R-5 | A number is wrong: prices, best price, calculator output, profit and loss, settlement | Any reproducible case | Release owner. Also INCIDENT_RESPONSE 5.4 |
| R-6 | Data presented as current is stale or unlabelled, or synthetic data loses its label | Any | Release owner |
| R-7 | Server error rate after release | Above ______ % for ______ minutes | Release owner |
| R-8 | Response time after release | Above ______ for ______ minutes | Release owner |
| R-9 | A notification, page or message contains wording that breaks `docs/marketing/BRAND_VOICE.md` or the responsible-gambling rules | Any | Release owner and Founder |
| R-10 | The release crossed an approval gate without sign-off | Any | Founder |
| R-11 | Migration failed or left the schema in an unknown state | Any | Stop. Section 5 |

When in doubt, roll back. Rolling forward with a fix is allowed only when the fix is smaller and better understood
than the rollback, and the release owner says so in the incident record.

## 3. Before every release (what makes rollback possible)

- [ ] The previous known-good release is identified and its images are still on the server (`ACTION=status`,
      "releases with images on this server"); written in the release record
- [ ] The release's migrations are read and classified additive or destructive (`DEPLOYMENT_PLAN.md` section 6)
- [ ] No destructive migration without G-08 on record
- [ ] The previous application version runs against the new schema. State how this was checked
- [ ] A database restore point exists from before the migration. On the preview `ACTION=deploy` writes and checks
      a pre-deploy dump before it migrates and stops if it cannot
- [ ] The release does not change `ODDVEX_JWT_SECRET` (that signs everyone out and is not undone by a rollback)
- [ ] Setting changes in this release are listed. `ACTION=setenv` prints the old and the new value of a non-secret
      setting; secrets are never printed and never written in this repository
- [ ] The release owner and a second person are named and reachable for ______ after release
- [ ] If the mobile app depends on this API release: confirmed that the previous API still serves the published
      mobile build (section 6)

## 4. Procedure: application rollback (no schema change)

| Step | Action | Owner |
|---|---|---|
| 1 | Declare the rollback in the incident channel. Note the time and the trigger | Release owner |
| 2 | `ACTION=rollback` with `REF` set to the previous known-good release. It starts the images of that release if they are on the server and builds that commit otherwise; it never applies or undoes a migration. Web and API go back together: they are one release | Release owner |
| 3 | Put back any setting the release changed (`ACTION=setenv`; it takes effect with the rollback only if sent before it) | Release owner |
| 4 | Run the smoke test (`DEPLOYMENT_PLAN.md` section 10) | Second person |
| 5 | Confirm the trigger condition is gone | Second person |
| 6 | Tell the Founder. Decide whether users need to be told (Founder; any email is G-06) | Release owner |
| 7 | Write the record (section 8) | Release owner |

On the preview web and API are one release and roll back together. On another host, order when both apps roll back:
API contract first. The web app and every mobile build in use must both work against whichever API is live. The API schema is treated as a contract: fields are added, not renamed
(`services/api/README.md`), which is what makes an older client safe against a newer API. The reverse (newer web
against older API) is **not** safe if the web release uses a route the old API lacks. So: if only the web release is
bad, roll back web alone; if the API release is bad, roll back the API and then any web release that depends on it.

## 5. Procedure: release that included a migration

### 5.1 Additive migration (the only kind that exists today: 0001 to 0007)

1. Roll back the application as in section 4. **Leave the schema at the new revision.**
2. On the preview the API container never migrates at start (the compose file overrides the image's command), so the
   older image starts against the newer schema. `ACTION=rollback` says so when the database is newer than the
   release, and prints the newest pre-deploy dump taken while that release ran, with the lines to restore it. It
   refuses when the database is older than the release needs: use `ACTION=deploy` then.
3. Confirm with `ACTION=status` that the schema is at the expected revision.
4. New tables and columns stay in place, unused, until the fixed release ships. Data written to them by the bad
   release stays too. Decide in the review whether any of it must be cleaned up (a bulk delete is G-08).

### 5.2 Migration failed part-way

1. Stop. Do not re-run it, do not downgrade, do not edit tables by hand.
2. Keep the previous application version: a failed migration step in `ACTION=deploy` replaces no container.
3. Establish the real state: `ACTION=status` shows the revision; compare the tables with what the migration creates.
4. Declare an incident (INCIDENT_RESPONSE 5.8).
5. Options, each needing the Founder: complete the migration with a corrected script; restore the pre-deploy dump
   that the failed deploy printed (section 5.4).

### 5.3 Destructive migration or schema downgrade

G-08, every time. See `RUNBOOK.md` section 6 for what each existing downgrade drops and the approved procedure.

### 5.4 Restore from backup

- Founder approval required, recorded before the restore starts.
- Everything written after the restore point is lost. State the size of that window to the Founder before they
  decide.
- A restore brings back accounts that users deleted after the restore point. Those deletions must be re-applied
  before the service is reopened. **There is no deletion ledger in the code today**, so the only source is the
  `account.deleted` entries in the audit log, and the audit log is in the same database being restored. This gap
  must be closed before real users exist. Owner: to be decided (engineering).
- Mechanics: `ACTION=restore` with `DUMP` and `CONFIRM` set to the same file name from `/opt/oddvex/backups`
  (`ACTION=restore` without `DUMP` lists them). It dumps the live database first (`prerestore-<time>.dump`), loads the
  chosen dump into a new database, stops the API, worker, backup and web containers for the swap, starts them again
  and keeps the replaced database as `oddvex_replaced_<time>`. A restore is undone by restoring its `prerestore-`
  dump. Details: `hostinger/README.md`, "Going back".
- Which dumps exist: one daily dump (kept 14 days by default) and the newest five pre-deploy dumps, all on the same
  disk as the database. Losing the server loses them too.
- Duration: not measured. A restore has not been run on the server; it is rehearsed in tests against PostgreSQL 16.

## 6. What a rollback cannot undo

| Thing | Why | What to do instead |
|---|---|---|
| A mobile build already installed from a store | Users keep the build they have. Store rollback and review timing are outside our control (to confirm against current store documentation) | Keep the API compatible with every published mobile build. Fix forward with a new build |
| Notifications already created | They are rows users have seen | Delete only with Founder approval (bulk delete, G-08); consider a correction |
| Emails already sent | Not applicable today: nothing sends | When email exists: a correction email is G-06 |
| A restore | The replaced database is kept as `oddvex_replaced_<time>` and the live one was dumped first | Restore the `prerestore-` dump it printed |
| Bets auto-settled wrongly | Settlement changed stored results and profit | Incident, data-integrity review, corrective script reviewed and approved |
| A rotated JWT secret | Users are already signed out | None needed |
| DNS changes | Resolvers cache for the record's TTL | Restore the saved records; wait out the TTL (`DEPLOYMENT_PLAN.md` section 8) |
| Search engines or caches holding a bad page | Outside our control | Fix the page; request recrawl if it matters |

## 7. Kill switches

Feature flags are global switches stored in the database with defaults in code (`services/api/src/oddvex_api/flags/catalog.py`).
An administrator turns one on or off with `PUT /v1/admin/flags/{key}` or on `/app/admin/flags`; it applies to everyone
at once, needs no restart and writes `admin.flag_set` to the audit log with the value before and after.

| Flag | Default | What turning it off stops |
|---|---|---|
| `value_screen` | On | The market discrepancies screen and `GET /v1/value` |
| `tracker_analytics` | On | Tracker analytics |
| `community` | Off | The whole community module, member and moderation routes |
| `community_leaderboard` | Off | The community leaderboard |
| `email_flows` | Off in production | Email verification and password reset |
| `premium_gating` | Off | Plan enforcement. Turning it on is a pricing decision (G-07) |

**The preview has no administrator** (`ODDVEX_ADMIN_EMAILS` is empty), so no flag can be switched there until one is
made (`RUNBOOK.md` section 8: setenv, deploy, `ACTION=admin`). Who may flip a flag is to be decided with the first
administrator (O-12); every flip is recorded in the audit log.

Other switches, all settings that need a deploy to take effect:

| Setting | Effect | Use in an incident |
|---|---|---|
| `ODDVEX_ADMIN_EMAILS` (`ACTION=setenv`) | An address taken off the list loses the admin role at its next request | Remove an administrator (`RUNBOOK.md` section 8) |
| `ODDVEX_PASSWORD_HASH_CONCURRENCY`, `ODDVEX_PASSWORD_HASH_WAIT_SECONDS` (`ACTION=setenv`) | How many password hashes run at once and how long a sign-in waits for one | Lower to protect memory during a sign-in flood |
| `ODDVEX_RATE_LIMIT_AUTH_PER_MINUTE`, `ODDVEX_RATE_LIMIT_ASSISTANT_PER_MINUTE`, `ODDVEX_LOGIN_MAX_FAILURES_PER_EMAIL`, `ODDVEX_ALERT_EVAL_MIN_SECONDS` | Per-IP limits, the per-email sign-in ceiling, the lazy alert evaluation | On the preview none of these is passed by `hostinger/compose.yaml` or accepted by `ACTION=setenv`; changing one there needs a change to those files first |
| `ODDVEX_JWT_SECRET` | Rotation signs every user out | No action rotates it on the preview (`RUNBOOK.md` section 7) |
| `ACTION=stop` | Takes OddVex offline, keeping the database and the dumps | Last resort: suspected leak, data exposure |

## 8. Rollback record

```
Release / version rolled back:   ____________
Rolled back to:                  ____________
Trigger (R-number and evidence): ____________
Decided by / at (UTC):           ____________
Performed by:                    ____________
Verified by:                     ____________
Migration in the release:        none / additive / destructive (revision ______)
Schema state after rollback:     ____________
Environment variables restored:  ____________ (names only)
Data written by the bad release: ____________ (kept / cleaned with approval ______)
User impact and duration:        ____________
Users or Founder informed:       ____________
Follow-up issue (Linear):        ____________
Review date:                     ____________
```

## 9. Rehearsal log

| Date | Environment | Scenario | Result | Time taken | By |
|---|---|---|---|---|---|
| | | Application rollback, no migration | | | |
| | | Rollback across an additive migration | | | |
| | | Restore to a point in time, then re-apply deletions | | | |
| | | DNS record restore | | | |

No rehearsal has been run on a server. In tests, `infrastructure/hostinger/tests/test_ops_deploy.py` runs deploy,
put-back and rollback against a stand-in for `docker`, and `infrastructure/hostinger/tests/test_restore_postgres.py`
runs the dump, restore and undo commands against a real PostgreSQL 16 server.
