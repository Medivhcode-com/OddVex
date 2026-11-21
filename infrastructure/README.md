# Infrastructure

Last updated: 2026-11-21

**A private preview is deployed.** Since 2026-11-18 OddVex runs on the shared Hostinger VPS (decision D-016), in
production mode on synthetic data: `preview.oddvex.com` behind a password, and `api-preview.oddvex.com` with no
password, open to the internet, accepting sign-ups. The server holds production credentials (a generated database
password, JWT secret and preview password) in `/opt/oddvex/` on the server, never in this repository. `oddvex.com`
itself is unchanged and no public launch has been decided. What has been deployed and checked is recorded in
`docs/product/BUILD_STATUS.md`, section "Private preview on the Hostinger VPS".

The server setup is in `hostinger/`: the compose file, the one-shot ops container and `hostinger/ops.sh`, through
which every operation on the server is done. Nobody has a shell on the server.

## What is here

| File | What it is | Status |
|---|---|---|
| [hostinger/README.md](./hostinger/README.md) | The preview on the Hostinger VPS: how the server is shared, the `ops.sh` actions, what a deploy does, going back, settings, the first administrator, limits | Current. Describes what is deployed |
| [RUNBOOK.md](./RUNBOOK.md) | How to operate the preview: health checks, logs, common failures, deploys and migrations, restores, secret rotation, admin access, sign-in refusals, scripts | Written from the code at release `2b0c7c1`. The deploy steps have run on the server; restore, rollback and secret rotation have not |
| [ROLLBACK_PLAN.md](./ROLLBACK_PLAN.md) | When and how to roll back a release or restore the database | Procedure for the preview. Rollback and restore are rehearsed in tests only, not on the server |
| [DEPLOYMENT_PLAN.md](./DEPLOYMENT_PLAN.md) | The earlier plan for Vercel, Neon and Resend (decisions D-004, D-005), with a summary of how the preview is deployed instead | The Vercel plan was not executed and is not the current plan |

## What exists outside this directory

| Thing | Where | Verified how |
|---|---|---|
| API container image | `services/api/Dockerfile` | Built and smoke-tested in CI (`docker` job in `.github/workflows/ci.yml`); runs on the preview |
| Web container image | `apps/web/Dockerfile` | Built and smoke-tested in the same CI job; runs on the preview |
| Local stack | `docker-compose.yml` | Not started by anyone yet (see `docs/product/BUILD_STATUS.md`, "Not verified") |
| Database migrations | `services/api/alembic/versions/` (0001 to 0007) | Upgrade and downgrade tested on SQLite and PostgreSQL 16 in CI. Applied on the server's PostgreSQL 17 up to 0007 on 2026-11-21 |
| Server scripts | `hostinger/ops.sh`, `hostinger/compose.yaml`, `hostinger/ops.compose.yaml` | Tests in `hostinger/tests/` run the script against a stand-in for `docker` and a real PostgreSQL 16 (CI job "Infrastructure (ops script, compose files)"); deploys have run on the server |
| CI | `.github/workflows/ci.yml` | Runs on pull requests and on pushes to `main` |

## Approval gates that apply to everything in this directory

Gates are defined in `docs/product/ROADMAP.md` and listed in `PROJECT_CONSTITUTION.md` section 3. No row of
`docs/product/DECISION_LOG.md` records a Founder `Approval` for any gate below. The preview was deployed and its
credentials created on the authority of D-016 and D-007, and since 2026-11-19 of the Founder's waiver D-019; the log
records this in D-021 and asks the Founder to confirm it (O-17). The constitution's note on D-019 is at the end of
its section 3.

| Gate | What it covers here |
|---|---|
| G-02 | Creating any paid account or plan: hosting, managed database, email, monitoring, scheduler |
| G-03 | Any production deploy and the DNS cut-over for oddvex.com |
| G-06 | Sending any real email |
| G-08 | Any destructive migration, including a migration downgrade that drops data |
| G-09 | Creating, rotating, sharing or using production secrets; granting production access such as the admin role |
| G-10 | Accepting vendor contracts and data-processing terms; publishing legal pages as final |
| G-13 | Adding a sub-processor that receives personal data |

The Founder stated a **preference** for Vercel, Neon and Resend (D-004, D-005) and later chose the Hostinger VPS
(D-016). See `docs/product/DECISION_LOG.md`.

## Rules for this directory

- Names of environment variables only. Never values.
- No vendor feature is stated as fact unless the repository proves it. Everything else is marked
  "to confirm with vendor docs".
- No costs, dates or service levels. Where one is needed it says "To be decided" and names who decides.
