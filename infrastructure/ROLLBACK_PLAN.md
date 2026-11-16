# Rollback plan

Last updated: 2026-11-16 · Status: **procedure only. Never rehearsed. No environment exists to rehearse it in.**

Rehearsing this in staging is a launch requirement (`docs/compliance/LAUNCH_READINESS_CHECKLIST.md` sections 6
and 12). Until that is done and recorded, do not rely on any step here working as written.

Related: `RUNBOOK.md` (operations), `DEPLOYMENT_PLAN.md` (how a release goes out),
`docs/compliance/INCIDENT_RESPONSE.md` section 5.8.

## 1. Principles

1. **Roll the application back, not the database.** A schema downgrade destroys data and is gate G-08.
2. **Every release must be reversible without a schema change.** If a release cannot meet that, it says so in its
   pull request and the Founder approves it before it ships.
3. **Stop the harm first.** A rollback does not need a root cause.
4. **Do not improvise database fixes.** Restoring from backup needs Founder approval.
5. **A rollback is a production deploy.** The person doing it must already hold deploy authority under G-03. Who
   that is: to be decided by the Founder before the first production release.

## 2. Rollback triggers

Any one is enough. The numeric thresholds are blank on purpose: no production traffic exists to set them from.
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

- [ ] The previous known-good build of web and API is identified and can be redeployed (deployment id or image tag
      written in the release record)
- [ ] The release's migrations are read and classified additive or destructive (`DEPLOYMENT_PLAN.md` section 6)
- [ ] No destructive migration without G-08 on record
- [ ] The previous application version runs against the new schema. State how this was checked
- [ ] A database restore point exists from before the migration. Method: to confirm with vendor docs
- [ ] The release does not change `ODDVEX_JWT_SECRET` (that signs everyone out and is not undone by a rollback)
- [ ] Environment variable changes in this release are listed, with their previous values held in the secret store's
      history or by the release owner, never in this repository
- [ ] The release owner and a second person are named and reachable for ______ after release
- [ ] If the mobile app depends on this API release: confirmed that the previous API still serves the published
      mobile build (section 6)

## 4. Procedure: application rollback (no schema change)

| Step | Action | Owner |
|---|---|---|
| 1 | Declare the rollback in the incident channel. Note the time and the trigger | Release owner |
| 2 | Redeploy the previous known-good build of the affected app (web, API or both). On a managed host, use its action for restoring a previous deployment (to confirm with vendor docs). With Docker, start the previous image tag | Release owner |
| 3 | Restore any environment variable the release changed | Release owner |
| 4 | Run the smoke test (`DEPLOYMENT_PLAN.md` section 10) | Second person |
| 5 | Confirm the trigger condition is gone | Second person |
| 6 | Tell the Founder. Decide whether users need to be told (Founder; any email is G-06) | Release owner |
| 7 | Write the record (section 8) | Release owner |

Order when both apps roll back: API contract first. The web app and the published mobile build must both work
against whichever API is live. The API schema is treated as a contract: fields are added, not renamed
(`services/api/README.md`), which is what makes an older client safe against a newer API. The reverse (newer web
against older API) is **not** safe if the web release uses a route the old API lacks. So: if only the web release is
bad, roll back web alone; if the API release is bad, roll back the API and then any web release that depends on it.

## 5. Procedure: release that included a migration

### 5.1 Additive migration (the only kind that exists today: 0001 to 0003)

1. Roll back the application as in section 4. **Leave the schema at the new revision.**
2. Docker only: an older image will fail at `alembic upgrade head` because it does not know the newer revision
   (see `RUNBOOK.md` section 5). Start it with the command overridden to run uvicorn only. On a host where
   migrations are a separate release step this does not arise.
3. Confirm with `alembic current` (run from the **new** code) that the schema is at the expected revision and was
   fully applied.
4. New tables and columns stay in place, unused, until the fixed release ships. Data written to them by the bad
   release stays too. Decide in the review whether any of it must be cleaned up (a bulk delete is G-08).

### 5.2 Migration failed part-way

1. Stop. Do not re-run it, do not downgrade, do not edit tables by hand.
2. Keep or restore the previous application version.
3. Establish the real state: `alembic current`, and compare the tables with what the migration creates.
4. Declare an incident (INCIDENT_RESPONSE 5.8).
5. Options, each needing the Founder: complete the migration with a corrected script; restore to the restore point
   taken before the migration.

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
- Restore mechanics and duration: to confirm with vendor docs and by a test restore.

## 6. What a rollback cannot undo

| Thing | Why | What to do instead |
|---|---|---|
| A mobile build already installed from a store | Users keep the build they have. Store rollback and review timing are outside our control (to confirm against current store documentation) | Keep the API compatible with every published mobile build. Fix forward with a new build |
| Notifications already created | They are rows users have seen | Delete only with Founder approval (bulk delete, G-08); consider a correction |
| Emails already sent | Not applicable today: nothing sends | When email exists: a correction email is G-06 |
| Bets auto-settled wrongly | Settlement changed stored results and profit | Incident, data-integrity review, corrective script reviewed and approved |
| A rotated JWT secret | Users are already signed out | None needed |
| DNS changes | Resolvers cache for the record's TTL | Restore the saved records; wait out the TTL (`DEPLOYMENT_PLAN.md` section 8) |
| Search engines or caches holding a bad page | Outside our control | Fix the page; request recrawl if it matters |

## 7. Kill switches

Feature flags are in progress in the API and are not yet documented in `services/api/README.md`. Until they are,
there is no way to turn a single feature off without a deploy.

Existing switches, all by environment variable and all needing a restart:

| Variable | Effect | Use in an incident |
|---|---|---|
| `ODDVEX_RATE_LIMIT_AUTH_PER_MINUTE`, `ODDVEX_RATE_LIMIT_ASSISTANT_PER_MINUTE` | Tighten or loosen per-IP limits | Tighten during a credential-stuffing wave. Remember web sign-ins share one bucket today |
| `ODDVEX_ALERT_EVAL_MIN_SECONDS` | How often reading notifications triggers alert evaluation | Raise to reduce load. It does not disable alerts |
| `ODDVEX_JWT_SECRET` | Rotation signs every user out | Suspected token or secret compromise |
| `ODDVEX_ADMIN_EMAILS` | Stops new promotions only. Does not demote | See `RUNBOOK.md` section 8 |

When flags land, list here: the flag name, what it turns off, who may flip it, and how the change is recorded.

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

No rehearsal has been run.
