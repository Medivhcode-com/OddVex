# Infrastructure

Last updated: 2026-11-16

**No infrastructure exists.** Nothing is deployed, no cloud account, database, domain record, email service,
scheduler or monitoring tool has been created or paid for, and no production credential exists. This directory holds
plans and procedures only. It contains no infrastructure-as-code, no vendor configuration and no secrets.

Everything OddVex runs today runs on a developer machine or in GitHub Actions, on synthetic data.

## What is here

| File | What it is | Status |
|---|---|---|
| [DEPLOYMENT_PLAN.md](./DEPLOYMENT_PLAN.md) | Plan for the Founder's stated hosting preference (Vercel for web and API, Neon PostgreSQL, Resend for email) | Plan only. Not executed. Not approved |
| [RUNBOOK.md](./RUNBOOK.md) | How to operate the service: health checks, logs, common failures, secret rotation, admin access, scripts | Grounded in the code as of 2026-11-16. Never exercised against a deployed environment |
| [ROLLBACK_PLAN.md](./ROLLBACK_PLAN.md) | When and how to roll back a release or a migration | Procedure only. Never rehearsed |

## What exists outside this directory

| Thing | Where | Verified how |
|---|---|---|
| API container image | `services/api/Dockerfile` | Built and smoke-tested in CI (`docker` job in `.github/workflows/ci.yml`) |
| Web container image | `apps/web/Dockerfile` | Built and smoke-tested in the same CI job |
| Local stack | `docker-compose.yml` | **Not started by anyone yet** (see `docs/product/BUILD_STATUS.md`, "Not verified") |
| Database migrations | `services/api/alembic/versions/` (0001 to 0003) | Upgrade and downgrade tested on SQLite and PostgreSQL 16 in CI |
| CI | `.github/workflows/ci.yml` | Runs on pull requests and on pushes to `main` |

## Approval gates that apply to everything in this directory

Gates are defined in `docs/product/ROADMAP.md`. None has been approved.

| Gate | What it blocks here |
|---|---|
| G-02 | Creating any paid account or plan: hosting, managed database, email, monitoring, scheduler |
| G-03 | Any production deploy and the DNS cut-over for oddvex.com |
| G-06 | Sending any real email |
| G-08 | Any destructive migration, including a migration downgrade that drops data |
| G-09 | Creating, rotating, sharing or using production secrets |
| G-10 | Accepting vendor contracts and data-processing terms; publishing legal pages as final |
| G-13 | Adding a sub-processor that receives personal data |

The Founder has stated a **preference** for Vercel, Neon and Resend. A preference is not an approval. See
`docs/product/DECISION_LOG.md`.

## Rules for this directory

- Names of environment variables only. Never values.
- No vendor feature is stated as fact unless the repository proves it. Everything else is marked
  "to confirm with vendor docs".
- No costs, dates or service levels. Where one is needed it says "To be decided" and names who decides.

## Hostinger VPS preview

The Founder chose the Hostinger VPS for hosting (decision D-016). See `hostinger/README.md`. `DEPLOYMENT_PLAN.md`
(Vercel + Neon) is kept for reference and is not the current plan.
